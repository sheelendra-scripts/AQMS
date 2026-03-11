# AQMS - Air Quality Monitoring System

> **IoT-Enabled Real-Time Air Quality Intelligence Platform**
> Ward-Level Monitoring | ML Source Detection | Smart Alerts | Policy Recommendations

**Team MechaMinds**

[![Live Demo](https://img.shields.io/badge/Frontend-Vercel-black)](https://aqms-mechanminds.vercel.app)
[![Backend](https://img.shields.io/badge/Backend-Render-blue)](https://aqms-backend.onrender.com)

---

## Overview

AQMS is a full-stack air quality monitoring platform covering all **250 municipal wards** across **12 MCD zones** of Delhi. It combines IoT sensor hardware (ESP32), cloud data processing (FastAPI), three ML models, and an interactive React dashboard to provide real-time pollution intelligence.

**Key Metrics:** AQI range 71-362 across wards | Mean AQI: 262 | 7 configurable alert rules | 72-hour AQI forecast

---

## System Architecture

```
ESP32 + Sensors (PM2.5, CO, NO2, TVOC, DHT22)
       | every 30s via WiFi
       v
ThingSpeak Cloud (Channel 2697383)
       | REST API polling (30s)
       v
FastAPI Backend (Python)
  - ThingSpeak Data Fetcher (live + demo mode)
  - ML Pipeline (3 models + rule-based fallback)
  - Alert Engine (7 rules, 5-min debounce)
  - SQLite Storage (async via SQLAlchemy)
  - WebSocket Broadcast
       | REST + WebSocket
       v
React Frontend (Vite)
  - 8 Interactive Pages
  - Leaflet Ward Map (250 wards)
  - Recharts Visualization
  - Client-side ML Fallback
```

---

## Features

| Feature | Description |
|---|---|
| **Real-Time Dashboard** | Live AQI gauge, 6-metric grid, time-series chart, health advisory |
| **250-Ward Map** | Interactive Leaflet map with zone/ward toggle, color-coded AQI, search |
| **ML Source Detection** | Random Forest classifier identifying vehicle, industrial, construction, biomass, mixed sources |
| **AQI Forecasting** | XGBoost model predicting AQI 1-72 hours ahead with diurnal patterns |
| **Anomaly Detection** | Isolation Forest flagging unusual sensor patterns |
| **Smart Alerts** | 7 configurable rules with severity levels and 5-min debounce |
| **Health Advisory** | Population-specific guidance for general public and vulnerable groups |
| **Admin Policy Panel** | Source-specific intervention recommendations for municipal officials |

---

## Tech Stack

| Layer | Technology | Version |
|---|---|---|
| Backend | FastAPI + Uvicorn | 0.115.0 |
| Database | SQLite + SQLAlchemy (async) | 2.0.35 |
| ML | scikit-learn (RF, IF) + XGBoost | >=1.3, >=2.0 |
| Frontend | React + Vite | 19.2.0 / 7.3.1 |
| Maps | Leaflet + react-leaflet | 1.9.4 / 5.0.0 |
| Charts | Recharts | 3.8.0 |
| Animations | Framer Motion | 12.35.1 |
| IoT | ESP32 + ThingSpeak | Channel 2697383 |
| Deployment | Vercel (frontend) + Render (backend) | - |

---

## Project Structure

```
AQMS/
  backend/
    main.py                  # FastAPI app, CORS, startup, polling loop
    database.py              # SQLAlchemy async engine
    models.py                # ORM models (SensorReading, Ward)
    routers/
      live.py                # /api/live, /api/advisory
      history.py             # /api/history
      wards.py               # /api/wards (250 wards + 12 zones)
      ml.py                  # /api/ml/* (source, forecast, anomaly)
      alerts.py              # /api/alerts/* (rules, stats)
      policy.py              # /api/policy
    services/
      thingspeak_fetcher.py  # ThingSpeak polling + demo mode
    ml/
      predictor.py           # ML inference + rule-based fallback
      train_models.py        # Model training script
      models/                # Serialized .pkl files
    requirements.txt
  frontend/
    src/
      pages/                 # 8 pages (Dashboard, Map, Analytics, ML, Alerts, Advisory, Admin, Landing)
      components/            # 7 components (Sidebar, AQIGauge, MetricsGrid, WardMap, etc.)
      services/api.js        # API client + ThingSpeak fallback + client-side ML
      hooks/useData.js       # WebSocket + polling hooks
      data/wards.json        # 258-feature GeoJSON (12 zones + 246 wards)
    package.json
  scripts/
    generate_wards.py        # GeoJSON generator for 250 wards
    generate_report.py       # PDF report generator
  AQMS_Project_Report.pdf    # Comprehensive 27-page project report
```

---

## Hardware - IoT Sensor Node

| Component | Model | Measurement |
|---|---|---|
| Microcontroller | ESP32-WROOM-32 | WiFi/BLE, Dual-core 240MHz |
| PM2.5 Sensor | WINSEN ZPH02 (laser) | 0-1000 ug/m3 |
| CO Sensor | MQ-7 | 20-2000 ppm |
| NO2 Sensor | DFRobot MEMS | 0-5 ppm |
| TVOC Sensor | WINSEN ZP07-MP503 | 0-50 ppm |
| Temp/Humidity | DHT22 | -40 to 80C, 0-100% |
| Display | SSD1306 OLED 0.96" | 128x64 px |
| Power | 3.7V LiPo + MT3608 boost | ~8h runtime |

**Estimated cost per node: INR 5,200**

---

## ML Models

### 1. Pollution Source Classifier
- **Algorithm:** Random Forest (150 trees, max_depth=12)
- **Classes:** vehicle, industrial, construction, biomass, mixed
- **Features:** pm25, co, no2, tvoc, temperature, humidity, hour, pm25/co ratio, tvoc/no2 ratio
- **Fallback:** Rule-based detection (client-side + server-side) when model unavailable

### 2. AQI Forecaster
- **Algorithm:** XGBoost Regressor (200 rounds, lr=0.08)
- **Output:** Hourly AQI predictions for 1-72 hours
- **Features:** hour, day_of_week, pollutants, temperature, humidity, lag features (1h/3h/6h)

### 3. Anomaly Detector
- **Algorithm:** Isolation Forest (150 trees, contamination=0.05)
- **Output:** is_anomaly flag + anomaly_score (0-1)

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/live` | Latest sensor reading |
| GET | `/api/advisory` | Health advisory for current AQI |
| GET | `/api/history?hours=24` | Historical readings |
| GET | `/api/wards` | All 258 zone+ward readings |
| GET | `/api/wards/{ward_id}` | Single ward reading |
| GET | `/api/ml/source` | ML source classification |
| GET | `/api/ml/forecast?horizon=24` | AQI forecast |
| GET | `/api/ml/anomaly` | Anomaly detection |
| GET | `/api/ml/summary` | Combined ML analysis |
| GET | `/api/alerts` | Alert history |
| GET | `/api/alerts/rules` | Alert rules |
| GET | `/api/policy?source=vehicle` | Policy recommendations |
| GET | `/api/health` | Backend health check |
| WS | `/ws/live` | Real-time WebSocket feed |

---

## Quick Start

### Backend
```bash
cd backend
pip install -r requirements.txt
python3 -m uvicorn main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Environment Variables
```bash
# Backend (.env)
DEMO_MODE=auto          # auto | true | false
DATABASE_URL=sqlite+aiosqlite:///./aqms.db

# Frontend (Vercel or .env)
VITE_API_URL=https://your-backend.onrender.com
```

---

## Deployment

| Component | Platform | Config |
|---|---|---|
| Frontend | Vercel | Auto-deploy on push, SPA rewrites |
| Backend | Render | render.yaml, Python 3.9 |
| Source | GitHub | github.com/sheelendra-scripts/AQMS |

---

## Ward Coverage

12 MCD zones with distinct pollution profiles:

| Zone | Profile | Wards | PM2.5 Base |
|---|---|---|---|
| Central | vehicle | 15 | 160 |
| South | vehicle | 41 | 160 |
| Shahdara North | industrial | 27 | 220 |
| Shahdara South | mixed | 33 | 140 |
| City SP | mixed | 8 | 140 |
| Civil Lines | clean | 16 | 90 |
| Karol Bagh | vehicle | 18 | 160 |
| Najafgarh | biomass | 33 | 200 |
| Narela | biomass | 17 | 200 |
| Rohini | construction | 23 | 250 |
| West | construction | 14 | 250 |
| Keshavpuram | vehicle | 1 | 160 |

---

## Alert Rules

| Rule | Metric | Threshold | Severity |
|---|---|---|---|
| Severe AQI | AQI | > 400 | critical |
| Very Poor AQI | AQI | > 300 | critical |
| Poor AQI | AQI | > 200 | warning |
| Moderate AQI | AQI | > 150 | info |
| High PM2.5 | PM2.5 | > 120 ug/m3 | warning |
| Severe PM2.5 | PM2.5 | > 250 ug/m3 | critical |
| High CO | CO | > 6.0 ppm | critical |

---

## Documentation

- **Hardware Report:** [HARDWARE REPORT.pdf](HARDWARE%20REPORT.pdf) — Circuit design, sensor specs, ESP32 node, PCB layout
- **Hardware + Software Report:** [HARDWARE + SOFTWARE REPORT.pdf](HARDWARE%20+%20SOFTWARE%20REPORT.pdf) — Complete system documentation covering hardware, backend, ML models, frontend, and deployment
- **API Docs:** FastAPI auto-generated at `/docs` (Swagger UI)

---

## Team MechaMinds

Air Quality Monitoring & Management

---

*Built with ESP32, FastAPI, React, scikit-learn, XGBoost, Leaflet, and Recharts*
