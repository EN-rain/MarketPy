import { useEffect, useMemo, useState } from 'react';
import { Play, RotateCcw, Loader2 } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardBody, Badge, ProgressBar } from '../components/UI';
import { backtestResults, type BacktestResult, formatNumber } from '../data/mock';
import { cn } from '../utils/cn';

type BacktestRow = BacktestResult & { progress?: number };

function MetricBox({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="bg-bg-tertiary rounded px-3 py-2">
      <p className="text-[9px] uppercase tracking-wider text-text-muted font-medium mb-0.5">{label}</p>
      <p className={cn('text-sm font-mono font-semibold tabular-nums', color || 'text-text-primary')}>{value}</p>
    </div>
  );
}

function createBacktestRun(existing: BacktestRow[], strategy = 'AlphaNet Sweep'): BacktestRow {
  const maxNum = existing.reduce((max, b) => {
    const num = Number.parseInt(b.id.replace('BT-', ''), 10);
    return Number.isFinite(num) ? Math.max(max, num) : max;
  }, 0);

  return {
    id: `BT-${String(maxNum + 1).padStart(3, '0')}`,
    strategy,
    pair: 'BTC/USDT',
    period: '2024-01 -> 2024-06',
    trades: 0,
    winRate: 0,
    totalReturn: 0,
    sharpe: 0,
    maxDrawdown: 0,
    status: 'queued',
    duration: '--',
    progress: 0,
  };
}

