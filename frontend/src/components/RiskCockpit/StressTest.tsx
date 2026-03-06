'use client';

import type { CSSProperties, ReactNode } from 'react';

export interface StressTestResult {
  scenario_name: string;
  base_value: number;
  stressed_value: number;
  value_change: number;
  value_change_percent: number;
  position_impacts: Record<string, number>;
}

export default function StressTest({
  results,
}: {
  results: StressTestResult[];
}) {
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
      <h3 style={{ margin: 0 }}>Stress Testing</h3>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr>
              <Th>Scenario</Th>
              <Th>Base Value</Th>
              <Th>Stressed Value</Th>
              <Th>Change ($)</Th>
              <Th>Change (%)</Th>
            </tr>
          </thead>
          <tbody>
            {results.length === 0 ? (
              <tr>
                <td colSpan={5} style={{ padding: 10, color: '#6b7280' }}>
                  No stress test results
                </td>
              </tr>
            ) : (
              results.map((item) => (
                <tr key={item.scenario_name}>
                  <Td>{item.scenario_name}</Td>
                  <Td>${item.base_value.toLocaleString('en-US', { maximumFractionDigits: 2 })}</Td>
                  <Td>
                    ${item.stressed_value.toLocaleString('en-US', { maximumFractionDigits: 2 })}
                  </Td>
                  <Td style={{ color: item.value_change <= 0 ? '#b91c1c' : '#15803d' }}>
                    {item.value_change.toFixed(2)}
                  </Td>
                  <Td style={{ color: item.value_change_percent <= 0 ? '#b91c1c' : '#15803d' }}>
                    {(item.value_change_percent * 100).toFixed(2)}%
                  </Td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Th({ children }: { children: ReactNode }) {
  return (
    <th
      style={{
        textAlign: 'left',
        borderBottom: '1px solid #e5e7eb',
        padding: '8px 6px',
        color: '#6b7280',
        fontWeight: 600,
      }}
    >
      {children}
    </th>
  );
}

function Td({ children, style }: { children: ReactNode; style?: CSSProperties }) {
  return (
    <td style={{ borderBottom: '1px solid #f3f4f6', padding: '8px 6px', ...style }}>
      {children}
    </td>
  );
}
