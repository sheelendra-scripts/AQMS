import React, { useState, useEffect, useMemo } from 'react';
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import wardGeoJson from '../data/wards.json';

/* ── Force map resize when container size changes ──── */
function MapResizer() {
  const map = useMap();
  useEffect(() => {
    setTimeout(() => map.invalidateSize(), 100);
    const ro = new ResizeObserver(() => map.invalidateSize());
    const container = map.getContainer();
    ro.observe(container);
    return () => ro.disconnect();
  }, [map]);
  return null;
}

/* ── AQI color helpers ───────────────────── */
function getAqiColor(aqi) {
  if (aqi <= 50)  return '#22c55e';
  if (aqi <= 100) return '#84cc16';
  if (aqi <= 200) return '#eab308';
  if (aqi <= 300) return '#f97316';
  if (aqi <= 400) return '#ef4444';
  return '#991b1b';
}

function getAqiOpacity(aqi) {
  if (aqi <= 50) return 0.35;
  if (aqi <= 200) return 0.5;
  if (aqi <= 300) return 0.6;
  return 0.7;
}

/* ── Fly to ward on selection ──────────── */
function FlyToWard({ center }) {
  const map = useMap();
  useEffect(() => {
    if (center) map.flyTo(center, 14, { duration: 0.8 });
  }, [center, map]);
  return null;
}

/* ── Legend component ──────────────────── */
function MapLegend({ viewMode }) {
  const items = [
    { label: 'Good (0-50)', color: '#22c55e' },
    { label: 'Satisfactory (51-100)', color: '#84cc16' },
    { label: 'Moderate (101-200)', color: '#eab308' },
    { label: 'Poor (201-300)', color: '#f97316' },
    { label: 'Very Poor (301-400)', color: '#ef4444' },
    { label: 'Severe (401+)', color: '#991b1b' },
  ];

  return (
    <div className="map-legend">
      <div className="map-legend-title">AQI Scale</div>
      {items.map(({ label, color }) => (
        <div key={label} className="map-legend-item">
          <span className="map-legend-swatch" style={{ background: color }} />
          <span>{label}</span>
        </div>
      ))}
      <div style={{
        marginTop: 8, paddingTop: 6, borderTop: '1px solid rgba(0,0,0,0.08)',
        fontSize: '0.7rem', color: 'var(--earth-400)'
      }}>
        {viewMode === 'wards' ? '● Ward polygons' : '● Zone boundaries'}
      </div>
    </div>
  );
}

/* ── Split GeoJSON into zones & wards ─── */
const zoneGeoJson = {
  type: 'FeatureCollection',
  features: wardGeoJson.features.filter(f => f.properties.type === 'zone'),
};
const wardOnlyGeoJson = {
  type: 'FeatureCollection',
  features: wardGeoJson.features.filter(f => f.properties.type === 'ward'),
};

