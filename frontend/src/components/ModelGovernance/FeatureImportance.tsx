'use client';

export interface FeatureImportanceSeries {
  version: string;
  feature_scores: Record<string, number>;
}

export default function FeatureImportance({
  modelId,
  series,
}: {
  modelId: string;
  series: FeatureImportanceSeries[];
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
      <h3 style={{ margin: 0 }}>Feature Importance - {modelId}</h3>
      {series.length === 0 ? (
        <div style={{ fontSize: 12, color: '#9ca3af' }}>No feature importance snapshots.</div>
      ) : (
        series.map((entry) => (
          <div key={entry.version} style={{ border: '1px solid #f3f4f6', borderRadius: 8, padding: 10 }}>
            <div style={{ fontWeight: 700, marginBottom: 8 }}>Version {entry.version}</div>
            {Object.entries(entry.feature_scores).map(([feature, score]) => (
              <div key={`${entry.version}-${feature}`} style={{ display: 'grid', gridTemplateColumns: '120px 1fr 60px', gap: 8, marginBottom: 6 }}>
                <div style={{ fontSize: 12 }}>{feature}</div>
                <div style={{ background: '#f3f4f6', borderRadius: 4, height: 14, overflow: 'hidden' }}>
                  <div
                    style={{
                      width: `${Math.max(0, Math.min(100, score * 100))}%`,
                      height: '100%',
                      background: '#2563eb',
                    }}
                  />
                </div>
                <div style={{ fontSize: 12, textAlign: 'right' }}>{(score * 100).toFixed(1)}%</div>
              </div>
            ))}
          </div>
        ))
      )}
    </section>
  );
}