export default function Backtests() {
  const [rows, setRows] = useState<BacktestRow[]>(backtestResults.map(b => ({ ...b, progress: b.status === 'completed' ? 100 : b.status === 'running' ? 42 : 0 })));

  useEffect(() => {
    const timer = setInterval(() => {
      setRows(prev => {
        const next = [...prev];
        const runningIdx = next.findIndex(b => b.status === 'running');

        if (runningIdx === -1) {
          const queuedIdx = next.findIndex(b => b.status === 'queued');
          if (queuedIdx !== -1) {
            next[queuedIdx] = { ...next[queuedIdx], status: 'running', progress: 10, duration: '0m 05s' };
          }
          return next;
        }

        const running = next[runningIdx];
        const progress = Math.min(100, (running.progress ?? 0) + 18);

        if (progress >= 100) {
          const totalReturn = Number.parseFloat((Math.random() * 40 - 5).toFixed(1));
          const winRate = Number.parseFloat((48 + Math.random() * 32).toFixed(1));
          const sharpe = Number.parseFloat((0.8 + Math.random() * 2.1).toFixed(2));
          const maxDrawdown = -Number.parseFloat((2 + Math.random() * 15).toFixed(1));
          const trades = Math.floor(120 + Math.random() * 500);

          next[runningIdx] = {
            ...running,
            status: 'completed',
            progress: 100,
            duration: `${Math.floor(1 + Math.random() * 5)}m ${String(Math.floor(Math.random() * 59)).padStart(2, '0')}s`,
            totalReturn,
            winRate,
            sharpe,
            maxDrawdown,
            trades,
          };
          return next;
        }

        next[runningIdx] = {
          ...running,
          progress,
          duration: `0m ${String(5 + Math.floor(progress / 4)).padStart(2, '0')}s`,
        };

        return next;
      });
    }, 2500);

    return () => clearInterval(timer);
  }, []);

  const completed = useMemo(() => rows.filter(b => b.status === 'completed'), [rows]);
  const bestReturn = useMemo(() => completed.reduce<BacktestRow | undefined>((best, b) => {
    if (!best) return b;
    return b.totalReturn > best.totalReturn ? b : best;
  }, undefined), [completed]);

  const addNewBacktest = () => setRows(prev => [createBacktestRun(prev), ...prev]);
  const rerunBest = () => {
    if (!bestReturn) return;
    setRows(prev => [createBacktestRun(prev, `${bestReturn.strategy} Re-run`), ...prev]);
  };

  return (
    <div className="space-y-4 animate-slide-up">
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
            <p className="text-xl font-mono font-semibold text-profit">{bestReturn ? `+${bestReturn.totalReturn}%` : '--'}</p>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="py-3">
            <p className="text-[10px] uppercase tracking-wider text-text-muted font-medium mb-1">Best Sharpe</p>
            <p className="text-xl font-mono font-semibold text-info">
              {completed.reduce((best, b) => (b.sharpe > best ? b.sharpe : best), 0).toFixed(2)}
            </p>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="py-3">
            <p className="text-[10px] uppercase tracking-wider text-text-muted font-medium mb-1">Running</p>
            <p className="text-xl font-mono font-semibold text-warn">{rows.filter(b => b.status === 'running').length}</p>
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Backtest Results</CardTitle>
          <button
            onClick={addNewBacktest}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-accent/10 text-accent text-[11px] font-medium border border-accent/20 hover:bg-accent/20 transition-all cursor-pointer"
          >
            <Play size={11} /> New Backtest
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
                <th className="text-left px-4 py-2.5 font-medium">Status</th>
                <th className="text-right px-4 py-2.5 font-medium">Duration</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.map(bt => (
                <tr key={bt.id} className="hover:bg-bg-hover transition-colors">
                  <td className="px-4 py-3 font-mono text-text-muted">{bt.id}</td>
                  <td className="px-4 py-3 font-medium text-text-primary">{bt.strategy}</td>
                  <td className="px-4 py-3 font-mono text-text-secondary">{bt.pair}</td>
                  <td className="px-4 py-3 font-mono text-text-muted text-[10px]">{bt.period}</td>
                  <td className="px-4 py-3 font-mono text-right text-text-secondary tabular-nums">{bt.trades || '--'}</td>
                  <td className="px-4 py-3 font-mono text-right tabular-nums">
                    {bt.winRate > 0 ? (
                      <span className={bt.winRate >= 60 ? 'text-profit' : bt.winRate >= 50 ? 'text-warn' : 'text-loss'}>
                        {formatNumber(bt.winRate, 1)}%
                      </span>
                    ) : '--'}
                  </td>
                  <td className={cn('px-4 py-3 font-mono text-right tabular-nums font-medium',
                    bt.totalReturn > 0 ? 'text-profit' : bt.totalReturn < 0 ? 'text-loss' : 'text-text-muted',
                  )}>
                    {bt.totalReturn !== 0 ? `${bt.totalReturn > 0 ? '+' : ''}${formatNumber(bt.totalReturn, 1)}%` : '--'}
                  </td>
                  <td className={cn('px-4 py-3 font-mono text-right tabular-nums',
                    bt.sharpe >= 2 ? 'text-accent' : bt.sharpe >= 1 ? 'text-text-primary' : 'text-text-muted',
                  )}>
                    {bt.sharpe > 0 ? formatNumber(bt.sharpe, 2) : '--'}
                  </td>
                  <td className="px-4 py-3 font-mono text-right tabular-nums text-loss">
                    {bt.maxDrawdown !== 0 ? `${formatNumber(bt.maxDrawdown, 1)}%` : '--'}
                  </td>
                  <td className="px-4 py-3">
                    {bt.status === 'completed' && <Badge variant="accent">Completed</Badge>}
                    {bt.status === 'running' && (
                      <Badge variant="warning">
                        <Loader2 size={9} className="animate-spin mr-1" /> Running {bt.progress ?? 0}%
                      </Badge>
                    )}
                    {bt.status === 'queued' && <Badge>Queued</Badge>}
                  </td>
                  <td className="px-4 py-3 font-mono text-right text-text-muted">{bt.duration}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardBody>
      </Card>

      {bestReturn && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <CardTitle>Best Strategy: {bestReturn.strategy}</CardTitle>
              <Badge variant="success">Top Performer</Badge>
            </div>
            <button onClick={rerunBest} className="flex items-center gap-1 text-[11px] text-text-muted hover:text-text-primary transition-colors cursor-pointer">
              <RotateCcw size={11} /> Re-run
            </button>
          </CardHeader>
          <CardBody>
            <div className="grid grid-cols-6 gap-3">
              <MetricBox label="Total Return" value={`+${bestReturn.totalReturn}%`} color="text-profit" />
              <MetricBox label="Sharpe Ratio" value={formatNumber(bestReturn.sharpe, 2)} color="text-accent" />
              <MetricBox label="Win Rate" value={`${bestReturn.winRate}%`} color="text-profit" />
              <MetricBox label="Total Trades" value={bestReturn.trades.toString()} />
              <MetricBox label="Max Drawdown" value={`${bestReturn.maxDrawdown}%`} color="text-loss" />
              <MetricBox label="Period" value={bestReturn.period.split(' -> ')[1] || bestReturn.period} />
            </div>
            <div className="mt-4 grid grid-cols-3 gap-4">
              <div>
                <p className="text-[10px] uppercase tracking-wider text-text-muted font-medium mb-2">Win Rate</p>
                <ProgressBar value={bestReturn.winRate} color="profit" className="h-1.5" />
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-wider text-text-muted font-medium mb-2">Sharpe Score</p>
                <ProgressBar value={bestReturn.sharpe * 33} color="accent" className="h-1.5" />
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-wider text-text-muted font-medium mb-2">Risk (Inv. DD)</p>
                <ProgressBar value={100 + bestReturn.maxDrawdown} color="warn" className="h-1.5" />
              </div>
            </div>
          </CardBody>
        </Card>
      )}
    </div>
  );
}
