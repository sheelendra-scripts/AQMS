import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Clock, MapPin, Wifi, RefreshCw, Brain, TrendingUp } from 'lucide-react';
import AQIGauge from '../components/AQIGauge';
import MetricsGrid from '../components/MetricsGrid';
import TimeSeriesChart from '../components/TimeSeriesChart';
import HealthAdvisory from '../components/HealthAdvisory';
import { useLiveData, useHistoryData, useTimeAgo } from '../hooks/useData';
import { fetchMLSource, fetchMLForecast, detectSourceLocal } from '../services/api';

const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  show: (i) => ({
    opacity: 1, y: 0,
    transition: { delay: i * 0.1, duration: 0.5, ease: [0.4, 0, 0.2, 1] }
  }),
};

const LOADING_STEPS = [
  { key: 'init', label: 'Initializing system...', pct: 10 },
  { key: 'connecting', label: 'Connecting to sensor network...', pct: 30 },
  { key: 'fetching', label: 'Fetching live readings...', pct: 60 },
  { key: 'processing', label: 'Processing AQI data...', pct: 85 },
  { key: 'done', label: 'Ready', pct: 100 },
];

function LoadingScreen({ step }) {
  const current = LOADING_STEPS.find(s => s.key === step) || LOADING_STEPS[0];
  return (
    <div className="loading-screen" style={{ position: 'relative', minHeight: '60vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 20 }}>
      <div className="loading-spinner" />
      <div style={{ textAlign: 'center' }}>
        <div className="loading-text" style={{ marginBottom: 12 }}>{current.label}</div>
        <div style={{ width: 220, height: 6, background: 'var(--earth-100)', borderRadius: 3, overflow: 'hidden', margin: '0 auto' }}>
          <div style={{
            width: `${current.pct}%`, height: '100%',
            background: 'linear-gradient(90deg, #10b981, #059669)',
            borderRadius: 3, transition: 'width 0.6s ease',
          }} />
        </div>
        <div style={{ fontSize: '0.7rem', color: 'var(--earth-400)', marginTop: 8 }}>
          Polling ThingSpeak IoT Cloud + ML Pipeline
        </div>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { data, loading, loadingStep, refetch } = useLiveData();
  const { data: history, loading: historyLoading } = useHistoryData(300);
  const timeAgo = useTimeAgo(data?.timestamp);
  const [mlSource, setMlSource] = useState(null);
  const [mlForecast, setMlForecast] = useState(null);

  // Pre-seed ML source from live data or run client-side detection
  useEffect(() => {
    if (data && !mlSource) {
      if (data.source_detected && data.source_detected !== 'unknown') {
        // Use source with client-side probabilities
        const local = detectSourceLocal(data.pm25 || 0, data.co || 0, data.no2 || 0, data.tvoc || 0);
        setMlSource(local);
      } else {
        setMlSource(detectSourceLocal(data.pm25 || 0, data.co || 0, data.no2 || 0, data.tvoc || 0));
      }
    }
  }, [data]);

  useEffect(() => {
    if (!data) return;
    const fetchSource = () => {
      fetchMLSource()
        .then(res => {
          if (res && res.source && !res.error) setMlSource(res);
          else if (data) setMlSource(detectSourceLocal(data.pm25 || 0, data.co || 0, data.no2 || 0, data.tvoc || 0));
        })
        .catch(() => {
          if (data) setMlSource(detectSourceLocal(data.pm25 || 0, data.co || 0, data.no2 || 0, data.tvoc || 0));
        });
    };
    fetchSource();
    fetchMLForecast(6).then(setMlForecast).catch(() => {});
    const iv = setInterval(() => {
      fetchSource();
      fetchMLForecast(6).then(setMlForecast).catch(() => {});
    }, 60000);
    return () => clearInterval(iv);
  }, [data]);

  if (loading && !data) {
    return <LoadingScreen step={loadingStep} />;
  }

  return (
    <div className="dashboard-grid">
      {/* Page Header */}
      <motion.div
        className="page-header"
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h2>Air Quality Dashboard</h2>
            <p>Real-time monitoring from your IoT sensor network</p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            {data && (
              <div className="last-updated">
                <span className="dot" />
                <Clock size={12} />
                <span>Updated {timeAgo}</span>
              </div>
            )}
            <button
              onClick={refetch}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '8px 16px', borderRadius: 'var(--radius-sm)',
                border: '1px solid rgba(16,185,129,0.2)',
                background: 'rgba(16,185,129,0.05)',
                color: 'var(--forest-700)', fontSize: '0.82rem',
                fontWeight: 500, cursor: 'pointer',
                transition: 'all 0.2s',
              }}
            >
              <RefreshCw size={14} />
              Refresh
            </button>
          </div>
        </div>
      </motion.div>

      {/* Top section: AQI Gauge + Metrics */}
      <div className="dashboard-top">
        <motion.div
          className="glass-card"
          style={{ padding: 0, overflow: 'hidden' }}
          custom={0}
          variants={fadeUp}
          initial="hidden"
          animate="show"
        >
          {data && (
            <>
              <AQIGauge aqi={data.aqi} category={data.aqi_category} color={data.aqi_color} />
              <div style={{
                padding: '12px 24px 20px',
                display: 'flex', justifyContent: 'center',
                alignItems: 'center', gap: 6,
                fontSize: '0.78rem', color: 'var(--earth-400)'
              }}>
                <MapPin size={12} />
                <span>Ward 01 — Sensor Node</span>
                <span style={{ margin: '0 4px' }}>·</span>
                <Wifi size={12} />
                <span>ThingSpeak Live</span>
              </div>
            </>
          )}
        </motion.div>

        <motion.div custom={1} variants={fadeUp} initial="hidden" animate="show">
          <MetricsGrid data={data} />
        </motion.div>
      </div>

      {/* Chart */}
      <motion.div custom={2} variants={fadeUp} initial="hidden" animate="show">
        <TimeSeriesChart data={history} title="Real-time Pollutant Trends" />
      </motion.div>

      {/* Bottom section: Advisory + Source detection placeholder */}
      <div className="dashboard-bottom">
        <motion.div custom={3} variants={fadeUp} initial="hidden" animate="show">
          {data && <HealthAdvisory aqi={data.aqi} source={data.source_detected} />}
        </motion.div>

        <motion.div custom={4} variants={fadeUp} initial="hidden" animate="show">
          <div className="glass-card" style={{ height: '100%' }}>
            <div className="section-title"><Brain size={16} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 6 }} />ML Source Detection</div>
            {mlSource && mlSource.source ? (() => {
              const SOURCE_META = {
                vehicle:      { icon: '🚗', label: 'Vehicle Emissions', color: '#f97316' },
                industrial:   { icon: '🏭', label: 'Industrial Activity', color: '#ef4444' },
                construction: { icon: '🏗️', label: 'Construction Dust', color: '#eab308' },
                biomass:      { icon: '🔥', label: 'Biomass Burning', color: '#a855f7' },
                mixed:        { icon: '🌫️', label: 'Mixed Sources', color: '#6366f1' },
                unknown:      { icon: '❓', label: 'Unknown', color: '#78716c' },
              };
              const m = SOURCE_META[mlSource.source] || SOURCE_META.unknown;
              const probs = mlSource.probabilities || {};
              const sorted = Object.entries(probs).sort((a, b) => b[1] - a[1]).slice(0, 3);
              return (
                <div style={{ padding: '8px 0' }}>
                  <div style={{
                    display: 'flex', alignItems: 'center', gap: 12, padding: '14px 16px',
                    background: `${m.color}08`, borderRadius: 14, border: `1.5px solid ${m.color}20`, marginBottom: 14,
                  }}>
                    <span style={{ fontSize: '2rem' }}>{m.icon}</span>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '1.05rem', color: m.color }}>{m.label}</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--earth-400)' }}>Confidence: {((mlSource.confidence || 0) * 100).toFixed(0)}%</div>
                    </div>
                  </div>
                  {sorted.map(([src, prob]) => {
                    const sm = SOURCE_META[src] || SOURCE_META.unknown;
                    return (
                      <div key={src} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                        <span style={{ fontSize: '0.85rem', width: 20, textAlign: 'center' }}>{sm.icon}</span>
                        <span style={{ fontSize: '0.75rem', color: 'var(--earth-600)', width: 80 }}>{src}</span>
                        <div style={{ flex: 1, height: 6, background: 'var(--earth-100)', borderRadius: 3, overflow: 'hidden' }}>
                          <div style={{ width: `${prob * 100}%`, height: '100%', background: sm.color, borderRadius: 3 }} />
                        </div>
                        <span style={{ fontSize: '0.72rem', fontWeight: 600, width: 38, textAlign: 'right' }}>{(prob * 100).toFixed(0)}%</span>
                      </div>
                    );
                  })}
                  {mlForecast && mlForecast.forecasts && (
                    <div style={{ marginTop: 14, padding: '10px 12px', background: 'var(--earth-50)', borderRadius: 10 }}>
                      <div style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--earth-500)', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 4 }}>
                        <TrendingUp size={12} /> 6h Forecast Preview
                      </div>
                      <div style={{ display: 'flex', gap: 4, justifyContent: 'space-between' }}>
                        {mlForecast.forecasts.slice(0, 6).map(f => (
                          <div key={f.hour_offset} style={{ textAlign: 'center', flex: 1 }}>
                            <div style={{ fontSize: '0.65rem', color: 'var(--earth-400)' }}>+{f.hour_offset}h</div>
                            <div style={{
                              fontFamily: 'var(--font-display)', fontSize: '0.85rem', fontWeight: 700, color: f.color,
                            }}>{f.predicted_aqi}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })() : (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 180, color: 'var(--earth-400)', fontSize: '0.85rem' }}>
                Loading ML analysis...
              </div>
            )}
          </div>
        </motion.div>
      </div>
    </div>
  );
}
