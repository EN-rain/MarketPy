'use client';

export interface VaRDisplayResult {
  confidence_level: number;
  var_dollar: number;
  var_percent: number;
  method?: string;
}

export default function VaRDisplay({
  var95,
  var99,
  thresholdPercent,
}: {
  var95: VaRDisplayResult;
  var99: VaRDisplayResult;
  thresholdPercent?: number;
}) {
  const threshold = thresholdPercent ?? 0.05;
  const warn95 = var95.var_percent >= threshold;
  const warn99 = var99.var_percent >= threshold;

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
      <h3 style={{ margin: 0 }}>Value at Risk (VaR)</h3>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(140px, 1fr))', gap: 8 }}>
        <VaRCard title="95% VaR" result={var95} warning={warn95} />
        <VaRCard title="99% VaR" result={var99} warning={warn99} />
      </div>

      <div style={{ fontSize: 12, color: '#6b7280' }}>
        Threshold: {(threshold * 100).toFixed(2)}%
      </div>
    </section>
  );
}

function VaRCard({
  title,
  result,
  warning,
}: {
  title: string;
  result: VaRDisplayResult;
  warning: boolean;
}) {
  return (
    <div
      style={{
        border: `1px solid ${warning ? '#ef4444' : '#d1d5db'}`,
        borderRadius: 8,
        padding: 10,
      }}
    >
      <div style={{ fontSize: 12, color: '#6b7280' }}>{title}</div>
      <div style={{ fontSize: 18, fontWeight: 700 }}>
        ${result.var_dollar.toLocaleString('en-US', { maximumFractionDigits: 2 })}
      </div>
      <div style={{ fontSize: 13 }}>
        {(result.var_percent * 100).toFixed(2)}% ({result.method ?? 'N/A'})
      </div>
      {warning && (
        <div style={{ color: '#b91c1c', fontSize: 12, marginTop: 4 }}>
          Risk threshold exceeded
        </div>
      )}
    </div>
  );
}
