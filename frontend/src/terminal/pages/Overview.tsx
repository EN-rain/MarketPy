'use client';

import { useMemo, useRef, useState } from 'react';
import { TrendingUp, Activity, DollarSign, BarChart3, AlertTriangle } from 'lucide-react';
import { useApi } from '@/hooks/useApi';
import { useWebSocket, WSMessage } from '@/hooks/useWebSocket';
import { Card, CardHeader, CardTitle, CardBody, Badge, Chip, MiniSparkline, StatValue, ProgressBar } from '../components/UI';
import { cn } from '../utils/cn';

type MarketRecord = {
  market_id: string;
  question: string;
  mid: number;
  change_24h_pct: number;
  volume_24h: number;
};

type PortfolioPosition = {
  side: string;
  size: number;
  avg_entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  market_value: number;
};

type PortfolioRecord = {
  cash: number;
  initial_cash: number;
  total_equity: number;
  total_pnl: number;
  total_pnl_pct: number;
  positions: Record<string, PortfolioPosition>;
  trades: TradeRecord[];
};

type TradeRecord = {
  id: string;
  timestamp: string;
  market_id: string;
  action: string;
  price: number;
  size: number;
  fee: number;
  pnl?: number | null;
  strategy: string;
};

type SignalRecord = {
  market_id: string;
  decision: string;
  confidence: number;
  edge: number;
  predicted_price?: number | null;
  current_mid?: number | null;
  strategy?: string;
  reason?: string;
};

type ActivityEntry = {
  id: string;
  time: string;
  level: 'info' | 'warn' | 'error';
  msg: string;
};

type EquityScaleMode = 'tight' | 'balanced' | 'full';

const currencyFormatter = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 2,
});

function formatCurrency(value: number): string {
  return currencyFormatter.format(Number.isFinite(value) ? value : 0);
}

