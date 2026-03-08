'use client';

export interface FusionSignalView {
  signal: number;
  confidence: number;
  components: Record<string, number>;
}

export default function FusionSignals({
  current,
  performance,
}: {
  current: FusionSignalView;
  performance: { total_return: number; hit_rate: number };
}) {
  return (
    <section style={{ border: '1px solid #e5e7eb', borderRadius: 12, padding: 16, display: 'grid', gap: 10 }}>
      <h3 style={{ margin: 0 }}>Fusion Signals</h3>
      <div style={{ fontSize: 14 }}>
        Signal: <strong>{current.signal.toFixed(4)}</strong> | Confidence:{' '}
        <strong>{(current.confidence * 100).toFixed(2)}%</strong>
      </div>
      <div style={{ fontSize: 12, color: '#6b7280' }}>Components</div>
      {Object.entries(current.components).map(([k, v]) => (
        <div key={k} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
          <span>{k}</span>
          <span>{v.toFixed(4)}</span>
        </div>
      ))}
      <div style={{ borderTop: '1px solid #f3f4f6', paddingTop: 8, fontSize: 12 }}>
        Backtest: return={performance.total_return.toFixed(4)}, hit rate=
        {(performance.hit_rate * 100).toFixed(2)}%
      </div>
    </section>
  );
}
