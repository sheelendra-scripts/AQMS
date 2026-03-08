"""ThingSpeak data fetcher — polls channel every 30s and stores in DB.

When the ESP32 device is offline (all zeros or no data), falls back to
realistic simulated data so the dashboard always looks populated.
"""
import os
import math
import random
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
from sqlalchemy import select, desc

from services.database import async_session, SensorReading, init_db
from utils.aqi_calc import calculate_aqi, get_aqi_category
from ml.predictor import detect_source as _detect_source

logger = logging.getLogger("aqms.fetcher")

CHANNEL_ID = os.getenv("THINGSPEAK_CHANNEL_ID", "2697383")
READ_API_KEY = os.getenv("THINGSPEAK_READ_API_KEY", "RAYZJW1K4FBNIVP6")
BASE_URL = f"https://api.thingspeak.com/channels/{CHANNEL_ID}"

# Toggle for demo mode (auto-enabled when device sends zeros)
DEMO_MODE = os.getenv("DEMO_MODE", "auto")  # "auto", "true", "false"

# In-memory cache of most recent reading for instant API response
_latest_reading: Optional[dict] = None


# ─── Realistic demo data generator ───────────────────────────
def _generate_demo_reading(ts: Optional[datetime] = None) -> dict:
    """Generate a realistic reading based on time-of-day patterns."""
    now = ts or datetime.now(timezone.utc)
    hour = now.hour + now.minute / 60.0

    # Diurnal pattern: pollution peaks at ~8am and ~6pm (rush hours)
    morning_peak = math.exp(-((hour - 8) ** 2) / 8)
    evening_peak = math.exp(-((hour - 18) ** 2) / 8)
    traffic_factor = 0.3 + 0.7 * (morning_peak + evening_peak)

    # Base values with seasonal and random variation
    noise = lambda scale=1.0: random.gauss(0, scale)

    temperature = 28.0 + 5 * math.sin((hour - 14) * math.pi / 12) + noise(1.5)
    humidity = 55.0 - 15 * math.sin((hour - 14) * math.pi / 12) + noise(3)
    pm25 = max(5, 45 * traffic_factor + noise(12))
    co = max(0.1, 1.8 * traffic_factor + noise(0.3))
    no2 = max(0.005, 0.06 * traffic_factor + noise(0.01))
    tvoc = max(0.01, 0.35 * traffic_factor + noise(0.08))

    aqi = calculate_aqi(pm25, co, no2)
    cat = get_aqi_category(aqi)

    return {
        "timestamp": now.isoformat().replace("+00:00", "Z"),
        "temperature": round(max(15, min(45, temperature)), 1),
        "humidity": round(max(20, min(95, humidity)), 1),
        "pm25": round(pm25, 1),
        "tvoc": round(tvoc, 2),
        "no2": round(no2, 3),
        "co": round(co, 2),
        "aqi": aqi,
        "aqi_category": cat["category"],
        "aqi_color": cat["color"],
        "source_detected": "unknown",
        "ward_id": "ward_01",
        "demo": True,
    }


def _is_all_zeros(data: dict) -> bool:
    """Check if the ThingSpeak feed has all zero sensor values."""
    for key in ["field3", "field4", "field5", "field6"]:
        val = data.get(key)
        if val and float(val) != 0.0:
            return False
    return True


def _safe_float(val, default=0.0) -> float:
    try:
        return float(val) if val else default
    except (ValueError, TypeError):
        return default


def _safe_int(val, default=0) -> int:
    try:
        return int(float(val)) if val else default
    except (ValueError, TypeError):
        return default


async def fetch_latest_from_thingspeak() -> Optional[dict]:
    """Fetch the most recent reading from ThingSpeak REST API.
    Falls back to demo data when device is offline or all zeros."""
    global _latest_reading

    use_demo = DEMO_MODE == "true"

    if DEMO_MODE != "true":
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{BASE_URL}/feeds/last.json", params={"api_key": READ_API_KEY})
                if resp.status_code != 200:
                    logger.warning(f"ThingSpeak returned {resp.status_code}")
                    use_demo = True
                else:
                    data = resp.json()
                    if not data or not data.get("created_at") or _is_all_zeros(data):
                        logger.info("Device offline or all-zero data, using demo mode")
                        use_demo = True
                    else:
                        temperature = _safe_float(data.get("field1"))
                        humidity = _safe_float(data.get("field2"))
                        pm25 = _safe_float(data.get("field3"))
                        tvoc = _safe_float(data.get("field4"))
                        no2 = _safe_float(data.get("field5"))
                        co = _safe_float(data.get("field6"))
                        aqi_raw = _safe_int(data.get("field7"))

                        aqi = aqi_raw if aqi_raw > 0 else calculate_aqi(pm25, co, no2)
                        category_info = get_aqi_category(aqi)

                        try:
                            from datetime import datetime as _dt
                            _hour = _dt.now(timezone.utc).hour + _dt.now(timezone.utc).minute / 60.0
                            _src = _detect_source(pm25=pm25, co=co, no2=no2, tvoc=tvoc,
                                                  temperature=temperature, humidity=humidity, hour=_hour)
                            source_detected = _src.get("source", "unknown")
                        except Exception:
                            source_detected = "unknown"

                        reading = {
                            "timestamp": data["created_at"],
                            "temperature": round(temperature, 1),
                            "humidity": round(humidity, 1),
                            "pm25": round(pm25, 1),
                            "tvoc": round(tvoc, 2),
                            "no2": round(no2, 3),
                            "co": round(co, 2),
                            "aqi": aqi,
                            "aqi_category": category_info["category"],
                            "aqi_color": category_info["color"],
                            "source_detected": source_detected,
                            "ward_id": "ward_01",
                            "demo": False,
                        }

                        _latest_reading = reading
                        return reading

        except Exception as e:
            logger.error(f"ThingSpeak fetch error: {e}")
            use_demo = True

    # Demo fallback
    if use_demo or DEMO_MODE == "auto":
        reading = _generate_demo_reading()
        try:
            from datetime import datetime as _dt
            _hour = _dt.now(timezone.utc).hour + _dt.now(timezone.utc).minute / 60.0
            _src = _detect_source(pm25=reading["pm25"], co=reading["co"], no2=reading["no2"],
                                  tvoc=reading["tvoc"], temperature=reading["temperature"],
                                  humidity=reading["humidity"], hour=_hour)
            reading["source_detected"] = _src.get("source", "unknown")
        except Exception:
            reading["source_detected"] = "unknown"
        _latest_reading = reading
        return reading

    return _latest_reading


