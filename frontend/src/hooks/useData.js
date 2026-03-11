import { useState, useEffect, useRef, useCallback } from 'react';
import { getLiveData, getHistoryData, createWebSocket } from '../services/api';

/**
 * Hook: useLiveData
 * Fetches live sensor data — tries WebSocket first, then polls every 30s
 */
export function useLiveData() {
  const [data, setData] = useState(() => {
    // Restore cached data from sessionStorage for instant display
    try {
      const cached = sessionStorage.getItem('aqms_last_reading');
      return cached ? JSON.parse(cached) : null;
    } catch { return null; }
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [loadingStep, setLoadingStep] = useState('init');
  const dataRef = useRef(null);
  dataRef.current = data;

  const fetchData = useCallback(async () => {
    try {
      setLoadingStep('fetching');
      const result = await getLiveData();
      if (result) {
        setData(result);
        setError(null);
        // Cache for instant restore on next visit
        try { sessionStorage.setItem('aqms_last_reading', JSON.stringify(result)); } catch {}
      }
      // If result is null, keep previous data (don't reset to null)
    } catch (e) {
      setError(e.message);
      // Keep previous data on error — never flash zero
    } finally {
      setLoading(false);
      setLoadingStep('done');
    }
  }, []);

  useEffect(() => {
    setLoadingStep('connecting');
    fetchData();

    // Try WebSocket
    let cleanup;
    try {
      cleanup = createWebSocket((wsData) => {
        if (wsData && wsData.aqi != null) {
          setData(wsData);
          setLoading(false);
          setError(null);
          try { sessionStorage.setItem('aqms_last_reading', JSON.stringify(wsData)); } catch {}
        }
      });
    } catch {
      // WebSocket not available, use polling
    }

    // Fallback polling every 30s
    const interval = setInterval(fetchData, 30000);

    return () => {
      cleanup?.();
      clearInterval(interval);
    };
  }, [fetchData]);

  return { data, loading, error, loadingStep, refetch: fetchData };
}

/**
 * Hook: useHistoryData
 * Fetches historical data (last N entries)
 */
export function useHistoryData(results = 200) {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetch() {
      try {
        const history = await getHistoryData(results);
        setData(history);
      } catch {
        setData([]);
      } finally {
        setLoading(false);
      }
    }
    fetch();
    const interval = setInterval(fetch, 60000); // Refresh history every minute
    return () => clearInterval(interval);
  }, [results]);

  return { data, loading };
}

/**
 * Hook: useTimeAgo
 * Returns a human-readable "X seconds ago" string that updates in real time
 */
export function useTimeAgo(timestamp) {
  const [timeAgo, setTimeAgo] = useState('');

  useEffect(() => {
    if (!timestamp) return;

    function update() {
      const now = new Date();
      const then = new Date(timestamp);
      const seconds = Math.floor((now - then) / 1000);

      if (seconds < 10) setTimeAgo('just now');
      else if (seconds < 60) setTimeAgo(`${seconds}s ago`);
      else if (seconds < 3600) setTimeAgo(`${Math.floor(seconds / 60)}m ago`);
      else if (seconds < 86400) setTimeAgo(`${Math.floor(seconds / 3600)}h ago`);
      else setTimeAgo(`${Math.floor(seconds / 86400)}d ago`);
    }

    update();
    const interval = setInterval(update, 5000);
    return () => clearInterval(interval);
  }, [timestamp]);

  return timeAgo;
}
