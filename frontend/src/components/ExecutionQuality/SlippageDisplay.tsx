'use client';

export interface SlippageAnalysisView {
  count: number;
  avg_slippage_bps: number;
  by_symbol: Record<string, number>;
  by_size_bucket: Record<string, number>;
  by_hour: Record<string, number>;
}

export default function SlippageDisplay({
  analysis,
}: {
  analysis: SlippageAnalysisView;
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
      <h3 style={{ margin: 0 }}>Slippage Tracking</h3>
      <div style={{ fontSize: 13 }}>
        Records: {analysis.count} | Average: {analysis.avg_slippage_bps.toFixed(2)} bps
      </div>

      <Histogram title="By Symbol" values={analysis.by_symbol} />
      <Histogram title="By Size Bucket" values={analysis.by_size_bucket} />
      <Histogram title="By Hour" values={analysis.by_hour} />
    </section>
  );
}

function Histogram({ title, values }: { title: string; values: Record<string, number> }) {
  const entries = Object.entries(values);
  const maxVal = Math.max(...entries.map(([, value]) => Math.abs(value)), 1);
  return (
    <div style={{ border: '1px solid #f3f4f6', borderRadius: 8, padding: 10 }}>
      <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 8 }}>{title}</div>
      {entries.length === 0 ? (
        <div style={{ fontSize: 12, color: '#9ca3af' }}>No data</div>
      ) : (
        entries.map(([label, value]) => {
          const width = (Math.abs(value) / maxVal) * 100;
          const negative = value < 0;
          return (
            <div key={label} style={{ display: 'grid', gridTemplateColumns: '100px 1fr 70px', gap: 8, marginBottom: 6 }}>
              <div style={{ fontSize: 12 }}>{label}</div>
              <div style={{ background: '#f3f4f6', borderRadius: 4, height: 16, overflow: 'hidden' }}>
                <div
                  style={{
                    width: `${width}%`,
                    height: '100%',
                    background: negative ? '#ef4444' : '#22c55e',
                  }}
                />
              </div>
              <div style={{ fontSize: 12, textAlign: 'right' }}>{value.toFixed(2)} bps</div>
            </div>
          );
        })
      )}
    </div>
  );
}
