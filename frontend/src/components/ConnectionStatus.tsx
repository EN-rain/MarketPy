'use client';

import { Wifi, WifiOff } from 'lucide-react';
import { useWebSocket } from '@/hooks/useWebSocket';
import { getApiBaseUrl, getWebSocketUrl } from '@/lib/apiRuntime';
import styles from './ConnectionStatus.module.css';

const WS_URL = getWebSocketUrl();

export default function ConnectionStatus() {
  const { isConnected } = useWebSocket(WS_URL);

  if (isConnected) {
    return (
      <div className={`${styles.status} ${styles.connected}`}>
        <Wifi size={16} />
        <span>Live Connected</span>
      </div>
    );
  }

  // Disconnected - Show error with option to switch to demo
  return (
    <div className={styles.errorContainer}>
      <div className={`${styles.status} ${styles.error}`}>
        <WifiOff size={16} />
        <span>Backend Disconnected</span>
      </div>
      <p className={styles.helpText}>
        Live API unreachable at {getApiBaseUrl()}
      </p>
    </div>
  );
}