function formatNumber(value: number, digits = 2): string {
  return value.toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function formatTime(timestamp: string): string {
  const parsed = new Date(timestamp);
  return Number.isNaN(parsed.valueOf()) ? '--:--:--' : parsed.toISOString().slice(11, 19);
}

function buildSparkline(prices: number[], fallback: number): number[] {
  if (prices.length >= 2) {
    return prices.slice(-15);
  }
  const base = fallback > 0 ? fallback : 1;
  return Array.from({ length: 15 }, (_, index) => base * (1 + index * 0.0005));
}

function getScaleBounds(data: number[], scaleMode: EquityScaleMode): { min: number; max: number; range: number } {
  const rawMin = Math.min(...data);
  const rawMax = Math.max(...data);
  const rawRange = rawMax - rawMin;
  const baseRange = rawRange || Math.max(rawMax * 0.01, 1);
  const midpoint = (rawMax + rawMin) / 2;

  if (scaleMode === 'full') {
    const paddedMin = Math.min(0, rawMin - baseRange * 0.1);
    const paddedMax = rawMax + baseRange * 0.1;
    return { min: paddedMin, max: paddedMax, range: paddedMax - paddedMin || 1 };
  }

  if (scaleMode === 'balanced') {
    const halfRange = baseRange * 0.8;
    const min = midpoint - halfRange;
    const max = midpoint + halfRange;
    return { min, max, range: max - min || 1 };
  }

  const min = rawMin - baseRange * 0.15;
  const max = rawMax + baseRange * 0.15;
  return { min, max, range: max - min || 1 };
}

function EquityChart({ data, scaleMode }: { data: number[]; scaleMode: EquityScaleMode }) {
  const w = 600;
  const h = 140;
  const padding = 8;
  const { min, range } = getScaleBounds(data, scaleMode);
  const scaleY = (value: number) => h - (((value - min) / range) * (h - padding * 2) + padding);
  const points = data.map((value, index) => {
    const x = (index / Math.max(data.length - 1, 1)) * w;
    const y = scaleY(value);
    return `${x},${y}`;
  });
  const line = points.join(' ');
  const areaPoints = `0,${h} ${line} ${w},${h}`;

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-full w-full" preserveAspectRatio="none">
      <defs>
        <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#00d4aa" stopOpacity="0.15" />
          <stop offset="100%" stopColor="#00d4aa" stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={areaPoints} fill="url(#eqGrad)" />
      <polyline points={line} fill="none" stroke="#00d4aa" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function toActivityEntry(message: WSMessage): ActivityEntry | null {
  const data = (message.data ?? {}) as Record<string, unknown>;
  const now = message.timestamp ?? new Date().toISOString();

  if (message.type === 'paper_trade') {
    return {
      id: `trade-${now}-${String(data.market_id ?? 'market')}`,
      time: formatTime(now),
      level: 'info',
      msg: `Paper trade ${String(data.side ?? '').toUpperCase()} ${String(data.market_id ?? '')} @ ${formatCurrency(Number(data.price ?? 0))}`,
    };
  }

  if (message.type === 'paper_signal') {
    const decision = String(data.decision ?? 'HOLD').toUpperCase();
    return {
      id: `signal-${now}-${String(data.market_id ?? 'market')}`,
      time: formatTime(now),
      level: decision === 'HOLD' ? 'info' : 'warn',
      msg: `Signal ${String(data.market_id ?? '')} ${decision} (${formatNumber(Number(data.confidence ?? 0), 1)}%)`,
    };
  }

  if (message.type === 'status_update') {
    return {
      id: `status-${now}`,
      time: formatTime(now),
      level: 'info',
      msg: `Live feed ${Boolean(data.is_running) ? 'running' : 'idle'} across ${Number(data.connected_markets_count ?? 0)} markets`,
    };
  }

  return null;
}

export default function Overview() {
  const { data: marketResponse, isLoading: marketsLoading } = useApi<MarketRecord[]>('/markets', { pollInterval: 5000 });
  const { data: portfolioResponse, isLoading: portfolioLoading } = useApi<PortfolioRecord>('/paper/portfolio', { pollInterval: 3000 });
  const { data: tradesResponse } = useApi<TradeRecord[]>('/trades', { pollInterval: 5000 });

  const [liveMarkets, setLiveMarkets] = useState<Record<string, Partial<MarketRecord>>>({});
  const [priceHistory, setPriceHistory] = useState<Record<string, number[]>>({});
  const [latestSignals, setLatestSignals] = useState<Record<string, SignalRecord>>({});
  const [livePortfolio, setLivePortfolio] = useState<Partial<PortfolioRecord> | null>(null);
  const [equityHistory, setEquityHistory] = useState<number[]>([]);
  const [activityEntries, setActivityEntries] = useState<ActivityEntry[]>([]);
  const [equityScaleMode, setEquityScaleMode] = useState<EquityScaleMode>('balanced');
  const activitySequenceRef = useRef(0);

  const { isConnected } = useWebSocket(undefined, {
    onMessage: (message) => {
      const data = (message.data ?? {}) as Record<string, unknown>;

      if (message.type === 'market_update') {
        const marketId = String(data.symbol ?? '');
        if (marketId) {
          const price = Number(data.price ?? 0);
          setLiveMarkets((current) => ({
            ...current,
            [marketId]: {
              market_id: marketId,
              question: marketId.replace('USDT', ''),
              mid: price,
              change_24h_pct: Number(data.change_24h_pct ?? 0),
              volume_24h: Number(data.volume_24h ?? 0),
            },
          }));
          setPriceHistory((current) => ({
            ...current,
            [marketId]: [...(current[marketId] ?? []), price].filter((entry) => entry > 0).slice(-15),
          }));
        }
      }

      if (message.type === 'paper_signal') {
        const marketId = String(data.market_id ?? '');
        if (marketId) {
          setLatestSignals((current) => ({
            ...current,
            [marketId]: {
              market_id: marketId,
              decision: String(data.decision ?? 'HOLD'),
              confidence: Number(data.confidence ?? 0),
              edge: Number(data.edge ?? 0),
              predicted_price: data.predicted_price == null ? null : Number(data.predicted_price),
              current_mid: data.current_mid == null ? null : Number(data.current_mid),
              strategy: String(data.strategy ?? 'ai'),
              reason: String(data.reason ?? ''),
            },
          }));
        }
      }

      if (message.type === 'paper_portfolio') {
        const totalEquity = Number(data.total_equity ?? 0);
        setLivePortfolio((current) => ({
          ...(current ?? {}),
          total_equity: totalEquity,
          total_pnl: Number(data.total_pnl ?? 0),
          total_pnl_pct: Number(data.total_pnl_pct ?? 0),
        }));
        if (totalEquity > 0) {
          setEquityHistory((current) => [...current, totalEquity].slice(-25));
        }
      }

      const entry = toActivityEntry(message);
      if (entry) {
        activitySequenceRef.current += 1;
        const uniqueEntry = {
          ...entry,
          id: `${entry.id}-${activitySequenceRef.current}`,
        };
        setActivityEntries((current) => [uniqueEntry, ...current].slice(0, 20));
      }
    },
  });

  const markets = useMemo(() => {
    const baseMarkets = marketResponse ?? [];
    return baseMarkets.map((market) => ({
      ...market,
      ...liveMarkets[market.market_id],
    }));
  }, [liveMarkets, marketResponse]);

  const portfolio = useMemo(() => {
    if (!portfolioResponse) {
      return null;
    }
    return {
      ...portfolioResponse,
      ...livePortfolio,
    };
  }, [livePortfolio, portfolioResponse]);

  const positions = useMemo(() => {
    if (!portfolio?.positions) {
      return [];
    }
    const totalEquity = portfolio.total_equity || 1;
    return Object.entries(portfolio.positions).map(([symbol, position]) => ({
      symbol,
      value: position.market_value,
      pnl: position.unrealized_pnl + (position.realized_pnl ?? 0),
      allocation: totalEquity > 0 ? (position.market_value / totalEquity) * 100 : 0,
    }));
  }, [portfolio]);

  const topMovers = useMemo(
    () =>
      [...markets]
        .sort((left, right) => Math.abs(right.change_24h_pct) - Math.abs(left.change_24h_pct))
        .slice(0, 5),
    [markets],
  );

  const signals = useMemo(
    () =>
      Object.values(latestSignals)
        .filter((signal) => signal.decision.toUpperCase() !== 'HOLD')
        .sort((left, right) => right.confidence - left.confidence)
        .slice(0, 5),
    [latestSignals],
  );

  const trades = useMemo(() => (tradesResponse ?? []).slice(0, 6), [tradesResponse]);
  const chartData = equityHistory.length > 0
    ? equityHistory
    : portfolioResponse?.total_equity
      ? Array.from({ length: 25 }, () => portfolioResponse.total_equity)
      : [0, 0];
  const activeModels = signals.length > 0 ? signals.length : isConnected ? 1 : 0;
  const winRate = trades.length > 0
    ? (trades.filter((trade) => (trade.pnl ?? 0) >= 0).length / trades.length) * 100
    : 0;

  return (
    <div className="space-y-4 animate-slide-up">
      <div className="grid grid-cols-4 gap-3">
        <Card>
          <CardBody className="flex items-start gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent/10">
              <DollarSign size={14} className="text-accent" />
            </div>
            <StatValue
              label="Portfolio Value"
              value={formatCurrency(portfolio?.total_equity ?? 0)}
              change={portfolio?.total_pnl_pct ?? 0}
              sub={portfolioLoading ? 'syncing' : 'live'}
            />
          </CardBody>
        </Card>
        <Card>
          <CardBody className="flex items-start gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-profit/10">
              <TrendingUp size={14} className="text-profit" />
            </div>
            <StatValue
              label="Total P&L"
              value={formatCurrency(portfolio?.total_pnl ?? 0)}
              change={portfolio?.total_pnl_pct ?? 0}
              sub="paper"
            />
          </CardBody>
        </Card>
        <Card>
          <CardBody className="flex items-start gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-info/10">
              <Activity size={14} className="text-info" />
            </div>
            <StatValue label="Active Models" value={String(activeModels)} sub={isConnected ? 'websocket live' : 'waiting for feed'} />
          </CardBody>
        </Card>
        <Card>
          <CardBody className="flex items-start gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-warn/10">
              <BarChart3 size={14} className="text-warn" />
            </div>
            <StatValue label="Win Rate" value={`${formatNumber(winRate, 1)}%`} sub="recent trades" />
          </CardBody>
        </Card>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Card className="col-span-2">
          <CardHeader>
            <CardTitle>Equity Curve</CardTitle>
            <div className="flex items-center gap-2">
              <Badge variant="accent">Paper</Badge>
              <Chip active={equityScaleMode === 'tight'} onClick={() => setEquityScaleMode('tight')}>Tight</Chip>
              <Chip active={equityScaleMode === 'balanced'} onClick={() => setEquityScaleMode('balanced')}>Balanced</Chip>
              <Chip active={equityScaleMode === 'full'} onClick={() => setEquityScaleMode('full')}>Full</Chip>
              <span className="text-[10px] font-mono text-text-muted">{chartData.length} data points</span>
            </div>
          </CardHeader>
          <CardBody className="p-2">
            <div className="h-[140px]">
              <EquityChart data={chartData} scaleMode={equityScaleMode} />
            </div>
            <div className="mt-1 flex justify-between px-2">
              <span className="text-[9px] font-mono text-text-muted">start</span>
              <span className="text-[9px] font-mono text-text-muted">now</span>
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Positions</CardTitle>
            <Badge>{positions.length} assets</Badge>
          </CardHeader>
          <CardBody className="p-0">
            <div className="max-h-[190px] divide-y divide-border overflow-y-auto">
              {positions.length > 0 ? positions.map((position) => (
                <div key={position.symbol} className="flex items-center justify-between px-4 py-2.5 transition-colors hover:bg-bg-hover">
                  <div className="flex items-center gap-2.5">
                    <span className="text-xs font-mono font-semibold text-text-primary">{position.symbol}</span>
                    <span className="text-[10px] font-mono text-text-muted">{formatNumber(position.allocation, 1)}%</span>
                  </div>
                  <div className="text-right">
                    <p className="text-xs font-mono tabular-nums text-text-primary">{formatCurrency(position.value)}</p>
                    <p className={cn('text-[10px] font-mono tabular-nums', position.pnl >= 0 ? 'text-profit' : 'text-loss')}>
                      {position.pnl >= 0 ? '+' : ''}{formatCurrency(position.pnl)}
                    </p>
                  </div>
                </div>
              )) : (
                <div className="px-4 py-6 text-center text-[11px] font-mono text-text-muted">
                  {portfolioLoading ? 'Loading portfolio...' : 'No open positions'}
                </div>
              )}
            </div>
          </CardBody>
        </Card>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Card>
          <CardHeader>
            <CardTitle>Top Movers</CardTitle>
            <Badge variant="info">24h</Badge>
          </CardHeader>
          <CardBody className="p-0">
            <div className="divide-y divide-border">
              {topMovers.length > 0 ? topMovers.map((asset) => (
                <div key={asset.market_id} className="flex items-center justify-between px-4 py-2.5 transition-colors hover:bg-bg-hover">
                  <div className="flex items-center gap-2.5">
                    <span className="text-xs font-mono font-semibold text-text-primary">{asset.market_id.replace('USDT', '')}</span>
                    <MiniSparkline
                      data={buildSparkline(priceHistory[asset.market_id] ?? [], asset.mid)}
                      color={asset.change_24h_pct >= 0 ? 'profit' : 'loss'}
                      width={50}
                      height={16}
                    />
                  </div>
                  <div className="text-right">
                    <p className="text-xs font-mono tabular-nums text-text-primary">{formatCurrency(asset.mid)}</p>
                    <p className={cn('text-[10px] font-mono tabular-nums', asset.change_24h_pct >= 0 ? 'text-profit' : 'text-loss')}>
                      {asset.change_24h_pct >= 0 ? '+' : ''}{formatNumber(asset.change_24h_pct)}%
                    </p>
                  </div>
                </div>
              )) : (
                <div className="px-4 py-6 text-center text-[11px] font-mono text-text-muted">
                  {marketsLoading ? 'Loading markets...' : 'No market data yet'}
                </div>
              )}
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>AI Signals</CardTitle>
            <Badge variant={isConnected ? 'accent' : 'warning'}>{isConnected ? 'Live' : 'Stale'}</Badge>
          </CardHeader>
          <CardBody className="p-0">
            <div className="divide-y divide-border">
              {signals.length > 0 ? signals.map((signal) => (
                <div key={signal.market_id} className="flex items-center justify-between px-4 py-2.5 transition-colors hover:bg-bg-hover">
                  <div className="flex items-center gap-2.5">
                    <span className="text-xs font-mono font-semibold text-text-primary">{signal.market_id.replace('USDT', '')}</span>
                    <Badge variant={signal.decision.toUpperCase() === 'BUY' ? 'success' : 'danger'}>
                      {signal.decision.toUpperCase()}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-2">
                    <ProgressBar value={signal.confidence} color={signal.confidence > 75 ? 'accent' : 'warn'} className="w-12" />
                    <span className="w-7 text-right text-[10px] font-mono tabular-nums text-text-secondary">
                      {formatNumber(signal.confidence, 0)}%
                    </span>
                  </div>
                </div>
              )) : (
                <div className="px-4 py-6 text-center text-[11px] font-mono text-text-muted">
                  Waiting for prediction events
                </div>
              )}
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Activity Log</CardTitle>
            <div className={cn('h-1.5 w-1.5 rounded-full', isConnected ? 'bg-accent pulse-dot' : 'bg-warn')} />
          </CardHeader>
          <CardBody className="p-0">
            <div className="max-h-[195px] divide-y divide-border overflow-y-auto">
              {activityEntries.length > 0 ? activityEntries.map((entry) => (
                <div key={entry.id} className="px-4 py-2 transition-colors hover:bg-bg-hover">
                  <div className="mb-0.5 flex items-center gap-2">
                    <span className="text-[9px] font-mono text-text-muted">{entry.time}</span>
                    {entry.level !== 'info' ? <AlertTriangle size={9} className={entry.level === 'error' ? 'text-loss' : 'text-warn'} /> : null}
                  </div>
                  <p className="text-[11px] font-mono leading-tight text-text-secondary">{entry.msg}</p>
                </div>
              )) : (
                <div className="px-4 py-6 text-center text-[11px] font-mono text-text-muted">
                  Waiting for websocket events
                </div>
              )}
            </div>
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent Trades</CardTitle>
          <span className="text-[10px] font-mono text-text-muted">{trades.length} trades loaded</span>
        </CardHeader>
        <CardBody className="p-0">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border text-[10px] uppercase tracking-wider text-text-muted">
                <th className="px-4 py-2 text-left font-medium">ID</th>
                <th className="px-4 py-2 text-left font-medium">Pair</th>
                <th className="px-4 py-2 text-left font-medium">Side</th>
                <th className="px-4 py-2 text-right font-medium">Price</th>
                <th className="px-4 py-2 text-right font-medium">Amount</th>
                <th className="px-4 py-2 text-right font-medium">Total</th>
                <th className="px-4 py-2 text-left font-medium">Time</th>
                <th className="px-4 py-2 text-left font-medium">Status</th>
                <th className="px-4 py-2 text-right font-medium">P&L</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {trades.length > 0 ? trades.map((trade) => (
                <tr key={trade.id} className="transition-colors hover:bg-bg-hover">
                  <td className="px-4 py-2 font-mono text-text-muted">{trade.id}</td>
                  <td className="px-4 py-2 font-mono font-medium text-text-primary">{trade.market_id.replace('USDT', '/USDT')}</td>
                  <td className="px-4 py-2">
                    <Badge variant={trade.action.includes('BUY') ? 'success' : 'danger'}>
                      {trade.action.includes('BUY') ? 'BUY' : 'SELL'}
                    </Badge>
                  </td>
                  <td className="px-4 py-2 text-right font-mono tabular-nums text-text-primary">{formatCurrency(trade.price)}</td>
                  <td className="px-4 py-2 text-right font-mono tabular-nums text-text-secondary">{formatNumber(trade.size, 4)}</td>
                  <td className="px-4 py-2 text-right font-mono tabular-nums text-text-primary">{formatCurrency(trade.price * trade.size)}</td>
                  <td className="px-4 py-2 font-mono text-text-muted">{formatTime(trade.timestamp)}</td>
                  <td className="px-4 py-2">
                    <Badge variant="accent">filled</Badge>
                  </td>
                  <td className={cn(
                    'px-4 py-2 text-right font-mono tabular-nums',
                    trade.pnl == null ? 'text-text-muted' : trade.pnl >= 0 ? 'text-profit' : 'text-loss',
                  )}>
                    {trade.pnl == null ? '--' : `${trade.pnl >= 0 ? '+' : ''}${formatCurrency(trade.pnl)}`}
                  </td>
                </tr>
              )) : (
                <tr>
                  <td colSpan={9} className="px-4 py-6 text-center text-[11px] font-mono text-text-muted">
                    No live trades yet
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </CardBody>
      </Card>
    </div>
  );
}
