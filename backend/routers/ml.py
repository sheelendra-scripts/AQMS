"""ML Predictions API — source detection, AQI forecasting, anomaly detection."""
from datetime import datetime, timezone
from fastapi import APIRouter, Query

from ml.predictor import detect_source, forecast_aqi, detect_anomaly
from services.thingspeak_fetcher import get_cached_latest

router = APIRouter(prefix="/api/ml", tags=["ml"])

# 60-second in-memory cache for ML source result
_source_cache: dict = {"result": None, "at": 0.0}


@router.get("/source")
async def get_source_detection():
    """Classify the current pollution source using the Random Forest model."""
    import time
    now = time.monotonic()
    # Return cached result if fresh (within 60 s)
    if _source_cache["result"] and now - _source_cache["at"] < 60:
        return _source_cache["result"]

    try:
        reading = await get_cached_latest()
        if not reading:
            return {"error": "No live data available", "source": "vehicle", "confidence": 0.5,
                    "probabilities": {"vehicle": 0.5, "industrial": 0.2, "biomass": 0.15, "construction": 0.1, "mixed": 0.05}}

        hour = datetime.now(timezone.utc).hour + datetime.now(timezone.utc).minute / 60.0
        result = detect_source(
            pm25=reading.get("pm25", 0),
            co=reading.get("co", 0),
            no2=reading.get("no2", 0),
            tvoc=reading.get("tvoc", 0),
            temperature=reading.get("temperature", 30),
            humidity=reading.get("humidity", 50),
            hour=hour,
        )
        result["timestamp"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        result["reading"] = {
            "pm25": reading.get("pm25"),
            "co": reading.get("co"),
            "no2": reading.get("no2"),
            "tvoc": reading.get("tvoc"),
        }
        _source_cache["result"] = result
        _source_cache["at"] = now
        return result
    except Exception as e:
        import logging
        logging.getLogger("aqms.ml").error(f"Source detection error: {e}")
        return {"source": "vehicle", "confidence": 0.5,
                "probabilities": {"vehicle": 0.5, "industrial": 0.2, "biomass": 0.15, "construction": 0.1, "mixed": 0.05},
                "error": str(e)}


@router.get("/forecast")
async def get_aqi_forecast(horizon: int = Query(default=24, ge=1, le=72)):
    """Forecast AQI for the next N hours using XGBoost."""
    try:
        reading = await get_cached_latest()
        if not reading:
            return {"error": "No live data available", "forecasts": []}

        forecasts = forecast_aqi(reading, horizon_hours=horizon)
        return {
            "current_aqi": reading.get("aqi"),
            "horizon_hours": horizon,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "forecasts": forecasts,
        }
    except Exception as e:
        import logging
        logging.getLogger("aqms.ml").error(f"Forecast error: {e}")
        return {"error": str(e), "forecasts": []}


@router.get("/anomaly")
async def get_anomaly_detection():
    """Check if current sensor reading is anomalous."""
    try:
        reading = await get_cached_latest()
        if not reading:
            return {"error": "No live data available", "is_anomaly": False, "anomaly_score": 0.0}

        result = detect_anomaly(
            pm25=reading.get("pm25", 0),
            co=reading.get("co", 0),
            no2=reading.get("no2", 0),
            tvoc=reading.get("tvoc", 0),
            temperature=reading.get("temperature", 30),
            humidity=reading.get("humidity", 50),
        )
        result["timestamp"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        result["reading"] = {
            "pm25": reading.get("pm25"),
            "co": reading.get("co"),
            "no2": reading.get("no2"),
            "tvoc": reading.get("tvoc"),
            "temperature": reading.get("temperature"),
            "humidity": reading.get("humidity"),
        }
        return result
    except Exception as e:
        import logging
        logging.getLogger("aqms.ml").error(f"Anomaly detection error: {e}")
        return {"is_anomaly": False, "anomaly_score": 0.0, "error": str(e)}


@router.get("/summary")
async def get_ml_summary():
    """Combined ML analysis — source + anomaly + mini forecast (6h)."""
    try:
        reading = await get_cached_latest()
        if not reading:
            return {"error": "No live data available",
                    "source_detection": {"source": "vehicle", "confidence": 0.5, "probabilities": {}},
                    "anomaly_detection": {"is_anomaly": False, "anomaly_score": 0.0},
                    "forecast_6h": []}

        hour = datetime.now(timezone.utc).hour + datetime.now(timezone.utc).minute / 60.0

        source = detect_source(
            pm25=reading.get("pm25", 0), co=reading.get("co", 0),
            no2=reading.get("no2", 0), tvoc=reading.get("tvoc", 0),
            temperature=reading.get("temperature", 30), humidity=reading.get("humidity", 50),
            hour=hour,
        )
        anomaly = detect_anomaly(
            pm25=reading.get("pm25", 0), co=reading.get("co", 0),
            no2=reading.get("no2", 0), tvoc=reading.get("tvoc", 0),
            temperature=reading.get("temperature", 30), humidity=reading.get("humidity", 50),
        )
        forecasts = forecast_aqi(reading, horizon_hours=6)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "current_aqi": reading.get("aqi"),
            "source_detection": source,
            "anomaly_detection": anomaly,
            "forecast_6h": forecasts,
        }
    except Exception as e:
        import logging
        logging.getLogger("aqms.ml").error(f"ML summary error: {e}")
        return {"error": str(e),
                "source_detection": {"source": "vehicle", "confidence": 0.5, "probabilities": {}},
                "anomaly_detection": {"is_anomaly": False, "anomaly_score": 0.0},
                "forecast_6h": []}
