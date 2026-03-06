'use client';

import { AlertTriangle, CheckCircle2, RefreshCw, WifiOff } from 'lucide-react';
import styles from './RequestState.module.css';

type Variant = 'error' | 'warning' | 'success';

function getVariantIcon(variant: Variant) {
  switch (variant) {
    case 'success':
      return <CheckCircle2 size={18} />;
    case 'warning':
      return <AlertTriangle size={18} />;
    default:
      return <WifiOff size={18} />;
  }
}

export function InlineNotice({
  variant,
  message,
}: {
  variant: Variant;
  message: string;
}) {
  return (
    <div className={`${styles.inline} ${styles[variant]}`} role="status">
      {getVariantIcon(variant)}
      <span>{message}</span>
    </div>
  );
}

export function ErrorState({
  title,
  description,
  onRetry,
}: {
  title: string;
  description: string;
  onRetry?: () => void;
}) {
  return (
    <div className={`${styles.card} ${styles.error}`} role="alert">
      <div className={styles.icon}>
        <WifiOff size={20} />
      </div>
      <div className={styles.title}>{title}</div>
      <div className={styles.description}>{description}</div>
      {onRetry ? (
        <div className={styles.actions}>
          <button type="button" className="btn btn-secondary" onClick={onRetry}>
            <RefreshCw size={16} />
            Retry
          </button>
        </div>
      ) : null}
    </div>
  );
}

export function LoadingState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className={`${styles.card} ${styles.warning}`} role="status">
      <div className={styles.icon}>
        <RefreshCw size={20} className="animate-spin-slow" />
      </div>
      <div className={styles.title}>{title}</div>
      <div className={styles.description}>{description}</div>
    </div>
  );
}