export default function WardMap({ wardData = [], selectedWard, onSelectWard, viewMode = 'wards' }) {
  const [flyCenter, setFlyCenter] = useState(null);

  // Build lookup: ward_id -> live data
  const wardLookup = useMemo(() => {
    const m = {};
    wardData.forEach(w => { m[w.ward_id] = w; });
    return m;
  }, [wardData]);

  // Compute zone-level aggregated AQI from ward readings
  const zoneAqiMap = useMemo(() => {
    const grouped = {};
    wardData.filter(w => w.feature_type === 'ward').forEach(w => {
      if (!grouped[w.zone]) grouped[w.zone] = [];
      grouped[w.zone].push(w.aqi);
    });
    const result = {};
    for (const [zone, aqis] of Object.entries(grouped)) {
      result[zone] = Math.round(aqis.reduce((a, b) => a + b, 0) / aqis.length);
    }
    return result;
  }, [wardData]);

  /* ── Style: Zones ──────────── */
  const getZoneStyle = (feature) => {
    const zoneName = feature.properties.zone;
    const aqi = zoneAqiMap[zoneName] || wardLookup[feature.properties.ward_id]?.aqi || 0;

    if (viewMode === 'wards') {
      // Zone outlines only when viewing wards
      return {
        fillColor: 'transparent',
        fillOpacity: 0,
        color: '#1e3a5f',
        weight: 2.5,
        dashArray: '6,4',
        opacity: 0.7,
      };
    }
    // Zone mode — filled
    const isSelected = feature.properties.ward_id === selectedWard;
    return {
      fillColor: getAqiColor(aqi),
      fillOpacity: isSelected ? 0.75 : getAqiOpacity(aqi),
      color: isSelected ? '#064e3b' : 'rgba(255,255,255,0.9)',
      weight: isSelected ? 3 : 2,
    };
  };

  /* ── Style: Wards ──────────── */
  const getWardStyle = (feature) => {
    const wd = wardLookup[feature.properties.ward_id];
    const aqi = wd?.aqi || 0;
    const isSelected = feature.properties.ward_id === selectedWard;
    return {
      fillColor: getAqiColor(aqi),
      fillOpacity: isSelected ? 0.8 : getAqiOpacity(aqi),
      color: isSelected ? '#064e3b' : 'rgba(255,255,255,0.65)',
      weight: isSelected ? 2.5 : 0.8,
    };
  };

  /* ── Zone interactions ─────── */
  const onEachZone = (feature, layer) => {
    const props = feature.properties;
    const zoneName = props.zone;
    const aqi = zoneAqiMap[zoneName] || wardLookup[props.ward_id]?.aqi || 0;

    layer.on({
      mouseover: (e) => {
        if (viewMode === 'zones') {
          e.target.setStyle({ weight: 3, color: '#064e3b', fillOpacity: 0.7 });
          e.target.bringToFront();
        }
      },
      mouseout: (e) => {
        if (viewMode === 'zones' && props.ward_id !== selectedWard) {
          e.target.setStyle(getZoneStyle(feature));
        }
      },
      click: () => {
        if (viewMode === 'zones') {
          onSelectWard?.(props.ward_id);
          const coords = feature.geometry.coordinates[0];
          const lat = coords.reduce((s, c) => s + c[1], 0) / coords.length;
          const lng = coords.reduce((s, c) => s + c[0], 0) / coords.length;
          setFlyCenter([lat, lng]);
        }
      },
    });

    if (aqi > 0) {
      const wardCount = props.ward_count || 0;
      layer.bindTooltip(
        `<div style="font-weight:700;font-size:13px">${props.name}</div>
         <div style="font-size:12px;color:#555">Avg AQI: <b style="color:${getAqiColor(aqi)}">${aqi}</b></div>
         <div style="font-size:11px;color:#888">${wardCount} wards</div>`,
        { sticky: true, className: 'ward-tooltip' }
      );
    }
  };

  /* ── Ward interactions ─────── */
  const onEachWard = (feature, layer) => {
    const props = feature.properties;
    const wd = wardLookup[props.ward_id];

    layer.on({
      mouseover: (e) => {
        e.target.setStyle({ weight: 2, color: '#064e3b', fillOpacity: 0.75 });
        e.target.bringToFront();
      },
      mouseout: (e) => {
        if (props.ward_id !== selectedWard) {
          e.target.setStyle(getWardStyle(feature));
        }
      },
      click: () => {
        onSelectWard?.(props.ward_id);
        const coords = feature.geometry.coordinates[0];
        const lat = coords.reduce((s, c) => s + c[1], 0) / coords.length;
        const lng = coords.reduce((s, c) => s + c[0], 0) / coords.length;
        setFlyCenter([lat, lng]);
      },
    });

    if (wd) {
      layer.bindTooltip(
        `<div style="font-weight:600;font-size:13px">${props.name}</div>
         <div style="font-size:11px;color:#888">${props.zone} Zone</div>
         <div style="font-size:12px;color:#555">AQI: <b style="color:${getAqiColor(wd.aqi)}">${wd.aqi}</b> · ${wd.aqi_category}</div>`,
        { sticky: true, className: 'ward-tooltip' }
      );
    }
  };

  // Rekey when live data or view changes
  const dataKey = useMemo(
    () => viewMode + '-' + wardData.map(w => w.aqi).join(','),
    [viewMode, wardData]
  );

  const center = [28.65, 77.15];

  return (
    <div className="ward-map-wrapper">
      <MapContainer
        center={center}
        zoom={10}
        scrollWheelZoom={true}
        zoomControl={false}
        className="ward-map"
        style={{ height: '100%', width: '100%', borderRadius: 'var(--radius-lg)', minHeight: 'inherit' }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org">OSM</a> &copy; <a href="https://carto.com">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
        />

        {/* Zone layer — always rendered (outlines in ward mode, filled in zone mode) */}
        <GeoJSON
          key={'zones-' + dataKey}
          data={zoneGeoJson}
          style={getZoneStyle}
          onEachFeature={onEachZone}
        />

        {/* Ward layer — only in ward view */}
        {viewMode === 'wards' && (
          <GeoJSON
            key={'wards-' + dataKey}
            data={wardOnlyGeoJson}
            style={getWardStyle}
            onEachFeature={onEachWard}
          />
        )}

        <FlyToWard center={flyCenter} />
        <MapResizer />
      </MapContainer>
      <MapLegend viewMode={viewMode} />
    </div>
  );
}
