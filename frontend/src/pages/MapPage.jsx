import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  MapPin, RefreshCw, Wind, Flame, CloudRain, Thermometer,
  Droplets, Atom, ChevronRight, X, Layers, Search, Grid3X3, Map as MapIcon
} from 'lucide-react';
import WardMap from '../components/WardMap';
import { fetchWards } from '../services/api';

const SOURCE_ICONS = {
  vehicle: '🚗',
  industrial: '🏭',
  construction: '🏗️',
  biomass: '🔥',
};

function WardDetailPanel({ ward, onClose }) {
  if (!ward) return null;

  const metrics = [
    { label: 'PM 2.5', value: ward.pm25, unit: 'µg/m³', icon: Wind, color: '#f97316' },
    { label: 'CO', value: ward.co, unit: 'ppm', icon: Flame, color: '#8b5cf6' },
    { label: 'NO₂', value: ward.no2, unit: 'ppm', icon: CloudRain, color: '#0ea5e9' },
    { label: 'TVOC', value: ward.tvoc, unit: 'ppm', icon: Atom, color: '#eab308' },
    { label: 'Temp', value: ward.temperature, unit: '°C', icon: Thermometer, color: '#ef4444' },
    { label: 'Humidity', value: ward.humidity, unit: '%', icon: Droplets, color: '#38bdf8' },
  ];

  return (
    <motion.div
      className="ward-detail-panel"
      initial={{ x: 320, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 320, opacity: 0 }}
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
    >
      <div className="ward-detail-header">
        <div>
          <h3>{ward.name}</h3>
          <span className="ward-zone-badge">{ward.zone}</span>
        </div>
        <button className="ward-detail-close" onClick={onClose}>
          <X size={18} />
        </button>
      </div>

      <div className="ward-aqi-hero" style={{ '--aqi-color': ward.aqi_color }}>
        <div className="ward-aqi-value">{ward.aqi}</div>
        <div className="ward-aqi-label">AQI</div>
        <div
          className="ward-aqi-badge"
          style={{ background: `${ward.aqi_color}20`, color: ward.aqi_color, border: `1px solid ${ward.aqi_color}40` }}
        >
          {ward.aqi_category}
        </div>
      </div>

      {ward.source_detected && (
        <div className="ward-source-badge">
          <span style={{ fontSize: '1.2rem' }}>{SOURCE_ICONS[ward.source_detected] || '❓'}</span>
          <div>
            <div style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--earth-800)' }}>
              {ward.source_detected.charAt(0).toUpperCase() + ward.source_detected.slice(1)} Source Detected
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--earth-400)' }}>
              Confidence: {Math.round((ward.source_confidence || 0) * 100)}%
            </div>
          </div>
        </div>
      )}

      <div className="ward-metrics-mini">
        {metrics.map(({ label, value, unit, icon: Icon, color }) => (
          <div key={label} className="ward-metric-item">
            <Icon size={14} style={{ color }} />
            <div>
              <div className="ward-metric-val">{typeof value === 'number' ? value.toFixed(1) : '—'}</div>
              <div className="ward-metric-label">{label} <span>{unit}</span></div>
            </div>
          </div>
        ))}
      </div>
    </motion.div>
  );
}

function WardListItem({ ward, isSelected, onClick }) {
  return (
    <button
      className={`ward-list-item ${isSelected ? 'active' : ''}`}
      onClick={onClick}
    >
      <div
        className="ward-list-aqi"
        style={{ background: `${ward.aqi_color}20`, color: ward.aqi_color }}
      >
        {ward.aqi}
      </div>
      <div className="ward-list-info">
        <div className="ward-list-name">{ward.name}</div>
        <div className="ward-list-zone">{ward.zone} · {ward.aqi_category}</div>
      </div>
      <ChevronRight size={14} style={{ color: 'var(--earth-300)', flexShrink: 0 }} />
    </button>
  );
}

