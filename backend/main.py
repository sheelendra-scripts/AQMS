"""
AQMS Backend — FastAPI Application
Real-time air quality monitoring with ThingSpeak integration + WebSocket push.
"""
import os
import sys
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Set

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import json

# Fix imports to work from the backend directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.database import init_db
from services.thingspeak_fetcher import fetch_and_store, get_cached_latest
from routers import live, history, policy, wards, ml, alerts
from routers.alerts import evaluate_rules

logger = logging.getLogger("aqms")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

# --- WebSocket connection manager ---
connected_clients: Set[WebSocket] = set()


async def broadcast(data: dict):
    """Push data to all connected WebSocket clients."""
    dead = set()
    message = json.dumps(data)
    for ws in connected_clients:
        try:
            await ws.send_text(message)
        except Exception:
            dead.add(ws)
    connected_clients.difference_update(dead)


# --- Background polling task ---
async def polling_loop():
    """Fetch from ThingSpeak every 30s and broadcast to WebSocket clients."""
    logger.info("🌿 ThingSpeak polling loop started (30s interval)")
    while True:
        try:
            reading = await fetch_and_store()
            if reading:
                await broadcast({**reading, "status": "online"})
                logger.info(f"📡 AQI={reading['aqi']} ({reading['aqi_category']}) "
                            f"PM2.5={reading['pm25']} CO={reading['co']} NO2={reading['no2']}")
            else:
                logger.warning("⏳ No data from ThingSpeak")

            # Evaluate alert rules against all MCD zones
            try:
                from routers.wards import WARD_META, _generate_ward_reading
                ward_data = [_generate_ward_reading(w) for w in WARD_META]
                triggered = evaluate_rules(ward_data)
                for alert in triggered:
                    await broadcast({"type": "alert", **alert})
                    logger.warning(f"🚨 Alert [{alert['severity'].upper()}]: {alert['message']}")
            except Exception as ae:
                logger.error(f"Alert evaluation error: {ae}")

        except Exception as e:
            logger.error(f"Polling error: {e}")
        await asyncio.sleep(30)


# --- App lifecycle ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start DB and background poller on startup."""
    await init_db()
    logger.info("✅ Database initialized")
    task = asyncio.create_task(polling_loop())
    yield
    task.cancel()
    logger.info("🛑 Shutting down")


# --- FastAPI App ---
app = FastAPI(
    title="AQMS — Air Quality Monitoring System",
    description="Hyper-Local AQI Intelligence with ML-powered Pollution Source Detection",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins for Vercel/Render deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(live.router)
app.include_router(history.router)
app.include_router(policy.router)
app.include_router(wards.router)
app.include_router(ml.router)
app.include_router(alerts.router)


@app.get("/")
async def root():
    return {
        "name": "AQMS API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": ["/api/live", "/api/history", "/api/advisory", "/api/policy",
                      "/api/wards", "/api/ml/source", "/api/ml/forecast",
                      "/api/ml/anomaly", "/api/ml/summary",
                      "/api/alerts", "/api/alerts/rules", "/api/alerts/stats",
                      "/ws/live"],
    }


@app.get("/api/health")
async def health_check():
    reading = await get_cached_latest()
    return {
        "status": "healthy",
        "thingspeak": "connected" if reading else "waiting",
        "websocket_clients": len(connected_clients),
    }


@app.websocket("/ws/live")
async def websocket_live(ws: WebSocket):
    """WebSocket endpoint — pushes live readings every 30s."""
    await ws.accept()
    connected_clients.add(ws)
    logger.info(f"🔌 WebSocket client connected ({len(connected_clients)} total)")
    try:
        # Send current data immediately on connect
        reading = await get_cached_latest()
        if reading:
            await ws.send_text(json.dumps({**reading, "status": "online"}))
        # Keep alive
        while True:
            await ws.receive_text()   # Wait for any message (ping/pong)
    except WebSocketDisconnect:
        pass
    finally:
        connected_clients.discard(ws)
        logger.info(f"🔌 WebSocket client disconnected ({len(connected_clients)} total)")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
