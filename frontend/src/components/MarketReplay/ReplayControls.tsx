'use client';

import { useState } from 'react';

export default function ReplayControls({
  onStart,
  onPause,
  onResume,
  onSeek,
}: {
  onStart?: (speed: number) => void;
  onPause?: () => void;
  onResume?: () => void;
  onSeek?: (index: number) => void;
}) {
  const [speed, setSpeed] = useState(1);
  const [position, setPosition] = useState(0);

  return (
    <section style={{ border: '1px solid #e5e7eb', borderRadius: 12, padding: 16, display: 'grid', gap: 10 }}>
      <h3 style={{ margin: 0 }}>Market Replay Controls</h3>
      <label style={{ display: 'grid', gap: 4 }}>
        <span style={{ fontSize: 12, color: '#6b7280' }}>Speed ({speed.toFixed(1)}x)</span>
        <input
          type="range"
          min={0.1}
          max={100}
          step={0.1}
          value={speed}
          onChange={(e) => setSpeed(Number(e.target.value))}
        />
      </label>
      <label style={{ display: 'grid', gap: 4 }}>
        <span style={{ fontSize: 12, color: '#6b7280' }}>Seek</span>
        <input
          type="number"
          min={0}
          value={position}
          onChange={(e) => setPosition(Number(e.target.value))}
          style={{ border: '1px solid #d1d5db', borderRadius: 8, padding: '8px 10px' }}
        />
      </label>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button type="button" onClick={() => onStart?.(speed)}>Start</button>
        <button type="button" onClick={() => onPause?.()}>Pause</button>
        <button type="button" onClick={() => onResume?.()}>Resume</button>
        <button type="button" onClick={() => onSeek?.(position)}>Seek</button>
      </div>
    </section>
  );
}
