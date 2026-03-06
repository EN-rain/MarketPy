'use client';

import { useState, useEffect, useSyncExternalStore, useCallback } from 'react';
import { Database, Wifi, WifiOff, Loader2 } from 'lucide-react';
import { postApi } from '@/hooks/useApi';
import { getApiUrl } from '@/lib/apiRuntime';
import styles from './DevModeToggle.module.css';

let globalMockMode = true;
let globalStreamRunning = false;
const listeners = new Set<(isMock: boolean) => void>();
const streamListeners = new Set<(isRunning: boolean) => void>();

function emitChange(isMock: boolean) {
  globalMockMode = isMock;
  listeners.forEach((listener) => listener(isMock));
}

function emitStreamChange(isRunning: boolean) {
  globalStreamRunning = isRunning;
  streamListeners.forEach((listener) => listener(isRunning));
}

export function subscribeToMockMode(listener: (isMock: boolean) => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function subscribeToStream(listener: (isRunning: boolean) => void) {
  streamListeners.add(listener);
  return () => streamListeners.delete(listener);
}

export function getMockMode() {
  return globalMockMode;
}

export function getStreamStatus() {
  return globalStreamRunning;
}

export function setMockMode(isMock: boolean) {
  if (typeof window !== 'undefined') {
    localStorage.setItem('marketpy_mock_mode', isMock ? 'true' : 'false');
  }

  emitChange(isMock);
}

export function useMockMode() {
  return useSyncExternalStore(subscribeToMockMode, () => globalMockMode, () => true);
}

export function useStreamStatus() {
  return useSyncExternalStore(subscribeToStream, () => globalStreamRunning, () => false);
}

export default function DevModeToggle() {
  const isMockMode = useMockMode();
  const isStreamRunning = useStreamStatus();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const checkStreamStatus = useCallback(async () => {
    try {
      const response = await fetch(getApiUrl('/markets/status'));
      if (!response.ok) {
        return;
      }

      const data = await response.json();
      emitStreamChange(Boolean(data.is_running));
    } catch {
      emitStreamChange(false);
    }
  }, []);

  useEffect(() => {
    const saved = localStorage.getItem('marketpy_mock_mode');
    if (saved !== null) {
      const isMock = saved === 'true';
      if (isMock !== globalMockMode) {
        emitChange(isMock);
      }
    }

    void checkStreamStatus();
  }, [checkStreamStatus]);

  const toggle = async () => {
    const nextModeIsMock = !isMockMode;
    setIsLoading(true);
    setError(null);

    try {
      if (!nextModeIsMock) {
        setMockMode(false);
        await postApi('/markets/start-stream', [
          'btcusdt',
          'ethusdt',
          'solusdt',
          'adausdt',
          'dotusdt',
          'linkusdt',
          'maticusdt',
          'avaxusdt',
        ]);
        emitStreamChange(true);
      } else {
        await postApi('/markets/stop-stream', {});
        emitStreamChange(false);
        setMockMode(true);
      }
    } catch (nextError: unknown) {
      const message =
        nextError instanceof Error
          ? nextError.message
          : 'Failed to change data source. Confirm the backend is reachable.';
      setError(message);
      setMockMode(isMockMode);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className={styles.wrapper}>
      <div className={styles.header}>
        <Database className={styles.icon} />
        <span>Data Source</span>
      </div>

      {error ? <div className={styles.error}>{error}</div> : null}

      <div className={styles.toggleContainer}>
        <div className={styles.toggleWrapper}>
          <input
            type="checkbox"
            id="data-mode-toggle"
            className={styles.toggleInput}
            checked={!isMockMode}
            onChange={toggle}
            disabled={isLoading}
          />
          <label htmlFor="data-mode-toggle" className={styles.toggleLabel}>
            {isLoading ? (
              <span className={styles.spinner}>
                <Loader2 size={14} />
              </span>
            ) : (
              <span className={styles.toggleKnob} />
            )}
          </label>
        </div>

        <div className={styles.statusBadge}>
          <span className={styles.statusLabel}>Mode</span>
          <span className={`${styles.statusValue} ${isMockMode ? styles.statusMock : styles.statusReal}`}>
            <span className={`${styles.statusDot} ${isLoading ? styles.pulsing : ''}`} />
            {isLoading ? 'Switching...' : isMockMode ? 'Demo Data' : 'Live API'}
            {!isLoading && (isMockMode ? <WifiOff size={14} /> : <Wifi size={14} />)}
          </span>
        </div>
      </div>

      <div className={styles.hint}>
        <span className={styles.hintIcon}>{isMockMode ? 'Demo' : 'Live'}</span>
        {isMockMode
          ? 'Using simulated data intentionally. Switch to Live API only when the backend is available.'
          : 'Using the configured backend. Switch back to Demo to isolate frontend behavior from live connectivity.'}
      </div>

      {isStreamRunning && !isMockMode ? (
        <div className={styles.streamStatus}>
          <span className={styles.streamIndicator} />
          Binance Stream Active
        </div>
      ) : null}
    </div>
  );
}
