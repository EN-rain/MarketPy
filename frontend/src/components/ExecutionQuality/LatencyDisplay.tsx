'use client';

export interface LatencyPercentilesView {
  p50: number;
  p95: number;
  p99: number;
}

export interface LatencySpikeView {
  order_id: string;
  total_latency_ms: number;
  submission_latency_ms: number;
  fill_latency_ms: number;
}

export default function LatencyDisplay({
  percentiles,
  spikes,
}: {
  percentiles: LatencyPercentilesView;
  spikes: LatencySpikeView[];
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
      <h3 style={{ margin: 0 }}>Latency Monitoring</h3>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(120px, 1fr))', gap: 8 }}>
        <Metric label="p50" value={percentiles.p50} />
        <Metric label="p95" value={percentiles.p95} />
        <Metric label="p99" value={percentiles.p99} />
      </div>

      <div style={{ border: '1px solid #f3f4f6', borderRadius: 8, padding: 10 }}>
        <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 8 }}>Latency Spikes (&gt; 500ms)</div>
        {spikes.length === 0 ? (
          <div style={{ fontSize: 12, color: '#9ca3af' }}>No spikes detected</div>
        ) : (
          spikes.slice(0, 20).map((spike) => (
            <div
              key={spike.order_id}
              style={{
                borderBottom: '1px solid #f9fafb',
                paddingBottom: 6,
                marginBottom: 6,
                fontSize: 12,
              }}
            >
              <strong>{spike.order_id}</strong> total={spike.total_latency_ms.toFixed(2)}ms | submit=
              {spike.submission_latency_ms.toFixed(2)}ms | fill={spike.fill_latency_ms.toFixed(2)}ms
            </div>
          ))
        )}
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: '8px 10px' }}>
      <div style={{ fontSize: 12, color: '#6b7280' }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 700 }}>{value.toFixed(2)} ms</div>
    </div>
  );
}
