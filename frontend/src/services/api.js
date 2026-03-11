/* API service for AQMS backend */
import axios from 'axios';

// Auto-detect: use VITE_API_URL env var, or fallback to localhost for dev
const API_BASE = import.meta.env.VITE_API_URL
  || (window.location.hostname === 'localhost' ? 'http://localhost:8000' : 'https://aqms-backend-ue5x.onrender.com');
const THINGSPEAK_CHANNEL = '2697383';
const THINGSPEAK_API_KEY = 'RAYZJW1K4FBNIVP6';
const THINGSPEAK_BASE = `https://api.thingspeak.com/channels/${THINGSPEAK_CHANNEL}`;

const api = axios.create({
  baseURL: API_BASE,
  timeout: 15000,
});

// ─── Backend API (when running) ───────────────────────
export const fetchLiveData = () => api.get('/api/live').then(r => r.data);
export const fetchHistory = (hours = 24) => api.get(`/api/history?hours=${hours}`).then(r => r.data);
export const fetchAdvisory = () => api.get('/api/advisory').then(r => r.data);
export const fetchPolicy = (source, aqi) =>
  api.get('/api/policy', { params: { source, aqi } }).then(r => r.data);
export const fetchHealth = () => api.get('/api/health').then(r => r.data);
export const fetchWards = () => api.get('/api/wards').then(r => r.data);
export const fetchWard = (wardId) => api.get(`/api/wards/${wardId}`).then(r => r.data);

// ─── Alerts API ─────────────────────────────────────
export const fetchAlerts      = (limit = 50)         => api.get(`/api/alerts?limit=${limit}`).then(r => r.data);
export const fetchAlertStats  = ()                   => api.get('/api/alerts/stats').then(r => r.data);
export const fetchAlertRules  = ()                   => api.get('/api/alerts/rules').then(r => r.data);
export const createAlertRule  = (rule)               => api.post('/api/alerts/rules', rule).then(r => r.data);
export const updateAlertRule  = (id, updates)        => api.put(`/api/alerts/rules/${id}`, updates).then(r => r.data);
export const deleteAlertRule  = (id)                 => api.delete(`/api/alerts/rules/${id}`).then(r => r.data);
export const clearAlerts      = ()                   => api.delete('/api/alerts').then(r => r.data);

// ─── ML Predictions API ──────────────────────────────// Client-side rule-based source detection fallback
export function detectSourceLocal(pm25, co, no2, tvoc) {
  const pmCo = pm25 / Math.max(co, 0.01);
  const scores = { vehicle: 0, industrial: 0, construction: 0, biomass: 0, mixed: 0.05 };

  // Vehicle
  if (pmCo > 30 && no2 > 0.08) scores.vehicle += 0.45;
  if (pmCo > 20) scores.vehicle += 0.15;
  if (co > 2.0 && co <= 5.0) scores.vehicle += 0.10;

  // Industrial
  if (no2 > 0.15 && co > 4.0) scores.industrial += 0.45;
  if (no2 > 0.10) scores.industrial += 0.15;
  if (tvoc > 0.5 && no2 > 0.12) scores.industrial += 0.10;

  // Biomass
  if (co > 5.0 && tvoc > 0.8) scores.biomass += 0.45;
  if (co > 4.0) scores.biomass += 0.10;
  if (tvoc > 0.6) scores.biomass += 0.10;

  // Construction
  if (tvoc > 1.0 && pm25 > 180) scores.construction += 0.45;
  if (pm25 > 150) scores.construction += 0.10;
  if (tvoc > 0.8) scores.construction += 0.05;

  const total = Object.values(scores).reduce((s, v) => s + v, 0) || 1;
  const probabilities = {};
  for (const k of Object.keys(scores)) probabilities[k] = Math.round((scores[k] / total) * 1000) / 1000;

  const src = Object.entries(probabilities).sort((a, b) => b[1] - a[1])[0][0];
  return { source: src, confidence: probabilities[src], probabilities };
}
export const fetchMLSource = () => api.get('/api/ml/source').then(r => r.data);
export const fetchMLForecast = (horizon = 24) => api.get(`/api/ml/forecast?horizon=${horizon}`).then(r => r.data);
export const fetchMLAnomaly = () => api.get('/api/ml/anomaly').then(r => r.data);
export const fetchMLSummary = () => api.get('/api/ml/summary').then(r => r.data);

