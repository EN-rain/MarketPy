'use client';

export interface DriftMetricsView {
  model_id: string;
  accuracy_drift: number;
  feature_drift: number;
  prediction_drift: number;
}

export default function DriftDisplay({
  metrics,
}: {
  metrics: DriftMetricsView[];
}) {
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
      <h3 style={{ margin: 0 }}>Model Drift Metrics</h3>
      {metrics.length === 0 ? (
        <div style={{ fontSize: 12, color: '#9ca3af' }}>No drift metrics available.</div>
      ) : (
        metrics.map((item) => (
          <div
            key={item.model_id}
            style={{
              border: '1px solid #e5e7eb',
              borderRadius: 8,
              padding: 10,
              display: 'grid',
              gap: 4,
            }}
          >
            <strong>{item.model_id}</strong>
            <div style={{ fontSize: 12 }}>
              Accuracy Drift: {item.accuracy_drift.toFixed(4)}
            </div>
            <div style={{ fontSize: 12 }}>
              Feature Drift (KS): {item.feature_drift.toFixed(4)}
            </div>
            <div style={{ fontSize: 12 }}>
              Prediction Drift: {item.prediction_drift.toFixed(4)}
            </div>
          </div>
        ))
      )}
    </section>
  );
}
