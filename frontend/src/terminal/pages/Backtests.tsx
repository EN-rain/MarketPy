'use client';

import { useMemo, useState } from 'react';
import { Loader2, Play, RotateCcw } from 'lucide-react';
import { postApi, useApi } from '@/hooks/useApi';
import { InlineNotice } from '@/components/RequestState';
import { Card, CardHeader, CardTitle, CardBody, Badge, ProgressBar } from '../components/UI';
import { cn } from '../utils/cn';

type BacktestCapabilities = {
  strategies: string[];
  execution_modes: string[];
  defaults: {
    strategy: string;
    execution_mode: string;
    bar_size: string;
    fill_model: string;
    use_instant_engine: boolean;
  };
  constraints: {
    api_key_required: boolean;
    rate_limit_per_minute: number;
    max_markets_per_request: number;
  };
};

type RecentBacktest = {
  id: string;
  strategy: string;
  pair: string;
  period: string;
  trades: number;
  win_rate: number;
  total_return: number;
  sharpe?: number | null;
  max_drawdown: number;
  status: string;
  duration?: number | string | null;
  execution_mode: string;
  engine: string;
};

type RecentBacktestResponse = {
  items: RecentBacktest[];
};

type RateLimitStatus = {
  used: number;
  limit: number;
  remaining: number;
};

type RunBacktestResponse = {
  total_pnl_pct: number;
  total_trades: number;
  win_rate: number;
  max_drawdown: number;
  sharpe_ratio?: number | null;
  diagnostics: Record<string, unknown>;
};

function formatNumber(value: number, digits = 2): string {
  return value.toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function formatDuration(value?: number | string | null): string {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value < 1000 ? `${Math.round(value)} ms` : `${(value / 1000).toFixed(1)} s`;
  }
  if (typeof value === 'string' && value.trim()) {
    return value;
  }
  return '--';
}

function MetricBox({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="bg-bg-tertiary rounded px-3 py-2">
      <p className="text-[9px] uppercase tracking-wider text-text-muted font-medium mb-0.5">{label}</p>
      <p className={cn('text-sm font-mono font-semibold tabular-nums', color ?? 'text-text-primary')}>{value}</p>
    </div>
  );
}

async function submitBacktest(strategy: string): Promise<RunBacktestResponse> {
  return postApi<RunBacktestResponse>('/backtest/run', {
    market_ids: ['BTCUSDT'],
    strategy,
    start_date: '2024-01-01T00:00:00Z',
    end_date: '2024-06-30T23:59:59Z',
    initial_cash: 10000,
    bar_size: '5m',
    fill_model: 'M2',
    use_instant_engine: true,
    execution_mode: 'event_driven',
  });
}

