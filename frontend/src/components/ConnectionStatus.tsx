'use client';

import { AlertCircle, CheckCircle, Wifi, WifiOff } from 'lucide-react';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useMockMode, setMockMode } from './DevModeToggle';
import { getApiBaseUrl, getWebSocketUrl } from '@/lib/apiRuntime';
import styles from './ConnectionStatus.module.css';

const WS_URL = getWebSocketUrl();

export default function ConnectionStatus() {
  const isMockMode = useMockMode();
  const { isConnected } = useWebSocket(WS_URL);

  // Demo Mode - Always show as connected with mock data
  if (isMockMode) {
    return (
      <div className={`${styles.status} ${styles.mock}`}>
        <CheckCircle size={16} />
        <span>Demo Mode Active</span>
      </div>
    );
  }

  // Live Mode - Show actual connection status
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
      <div className={styles.actions}>
        <button 
          onClick={() => setMockMode(true)} 
          className={styles.switchButton}
        >
          <AlertCircle size={14} />
          Switch to Demo
        </button>
      </div>
      <p className={styles.helpText}>
        Live API unreachable at {getApiBaseUrl()}
      </p>
    </div>
  );
}
