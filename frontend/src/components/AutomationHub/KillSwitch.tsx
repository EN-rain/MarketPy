'use client';

import { useState } from 'react';
import styles from './KillSwitch.module.css';

export default function KillSwitch({
  onToggle,
}: {
  onToggle?: (engaged: boolean) => void;
}) {
  const [engaged, setEngaged] = useState(false);

  const toggle = () => {
    setEngaged((prev) => {
      const next = !prev;
      onToggle?.(next);
      return next;
    });
  };

  return (
    <div className={styles.card}>
      <div className={styles.label}>Automation Kill Switch</div>
      <button
        type="button"
        onClick={toggle}
        className={`${styles.button} ${engaged ? styles.engaged : styles.armed}`}
      >
        {engaged ? 'Kill Switch: ENGAGED' : 'Kill Switch: ARMED'}
      </button>
    </div>
  );
}
