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

    reading = await get_cached_latest()
    if not reading:
        return {"error": "No live data available"}

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


@router.get("/forecast")
async def get_aqi_forecast(horizon: int = Query(default=24, ge=1, le=72)):
    """Forecast AQI for the next N hours using XGBoost."""
    reading = await get_cached_latest()
    if not reading:
        return {"error": "No live data available"}

    forecasts = forecast_aqi(reading, horizon_hours=horizon)
    return {
        "current_aqi": reading.get("aqi"),
        "horizon_hours": horizon,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "forecasts": forecasts,
    }


@router.get("/anomaly")
async def get_anomaly_detection():
    """Check if current sensor reading is anomalous."""
    reading = await get_cached_latest()
    if not reading:
        return {"error": "No live data available"}

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


@router.get("/summary")
async def get_ml_summary():
    """Combined ML analysis — source + anomaly + mini forecast (6h)."""
    reading = await get_cached_latest()
    if not reading:
        return {"error": "No live data available"}

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