// ─── Direct ThingSpeak fallback (works without backend) ─
function safeFloat(val) { return val ? parseFloat(val) || 0 : 0; }
function safeInt(val) { return val ? parseInt(val, 10) || 0 : 0; }

// CPCB AQI helper
function getAqiCategory(aqi) {
  if (aqi <= 50)  return { category: 'Good', color: '#22c55e' };
  if (aqi <= 100) return { category: 'Satisfactory', color: '#a3e635' };
  if (aqi <= 200) return { category: 'Moderate', color: '#facc15' };
  if (aqi <= 300) return { category: 'Poor', color: '#f97316' };
  if (aqi <= 400) return { category: 'Very Poor', color: '#ef4444' };
  return { category: 'Severe', color: '#991b1b' };
}

function parseThingSpeakFeed(feed) {
  const pm25 = safeFloat(feed.field3);
  const tvoc = safeFloat(feed.field4);
  const no2 = safeFloat(feed.field5);
  const co = safeFloat(feed.field6);
  const aqi = safeInt(feed.field7);
  const cat = getAqiCategory(aqi);
  const src = detectSourceLocal(pm25, co, no2, tvoc);
  return {
    timestamp: feed.created_at,
    temperature: safeFloat(feed.field1),
    humidity: safeFloat(feed.field2),
    pm25, tvoc, no2, co,
    aqi,
    aqi_category: cat.category,
    aqi_color: cat.color,
    source_detected: src.source,
    status: 'online',
  };
}

export async function fetchThingSpeakLive() {
  const resp = await axios.get(`${THINGSPEAK_BASE}/feeds/last.json`, { params: { api_key: THINGSPEAK_API_KEY } });
  return parseThingSpeakFeed(resp.data);
}

export async function fetchThingSpeakHistory(results = 100) {
  const resp = await axios.get(`${THINGSPEAK_BASE}/feeds.json`, { params: { api_key: THINGSPEAK_API_KEY, results } });
  const feeds = resp.data.feeds || [];
  return feeds.filter(f => f.created_at).map(parseThingSpeakFeed);
}

// ─── Smart fetcher: tries backend first, falls back to ThingSpeak ─
export async function getLiveData() {
  try {
    const data = await fetchLiveData();
    if (data.status !== 'offline') return data;
  } catch {
    // Backend not available
  }
  try {
    return await fetchThingSpeakLive();
  } catch {
    return null;
  }
}

export async function getHistoryData(results = 200) {
  try {
    const data = await fetchHistory(24);
    if (data.data && data.data.length > 0) return data.data;
  } catch {
    // Backend not available
  }
  try {
    return await fetchThingSpeakHistory(results);
  } catch {
    return [];
  }
}

// ─── WebSocket ────────────────────────────────────────
export function createWebSocket(onMessage) {
  const wsUrl = API_BASE.replace('http', 'ws') + '/ws/live';
  let ws;
  let reconnectTimer;

  function connect() {
    ws = new WebSocket(wsUrl);
    ws.onopen = () => console.log('🌿 WebSocket connected');
    ws.onmessage = (e) => {
      try { onMessage(JSON.parse(e.data)); } catch {}
    };
    ws.onclose = () => {
      console.log('WebSocket closed, reconnecting in 5s...');
      reconnectTimer = setTimeout(connect, 5000);
    };
    ws.onerror = () => ws.close();
  }

  connect();
  return () => {
    clearTimeout(reconnectTimer);
    ws?.close();
  };
}

export default api;
