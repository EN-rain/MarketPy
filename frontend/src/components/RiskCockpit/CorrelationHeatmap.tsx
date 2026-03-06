'use client';

import { useMemo, useState } from 'react';

export interface CorrelationMatrixView {
  assets: string[];
  matrix: number[][];
  window_days: number;
}

export interface CorrelationShift {
  asset_a: string;
  asset_b: string;
  previous: number;
  current: number;
}

export default function CorrelationHeatmap({
  correlation,
  shifts = [],
}: {
  correlation: CorrelationMatrixView;
  shifts?: CorrelationShift[];
}) {
  const [selected, setSelected] = useState<CorrelationShift | null>(null);

  const shiftIndex = useMemo(() => {
    const index = new Set<string>();
    for (const item of shifts) {
      index.add(`${item.asset_a}|${item.asset_b}`);
      index.add(`${item.asset_b}|${item.asset_a}`);
    }
    return index;
  }, [shifts]);

  return (
    <section
      style={{
        border: '1px solid #e5e7eb',
        borderRadius: 12,
        padding: 16,
        background: '#ffffff',
        display: 'grid',
        gap: 12,
      }}
    >
      <h3 style={{ margin: 0 }}>Correlation Heatmap ({correlation.window_days}d)</h3>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ borderCollapse: 'collapse', minWidth: 420 }}>
          <thead>
            <tr>
              <th style={{ padding: 6 }} />
              {correlation.assets.map((asset) => (
                <th key={`head-${asset}`} style={{ padding: 6, fontSize: 12, color: '#6b7280' }}>
                  {asset}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {correlation.assets.map((rowAsset, i) => (
              <tr key={`row-${rowAsset}`}>
                <th style={{ padding: 6, textAlign: 'left', fontSize: 12, color: '#6b7280' }}>{rowAsset}</th>
                {correlation.assets.map((colAsset, j) => {
                  const value = correlation.matrix[i][j] ?? 0;
                  const key = `${rowAsset}|${colAsset}`;
                  const changed = shiftIndex.has(key);
                  return (
                    <td key={key} style={{ padding: 3 }}>
                      <button
                        type="button"
                        onClick={() => setSelected(findShift(shifts, rowAsset, colAsset, value))}
                        style={{
                          width: 56,
                          height: 34,
                          borderRadius: 6,
                          border: changed ? '2px solid #f59e0b' : '1px solid #d1d5db',
                          cursor: 'pointer',
                          fontSize: 12,
                          fontWeight: 600,
                          color: '#111827',
                          background: correlationColor(value),
                        }}
                        title={`${rowAsset}/${colAsset}: ${value.toFixed(3)}`}
                      >
                        {value.toFixed(2)}
                      </button>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ fontSize: 12, color: '#6b7280' }}>
        Highlighted cells indicate significant shift (&gt; 0.2) versus previous period.
      </div>

      {selected && (
        <div
          style={{
            border: '1px solid #e5e7eb',
            borderRadius: 8,
            padding: 10,
            fontSize: 13,
          }}
        >
          <strong>
            {selected.asset_a} / {selected.asset_b}
          </strong>
          <div>Current correlation: {selected.current.toFixed(4)}</div>
          <div>Previous correlation: {selected.previous.toFixed(4)}</div>
          <div>Shift: {(selected.current - selected.previous).toFixed(4)}</div>
        </div>
      )}
    </section>
  );
}

function correlationColor(value: number): string {
  const clamped = Math.max(-1, Math.min(1, value));
  if (clamped >= 0) {
    const intensity = Math.round(235 - clamped * 120);
    return `rgb(${intensity}, 243, ${intensity})`;
  }
  const intensity = Math.round(235 - Math.abs(clamped) * 120);
  return `rgb(255, ${intensity}, ${intensity})`;
}

function findShift(
  shifts: CorrelationShift[],
  assetA: string,
  assetB: string,
  current: number
): CorrelationShift {
  const found = shifts.find(
    (item) =>
      (item.asset_a === assetA && item.asset_b === assetB) ||
      (item.asset_a === assetB && item.asset_b === assetA)
  );
  if (found) {
    return found;
  }
  return {
    asset_a: assetA,
    asset_b: assetB,
    previous: current,
    current,
  };
}
