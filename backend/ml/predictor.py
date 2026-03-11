"""ML Prediction Service — loads trained models and provides inference."""
import os
import math
import logging
import joblib
import numpy as np
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("aqms.ml")

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")

_source_model = None
_forecast_model = None
_anomaly_model = None


def _load_models():
    global _source_model, _forecast_model, _anomaly_model
    logger.info(f"Loading ML models from {MODELS_DIR}")
    logger.info(f"Models dir exists: {os.path.exists(MODELS_DIR)}, files: {os.listdir(MODELS_DIR) if os.path.exists(MODELS_DIR) else 'N/A'}")
    try:
        _source_model = joblib.load(os.path.join(MODELS_DIR, "source_classifier.pkl"))
        logger.info("✅ Source classifier loaded")
    except Exception as e:
        logger.error(f"❌ Source classifier failed: {e}")
        _source_model = None
    try:
        _forecast_model = joblib.load(os.path.join(MODELS_DIR, "aqi_forecaster.pkl"))
        logger.info("✅ AQI forecaster loaded")
    except Exception as e:
        logger.error(f"❌ AQI forecaster failed: {e}")
        _forecast_model = None
    try:
        _anomaly_model = joblib.load(os.path.join(MODELS_DIR, "anomaly_detector.pkl"))
        logger.info("✅ Anomaly detector loaded")
    except Exception as e:
        logger.error(f"❌ Anomaly detector failed: {e}")
        _anomaly_model = None


# Load on import
_load_models()


def _rule_based_source(pm25: float, co: float, no2: float, tvoc: float) -> dict:
    """Fallback rule-based source detection when ML model is unavailable."""
    pm25_co = pm25 / max(co, 0.01)
    tvoc_no2 = tvoc / max(no2, 0.001)

    # Score each source based on sensor signatures
    scores = {
        "vehicle": 0.0,
        "industrial": 0.0,
        "construction": 0.0,
        "biomass": 0.0,
        "mixed": 0.0,
    }

    # Vehicle indicators: high pm25/co ratio, moderate no2
    if pm25_co > 30 and no2 > 0.08:
        scores["vehicle"] += 0.45
    if pm25_co > 20:
        scores["vehicle"] += 0.15
    if co > 2.0 and co <= 5.0:
        scores["vehicle"] += 0.10

    # Industrial indicators: high no2 + co
    if no2 > 0.15 and co > 4.0:
        scores["industrial"] += 0.45
    if no2 > 0.10:
        scores["industrial"] += 0.15
    if tvoc > 0.5 and no2 > 0.12:
        scores["industrial"] += 0.10

    # Biomass indicators: high co + tvoc
    if co > 5.0 and tvoc > 0.8:
        scores["biomass"] += 0.45
    if co > 4.0:
        scores["biomass"] += 0.10
    if tvoc > 0.6:
        scores["biomass"] += 0.10

    # Construction indicators: high tvoc + pm25
    if tvoc > 1.0 and pm25 > 180:
        scores["construction"] += 0.45
    if pm25 > 150:
        scores["construction"] += 0.10
    if tvoc > 0.8:
        scores["construction"] += 0.05

    # Mixed: baseline
    scores["mixed"] = 0.05

    # Normalize to probabilities
    total = sum(scores.values())
    if total == 0:
        total = 1.0
    probabilities = {k: round(v / total, 3) for k, v in scores.items()}

    # Pick top source
    src = max(probabilities, key=probabilities.get)
    conf = probabilities[src]

    return {"source": src, "confidence": conf, "probabilities": probabilities}


def detect_source(pm25: float, co: float, no2: float, tvoc: float,
                  temperature: float, humidity: float, hour: float = None) -> dict:
    """Classify the pollution source from sensor readings."""
    if _source_model is None:
        return _rule_based_source(pm25, co, no2, tvoc)

    if hour is None:
        hour = datetime.now(timezone.utc).hour + datetime.now(timezone.utc).minute / 60.0

    pm25_co_ratio = pm25 / max(co, 0.01)
    tvoc_no2_ratio = tvoc / max(no2, 0.001)

    features = _source_model["features"]
    X = np.array([[pm25, co, no2, tvoc, temperature, humidity, hour, pm25_co_ratio, tvoc_no2_ratio]])

    pred = _source_model["model"].predict(X)[0]
    proba = _source_model["model"].predict_proba(X)[0]
    classes = _source_model["classes"]

    probabilities = {cls: round(float(p), 3) for cls, p in zip(classes, proba)}
    confidence = round(float(max(proba)), 3)

    return {
        "source": pred,
        "confidence": confidence,
        "probabilities": probabilities,
    }