async def store_reading(reading: dict):
    """Persist a reading to SQLite."""
    try:
        ts = datetime.fromisoformat(reading["timestamp"].replace("Z", "+00:00"))
    except Exception:
        ts = datetime.now(timezone.utc)

    async with async_session() as session:
        # Avoid duplicate timestamps
        existing = await session.execute(
            select(SensorReading).where(SensorReading.timestamp == ts).limit(1)
        )
        if existing.scalar_one_or_none():
            return

        row = SensorReading(
            timestamp=ts,
            ward_id=reading.get("ward_id", "ward_01"),
            temperature=reading["temperature"],
            humidity=reading["humidity"],
            pm25=reading["pm25"],
            tvoc=reading["tvoc"],
            no2=reading["no2"],
            co=reading["co"],
            aqi=reading["aqi"],
            aqi_category=reading["aqi_category"],
        )
        session.add(row)
        await session.commit()


async def fetch_and_store():
    """One poll cycle: fetch from ThingSpeak and store."""
    reading = await fetch_latest_from_thingspeak()
    if reading:
        await store_reading(reading)
    return reading


async def get_cached_latest() -> Optional[dict]:
    """Return in-memory cached latest reading (instant, no network)."""
    if _latest_reading:
        return _latest_reading
    return await fetch_latest_from_thingspeak()


async def get_history(hours: int = 24, ward_id: str = "ward_01") -> list:
    """Fetch historical readings from the DB. Falls back to demo data if insufficient."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    async with async_session() as session:
        result = await session.execute(
            select(SensorReading)
            .where(SensorReading.timestamp >= cutoff)
            .where(SensorReading.ward_id == ward_id)
            .order_by(SensorReading.timestamp.asc())
        )
        rows = result.scalars().all()

        # Need at least 10 real data points to show real history
        if len(rows) >= 10:
            return [
                {
                    "timestamp": r.timestamp.isoformat() + "Z",
                    "temperature": r.temperature,
                    "humidity": r.humidity,
                    "pm25": r.pm25,
                    "tvoc": r.tvoc,
                    "no2": r.no2,
                    "co": r.co,
                    "aqi": r.aqi,
                    "aqi_category": r.aqi_category,
                }
                for r in rows
            ]

    # Generate demo history when DB has insufficient data
    return generate_demo_history(hours)


def generate_demo_history(hours: int = 24) -> list:
    """Generate realistic demo history data spanning the given hours."""
    now = datetime.now(timezone.utc)
    readings = []
    # One reading every 5 minutes
    interval_minutes = 5
    total_points = (hours * 60) // interval_minutes
    for i in range(total_points):
        ts = now - timedelta(minutes=(total_points - i) * interval_minutes)
        readings.append(_generate_demo_reading(ts))
    return readings


async def get_thingspeak_history(results: int = 100) -> list:
    """Fetch historical entries directly from ThingSpeak API."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(f"{BASE_URL}/feeds.json", params={"api_key": READ_API_KEY, "results": results})
            if resp.status_code != 200:
                return []
            data = resp.json()
            feeds = data.get("feeds", [])
            return [
                {
                    "timestamp": f.get("created_at"),
                    "temperature": _safe_float(f.get("field1")),
                    "humidity": _safe_float(f.get("field2")),
                    "pm25": _safe_float(f.get("field3")),
                    "tvoc": _safe_float(f.get("field4")),
                    "no2": _safe_float(f.get("field5")),
                    "co": _safe_float(f.get("field6")),
                    "aqi": _safe_int(f.get("field7")),
                }
                for f in feeds
                if f.get("created_at")
            ]
    except Exception as e:
        logger.error(f"ThingSpeak history error: {e}")
        return []
