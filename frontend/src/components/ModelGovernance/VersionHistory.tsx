'use client';

import { useState } from 'react';

export interface VersionItem {
  model_id: string;
  version: string;
  status: string;
  performance_metrics: Record<string, number>;
}

export default function VersionHistory({
  versions,
  onSelect,
}: {
  versions: VersionItem[];
  onSelect?: (version: VersionItem) => void;
}) {
  const [selected, setSelected] = useState<string | null>(versions[0]?.version ?? null);

  const selectVersion = (item: VersionItem) => {
    setSelected(item.version);
    onSelect?.(item);
  };

  return (
    <section
      style={{
        border: '1px solid #e5e7eb',
        borderRadius: 12,
        padding: 16,
        background: '#ffffff',
        display: 'grid',
        gap: 10,
      }}
    >
      <h3 style={{ margin: 0 }}>Model Version History</h3>
      {versions.length === 0 ? (
        <div style={{ fontSize: 12, color: '#9ca3af' }}>No versions registered.</div>
      ) : (
        versions.map((item) => (
          <button
            key={`${item.model_id}-${item.version}`}
            type="button"
            onClick={() => selectVersion(item)}
            style={{
              border: selected === item.version ? '2px solid #111827' : '1px solid #d1d5db',
              borderRadius: 8,
              padding: 10,
              textAlign: 'left',
              background: '#fff',
              cursor: 'pointer',
            }}
          >
            <div style={{ fontWeight: 700 }}>
              {item.model_id} v{item.version}
            </div>
            <div style={{ fontSize: 12, color: '#6b7280' }}>Status: {item.status}</div>
            <div style={{ fontSize: 12, marginTop: 4 }}>
              {Object.entries(item.performance_metrics).map(([k, v]) => `${k}=${v.toFixed(4)}`).join(' | ')}
            </div>
          </button>
        ))
      )}
    </section>
  );
}
