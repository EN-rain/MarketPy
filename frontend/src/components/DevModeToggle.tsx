'use client';

import { useState, useEffect, useSyncExternalStore, useCallback } from 'react';
import { Database, Wifi, Loader2 } from 'lucide-react';
import { postApi } from '@/hooks/useApi';
import { getApiUrl } from '@/lib/apiRuntime';
import styles from './DevModeToggle.module.css';

let globalMockMode = false;
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
    localStorage.setItem('marketpy_mock_mode', 'false');
  }

  emitChange(false);
}

export function useMockMode() {
  return useSyncExternalStore(subscribeToMockMode, () => false, () => false);
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

  const ensureLiveStream = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
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
    } catch (nextError: unknown) {
      const message =
        nextError instanceof Error
          ? nextError.message
          : 'Failed to start live market stream. Confirm the backend is reachable.';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    emitChange(false);
    localStorage.setItem('marketpy_mock_mode', 'false');
    void checkStreamStatus();
  }, [checkStreamStatus]);

  useEffect(() => {
    if (!isStreamRunning && !isLoading) {
      void ensureLiveStream();
    }
  }, [ensureLiveStream, isLoading, isStreamRunning]);

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
            checked
            onChange={() => undefined}
            disabled
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
          <span className={`${styles.statusValue} ${styles.statusReal}`}>
            <span className={`${styles.statusDot} ${isLoading ? styles.pulsing : ''}`} />
            {isLoading ? 'Starting Stream...' : 'Live API Only'}
            {!isLoading ? <Wifi size={14} /> : null}
          </span>
        </div>
      </div>

      <div className={styles.hint}>
        <span className={styles.hintIcon}>Live</span>
        Demo mode is disabled. All terminal pages read from the configured API and websocket feed.
      </div>

      {isStreamRunning ? (
        <div className={styles.streamStatus}>
          <span className={styles.streamIndicator} />
          Binance Stream Active
        </div>
      ) : null}

      {!isStreamRunning && !isLoading ? (
        <div className={styles.streamStatus}>
          <span className={styles.streamIndicator} />
          Attempting to start live stream
        </div>
      ) : null}
    </div>
  );
}
