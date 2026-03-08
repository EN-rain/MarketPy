'use client';

interface TradeItem {
  timestamp: string;
  symbol?: string;
  side?: string;
  price?: number;
  size?: number;
}

interface EquityPoint {
  timestamp: string;
  equity: number;
}

export interface StrategyBacktestResult {
  total_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
  win_rate: number;
  trades: TradeItem[];
  equity_curve: EquityPoint[];
}

export default function BacktestResults({ result }: { result: StrategyBacktestResult }) {
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
      <h3 style={{ margin: 0 }}>Backtest Results</h3>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(120px, 1fr))', gap: 8 }}>
        <Metric label="Total Return" value={`${(result.total_return * 100).toFixed(2)}%`} />
        <Metric label="Sharpe" value={result.sharpe_ratio.toFixed(3)} />
        <Metric label="Max Drawdown" value={`${(result.max_drawdown * 100).toFixed(2)}%`} />
        <Metric label="Win Rate" value={`${(result.win_rate * 100).toFixed(2)}%`} />
      </div>

      <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 10 }}>
        <strong>Equity Curve</strong>
        <div style={{ marginTop: 8, maxHeight: 120, overflow: 'auto', fontSize: 12 }}>
          {result.equity_curve.slice(-20).map((point) => (
            <div key={`${point.timestamp}-${point.equity}`}>
              {point.timestamp}: {point.equity.toFixed(4)}
            </div>
          ))}
        </div>
      </div>

      <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 10 }}>
        <strong>Trades</strong>
        <div style={{ marginTop: 8, maxHeight: 160, overflow: 'auto', fontSize: 12 }}>
          {result.trades.length === 0 ? (
            <div>No trades</div>
          ) : (
            result.trades.slice(0, 50).map((trade) => (
              <div key={`${trade.timestamp}-${trade.symbol ?? 'symbol'}-${trade.side ?? 'side'}`}>
                {trade.timestamp} | {trade.symbol ?? '-'} | {trade.side ?? '-'} @{' '}
                {typeof trade.price === 'number' ? trade.price.toFixed(4) : '-'}
              </div>
            ))
          )}
        </div>
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        border: '1px solid #e5e7eb',
        borderRadius: 8,
        padding: '8px 10px',
      }}
    >
      <div style={{ fontSize: 12, color: '#6b7280' }}>{label}</div>
      <div style={{ fontSize: 16, fontWeight: 600 }}>{value}</div>
    </div>
  );
}