export default function MapPage() {
  const [wards, setWards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedWard, setSelectedWard] = useState(null);
  const [showList, setShowList] = useState(true);
  const [viewMode, setViewMode] = useState('wards'); // 'zones' | 'wards'
  const [searchQuery, setSearchQuery] = useState('');

  const loadWards = useCallback(async () => {
    try {
      const res = await fetchWards();
      setWards(res.wards || []);
    } catch {
      setWards([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadWards();
    const interval = setInterval(loadWards, 30000);
    return () => clearInterval(interval);
  }, [loadWards]);

  // Split data into zones and wards
  const zoneData = useMemo(() => wards.filter(w => w.feature_type === 'zone'), [wards]);
  const wardOnlyData = useMemo(() => wards.filter(w => w.feature_type === 'ward'), [wards]);

  // Currently visible list items
  const listItems = useMemo(() => {
    const items = viewMode === 'zones' ? zoneData : wardOnlyData;
    const filtered = searchQuery
      ? items.filter(w =>
          w.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          w.zone.toLowerCase().includes(searchQuery.toLowerCase())
        )
      : items;
    return [...filtered].sort((a, b) => b.aqi - a.aqi);
  }, [viewMode, zoneData, wardOnlyData, searchQuery]);

  const selectedWardData = wards.find(w => w.ward_id === selectedWard);

  // City-wide averages (from wards only)
  const cityAqi = wardOnlyData.length
    ? Math.round(wardOnlyData.reduce((s, w) => s + w.aqi, 0) / wardOnlyData.length)
    : 0;

  return (
    <div className="map-page">
      {/* Header */}
      <motion.div
        className="page-header"
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        style={{ position: 'relative', zIndex: 10 }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h2>Ward-Wise AQI Map</h2>
            <p>Interactive heatmap — {wardOnlyData.length} wards across {zoneData.length} MCD zones</p>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {/* View mode toggle */}
            <div className="map-view-toggle">
              <button
                className={`map-toggle-btn ${viewMode === 'zones' ? 'active' : ''}`}
                onClick={() => { setViewMode('zones'); setSelectedWard(null); }}
              >
                <Grid3X3 size={13} /> Zones
              </button>
              <button
                className={`map-toggle-btn ${viewMode === 'wards' ? 'active' : ''}`}
                onClick={() => { setViewMode('wards'); setSelectedWard(null); }}
              >
                <MapIcon size={13} /> Wards
              </button>
            </div>
            <button className="map-btn" onClick={() => setShowList(!showList)}>
              <Layers size={14} />
              {showList ? 'Hide' : 'List'}
            </button>
            <button className="map-btn" onClick={loadWards}>
              <RefreshCw size={14} />
            </button>
          </div>
        </div>

        {/* City summary bar */}
        {wardOnlyData.length > 0 && (
          <div className="city-summary-bar">
            <div className="city-aqi">
              <span className="city-aqi-dot" style={{ background: getAqiColor(cityAqi) }} />
              City Avg AQI: <strong>{cityAqi}</strong>
            </div>
            <div className="city-stats">
              <span>🟢 {wardOnlyData.filter(w => w.aqi <= 100).length} Good</span>
              <span>🟡 {wardOnlyData.filter(w => w.aqi > 100 && w.aqi <= 200).length} Moderate</span>
              <span>🔴 {wardOnlyData.filter(w => w.aqi > 200).length} Poor+</span>
            </div>
            <div className="city-wards-count">
              <MapPin size={12} /> {wardOnlyData.length} Wards · {zoneData.length} Zones
            </div>
          </div>
        )}
      </motion.div>

      {/* Main map area */}
      <div className="map-layout">
        {/* Sidebar */}
        <AnimatePresence>
          {showList && (
            <motion.div
              className="ward-list-panel"
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 300, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ duration: 0.3 }}
            >
              <div className="ward-list-header">
                <span>{viewMode === 'zones' ? 'Zones' : 'All Wards'} ({listItems.length})</span>
                <span style={{ fontSize: '0.7rem', color: 'var(--earth-400)' }}>by AQI ↓</span>
              </div>

              {/* Search */}
              {viewMode === 'wards' && (
                <div className="ward-search-box">
                  <Search size={14} style={{ color: 'var(--earth-400)', flexShrink: 0 }} />
                  <input
                    type="text"
                    placeholder="Search ward or zone..."
                    value={searchQuery}
                    onChange={e => setSearchQuery(e.target.value)}
                  />
                </div>
              )}

              <div className="ward-list-scroll">
                {loading ? (
                  <div style={{ padding: 32, textAlign: 'center', color: 'var(--earth-400)' }}>
                    Loading...
                  </div>
                ) : listItems.length === 0 ? (
                  <div style={{ padding: 32, textAlign: 'center', color: 'var(--earth-400)', fontSize: '0.85rem' }}>
                    No results
                  </div>
                ) : (
                  listItems.map(ward => (
                    <WardListItem
                      key={ward.ward_id}
                      ward={ward}
                      isSelected={ward.ward_id === selectedWard}
                      onClick={() => setSelectedWard(
                        ward.ward_id === selectedWard ? null : ward.ward_id
                      )}
                    />
                  ))
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Map */}
        <div className="map-container-wrapper">
          {loading ? (
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              height: '100%', color: 'var(--earth-400)'
            }}>
              <div className="loading-spinner" style={{ width: 32, height: 32 }} />
            </div>
          ) : (
            <WardMap
              wardData={wards}
              selectedWard={selectedWard}
              onSelectWard={setSelectedWard}
              viewMode={viewMode}
            />
          )}

          <AnimatePresence>
            {selectedWardData && (
              <WardDetailPanel
                ward={selectedWardData}
                onClose={() => setSelectedWard(null)}
              />
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}

function getAqiColor(aqi) {
  if (aqi <= 50) return '#22c55e';
  if (aqi <= 100) return '#84cc16';
  if (aqi <= 200) return '#eab308';
  if (aqi <= 300) return '#f97316';
  if (aqi <= 400) return '#ef4444';
  return '#991b1b';
}