export default function Backtests() {
  const [actionNotice, setActionNotice] = useState<{ variant: 'success' | 'warning' | 'error'; message: string } | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const recentRequest = useApi<RecentBacktestResponse>('/backtest/recent', { pollInterval: 5000 });
  const capabilitiesRequest = useApi<BacktestCapabilities>('/backtest/capabilities', { pollInterval: 30000 });
  const rateLimitRequest = useApi<RateLimitStatus>('/backtest/rate-limit-status', { pollInterval: 10000 });

  const rows = recentRequest.data?.items ?? [];
  const completed = rows.filter((row) => row.status === 'completed');
  const bestReturn = useMemo(
    () =>
      completed.reduce<RecentBacktest | null>((best, row) => {
        if (!best || row.total_return > best.total_return) {
          return row;
        }
        return best;
      }, null),
    [completed],
  );
  const bestSharpe = completed.reduce((best, row) => Math.max(best, row.sharpe ?? 0), 0);

  async function runBacktest(strategy?: string) {
    const selectedStrategy = strategy ?? capabilitiesRequest.data?.defaults.strategy ?? 'momentum';
    setIsSubmitting(true);
    setActionNotice(null);
    try {
      await submitBacktest(selectedStrategy);
      await recentRequest.refetch();
      await rateLimitRequest.refetch();
      setActionNotice({ variant: 'success', message: `Backtest completed with ${selectedStrategy}.` });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Backtest run failed.';
      setActionNotice({ variant: 'error', message });
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="space-y-4 animate-slide-up">
      {actionNotice ? <InlineNotice variant={actionNotice.variant} message={actionNotice.message} /> : null}

      <div className="grid grid-cols-5 gap-3">
        <Card>
          <CardBody className="py-3">
            <p className="text-[10px] uppercase tracking-wider text-text-muted font-medium mb-1">Total Backtests</p>
            <p className="text-xl font-mono font-semibold text-text-primary">{rows.length}</p>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="py-3">
            <p className="text-[10px] uppercase tracking-wider text-text-muted font-medium mb-1">Completed</p>
            <p className="text-xl font-mono font-semibold text-accent">{completed.length}</p>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="py-3">
            <p className="text-[10px] uppercase tracking-wider text-text-muted font-medium mb-1">Best Return</p>
            <p className="text-xl font-mono font-semibold text-profit">
              {bestReturn ? `${bestReturn.total_return > 0 ? '+' : ''}${formatNumber(bestReturn.total_return, 1)}%` : '--'}
            </p>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="py-3">
            <p className="text-[10px] uppercase tracking-wider text-text-muted font-medium mb-1">Best Sharpe</p>
            <p className="text-xl font-mono font-semibold text-info">{bestSharpe > 0 ? formatNumber(bestSharpe, 2) : '--'}</p>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="py-3 space-y-1.5">
            <div className="flex items-center justify-between text-[10px] uppercase tracking-wider text-text-muted font-medium">
              <span>Rate Limit</span>
              <span className="font-mono normal-case text-text-secondary">
                {rateLimitRequest.data ? `${rateLimitRequest.data.remaining}/${rateLimitRequest.data.limit}` : '--'}
              </span>
            </div>
            <ProgressBar
              value={rateLimitRequest.data?.used ?? 0}
              max={Math.max(rateLimitRequest.data?.limit ?? 1, 1)}
              color="warn"
              className="h-1.5"
            />
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Backtest Results</CardTitle>
          <button
            onClick={() => void runBacktest()}
            disabled={isSubmitting}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-accent/10 text-accent text-[11px] font-medium border border-accent/20 hover:bg-accent/20 transition-all cursor-pointer disabled:opacity-60"
          >
            {isSubmitting ? <Loader2 size={11} className="animate-spin" /> : <Play size={11} />}
            Run Backtest
          </button>
        </CardHeader>
        <CardBody className="p-0">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border text-[10px] uppercase tracking-wider text-text-muted">
                <th className="text-left px-4 py-2.5 font-medium">ID</th>
                <th className="text-left px-4 py-2.5 font-medium">Strategy</th>
                <th className="text-left px-4 py-2.5 font-medium">Pair</th>
                <th className="text-left px-4 py-2.5 font-medium">Period</th>
                <th className="text-right px-4 py-2.5 font-medium">Trades</th>
                <th className="text-right px-4 py-2.5 font-medium">Win Rate</th>
                <th className="text-right px-4 py-2.5 font-medium">Return</th>
                <th className="text-right px-4 py-2.5 font-medium">Sharpe</th>
                <th className="text-right px-4 py-2.5 font-medium">Max DD</th>
                <th className="text-left px-4 py-2.5 font-medium">Engine</th>
                <th className="text-right px-4 py-2.5 font-medium">Duration</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.map((row) => (
                <tr key={row.id} className="hover:bg-bg-hover transition-colors">
                  <td className="px-4 py-3 font-mono text-text-muted">{row.id}</td>
                  <td className="px-4 py-3 font-medium text-text-primary">{row.strategy}</td>
                  <td className="px-4 py-3 font-mono text-text-secondary">{row.pair}</td>
                  <td className="px-4 py-3 font-mono text-text-muted text-[10px]">{row.period}</td>
                  <td className="px-4 py-3 font-mono text-right text-text-secondary tabular-nums">{row.trades}</td>
                  <td className="px-4 py-3 font-mono text-right tabular-nums">
                    <span className={row.win_rate >= 60 ? 'text-profit' : row.win_rate >= 50 ? 'text-warn' : 'text-loss'}>
                      {formatNumber(row.win_rate, 1)}%
                    </span>
                  </td>
                  <td className={cn(
                    'px-4 py-3 font-mono text-right tabular-nums font-medium',
                    row.total_return > 0 ? 'text-profit' : row.total_return < 0 ? 'text-loss' : 'text-text-muted',
                  )}>
                    {`${row.total_return > 0 ? '+' : ''}${formatNumber(row.total_return, 1)}%`}
                  </td>
                  <td className={cn(
                    'px-4 py-3 font-mono text-right tabular-nums',
                    (row.sharpe ?? 0) >= 2 ? 'text-accent' : (row.sharpe ?? 0) >= 1 ? 'text-text-primary' : 'text-text-muted',
                  )}>
                    {row.sharpe != null ? formatNumber(row.sharpe, 2) : '--'}
                  </td>
                  <td className="px-4 py-3 font-mono text-right tabular-nums text-loss">{formatNumber(row.max_drawdown, 1)}%</td>
                  <td className="px-4 py-3">
                    <Badge variant={row.engine === 'instant' ? 'accent' : row.engine === 'vectorized' ? 'info' : 'default'}>
                      {row.engine}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 font-mono text-right text-text-muted">{formatDuration(row.duration)}</td>
                </tr>
              ))}
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={11} className="px-4 py-8 text-center text-text-muted">
                    No live backtest runs recorded yet.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <CardTitle>{bestReturn ? `Best Strategy: ${bestReturn.strategy}` : 'Backtest Defaults'}</CardTitle>
            {bestReturn ? <Badge variant="success">Top Performer</Badge> : null}
          </div>
          {bestReturn ? (
            <button onClick={() => void runBacktest(bestReturn.strategy)} className="flex items-center gap-1 text-[11px] text-text-muted hover:text-text-primary transition-colors cursor-pointer">
              <RotateCcw size={11} /> Re-run
            </button>
          ) : null}
        </CardHeader>
        <CardBody>
          {bestReturn ? (
            <>
              <div className="grid grid-cols-6 gap-3">
                <MetricBox label="Total Return" value={`${bestReturn.total_return > 0 ? '+' : ''}${formatNumber(bestReturn.total_return, 1)}%`} color="text-profit" />
                <MetricBox label="Sharpe Ratio" value={bestReturn.sharpe != null ? formatNumber(bestReturn.sharpe, 2) : '--'} color="text-accent" />
                <MetricBox label="Win Rate" value={`${formatNumber(bestReturn.win_rate, 1)}%`} color="text-profit" />
                <MetricBox label="Total Trades" value={bestReturn.trades.toString()} />
                <MetricBox label="Max Drawdown" value={`${formatNumber(bestReturn.max_drawdown, 1)}%`} color="text-loss" />
                <MetricBox label="Engine" value={bestReturn.engine} />
              </div>
              <div className="mt-4 grid grid-cols-3 gap-4">
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-text-muted font-medium mb-2">Win Rate</p>
                  <ProgressBar value={bestReturn.win_rate} color="profit" className="h-1.5" />
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-text-muted font-medium mb-2">Sharpe Score</p>
                  <ProgressBar value={(bestReturn.sharpe ?? 0) * 33} color="accent" className="h-1.5" />
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-text-muted font-medium mb-2">Risk (Inv. DD)</p>
                  <ProgressBar value={100 + bestReturn.max_drawdown} color="warn" className="h-1.5" />
                </div>
              </div>
            </>
          ) : (
            <div className="grid grid-cols-4 gap-3">
              <MetricBox label="Default Strategy" value={capabilitiesRequest.data?.defaults.strategy ?? '--'} />
              <MetricBox label="Execution Mode" value={capabilitiesRequest.data?.defaults.execution_mode ?? '--'} />
              <MetricBox label="Bar Size" value={capabilitiesRequest.data?.defaults.bar_size ?? '--'} />
              <MetricBox label="Markets / Run" value={String(capabilitiesRequest.data?.constraints.max_markets_per_request ?? '--')} />
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