def forecast_aqi(current_reading: dict, horizon_hours: int = 24) -> list:
    """Forecast AQI for the next N hours using XGBoost."""
    now = datetime.now(timezone.utc)
    current_hour = now.hour + now.minute / 60.0
    day_of_week = now.weekday()

    current_aqi = current_reading.get("aqi", 100)
    pm25 = current_reading.get("pm25", 50)
    co = current_reading.get("co", 1.5)
    no2 = current_reading.get("no2", 0.05)
    tvoc = current_reading.get("tvoc", 0.3)
    temp = current_reading.get("temperature", 30)
    humidity = current_reading.get("humidity", 50)

    if _forecast_model is None:
        # Rule-based diurnal forecast when model unavailable
        forecasts = []
        for h in range(1, horizon_hours + 1):
            future_hour = (current_hour + h) % 24
            morning = math.exp(-((future_hour - 8) ** 2) / 8)
            evening = math.exp(-((future_hour - 18) ** 2) / 8)
            traffic = 0.4 + 0.6 * (morning + evening)
            current_traffic = 0.4 + 0.6 * (
                math.exp(-((current_hour - 8) ** 2) / 8) + math.exp(-((current_hour - 18) ** 2) / 8))
            ratio = traffic / max(0.4, current_traffic)
            noise = (hash(str(h)) % 20 - 10)  # Deterministic small variation
            pred_aqi = int(max(20, min(500, current_aqi * ratio + noise)))

            if pred_aqi <= 50: cat, color = "Good", "#22c55e"
            elif pred_aqi <= 100: cat, color = "Satisfactory", "#84cc16"
            elif pred_aqi <= 200: cat, color = "Moderate", "#eab308"
            elif pred_aqi <= 300: cat, color = "Poor", "#f97316"
            elif pred_aqi <= 400: cat, color = "Very Poor", "#ef4444"
            else: cat, color = "Severe", "#991b1b"

            future_ts = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=h)
            forecasts.append({
                "hour_offset": h, "timestamp": future_ts.isoformat().replace("+00:00", "Z"),
                "predicted_aqi": pred_aqi, "category": cat, "color": color,
            })
        return forecasts

    # Recent AQI history (simulate lags from current)
    aqi_lag_1h = current_aqi
    aqi_lag_3h = current_aqi * 0.95
    aqi_lag_6h = current_aqi * 0.90

    forecasts = []
    model = _forecast_model["model"]

    # Get model's baseline prediction for current conditions to compute offset
    current_traffic = 0.4 + 0.6 * (
        math.exp(-((current_hour - 8) ** 2) / 8) + math.exp(-((current_hour - 18) ** 2) / 8))
    X_now = np.array([[current_hour, day_of_week, pm25, co, no2, tvoc,
                        temp, humidity, current_aqi, current_aqi * 0.95, current_aqi * 0.90]])
    model_baseline = float(model.predict(X_now)[0])
    # Offset to anchor predictions relative to actual current AQI
    aqi_offset = current_aqi - model_baseline

    for h in range(1, horizon_hours + 1):
        future_hour = (current_hour + h) % 24
        future_dow = (day_of_week + (int(current_hour + h) // 24)) % 7

        # Estimate future conditions with diurnal pattern
        morning = math.exp(-((future_hour - 8) ** 2) / 8)
        evening = math.exp(-((future_hour - 18) ** 2) / 8)
        traffic = 0.4 + 0.6 * (morning + evening)

        f_temp = 28 + 5 * math.sin((future_hour - 14) * math.pi / 12)
        f_humidity = 55 - 15 * math.sin((future_hour - 14) * math.pi / 12)
        f_pm25 = pm25 * traffic / max(0.4, current_traffic)

        X = np.array([[future_hour, future_dow, f_pm25, co * traffic, no2 * traffic,
                        tvoc * traffic, f_temp, f_humidity, aqi_lag_1h, aqi_lag_3h, aqi_lag_6h]])

        raw_pred = float(model.predict(X)[0])
        # Apply offset so predictions stay anchored to actual AQI level
        # Blend: offset decays slightly over time to allow natural trend
        blend = max(0.3, 1.0 - h * 0.01)
        pred_aqi = int(max(10, min(500, raw_pred + aqi_offset * blend)))

        # Determine category
        if pred_aqi <= 50:
            cat, color = "Good", "#22c55e"
        elif pred_aqi <= 100:
            cat, color = "Satisfactory", "#84cc16"
        elif pred_aqi <= 200:
            cat, color = "Moderate", "#eab308"
        elif pred_aqi <= 300:
            cat, color = "Poor", "#f97316"
        elif pred_aqi <= 400:
            cat, color = "Very Poor", "#ef4444"
        else:
            cat, color = "Severe", "#991b1b"

        future_ts = now.replace(minute=0, second=0, microsecond=0)
        from datetime import timedelta
        future_ts = future_ts + timedelta(hours=h)

        forecasts.append({
            "hour_offset": h,
            "timestamp": future_ts.isoformat().replace("+00:00", "Z"),
            "predicted_aqi": pred_aqi,
            "category": cat,
            "color": color,
        })

        # Update lags for next iteration
        aqi_lag_6h = aqi_lag_3h
        aqi_lag_3h = aqi_lag_1h
        aqi_lag_1h = pred_aqi

    return forecasts


def detect_anomaly(pm25: float, co: float, no2: float, tvoc: float,
                   temperature: float, humidity: float) -> dict:
    """Detect if current reading is anomalous."""
    if _anomaly_model is None:
        return {"is_anomaly": False, "anomaly_score": 0.0}

    X = np.array([[pm25, co, no2, tvoc, temperature, humidity]])
    prediction = _anomaly_model["model"].predict(X)[0]
    score = -_anomaly_model["model"].score_samples(X)[0]  # Higher = more anomalous

    return {
        "is_anomaly": bool(prediction == -1),
        "anomaly_score": round(float(score), 4),
    }
