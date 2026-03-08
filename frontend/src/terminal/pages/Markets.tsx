'use client';

import { useMemo, useState } from 'react';
import { Search, ArrowUpDown } from 'lucide-react';
import { useApi } from '@/hooks/useApi';
import { useWebSocket } from '@/hooks/useWebSocket';
import { Card, CardHeader, CardTitle, CardBody, Badge, MiniSparkline, Chip } from '../components/UI';
import { cn } from '../utils/cn';

type SortKey = 'symbol' | 'price' | 'change24h' | 'volume' | 'confidence';

type MarketResponse = {
  market_id: string;
  question: string;
  mid: number;
  change_24h_pct: number;
  volume_24h: number;
};

type SignalResponse = {
  market_id: string;
  decision: string;
  confidence: number;
};

type MarketView = {
  symbol: string;
  name: string;
  marketId: string;
  price: number;
  change24h: number;
  volume: number;
  sparkline: number[];
  signal: 'long' | 'short' | 'neutral';
  confidence: number;
};

type SortHeaderProps = {
  label: string;
  field: SortKey;
  className?: string;
  activeSortKey: SortKey;
  onToggleSort: (key: SortKey) => void;
};

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  }).format(Number.isFinite(value) ? value : 0);
}

function formatCompactNumber(value: number): string {
  return new Intl.NumberFormat('en-US', {
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(Number.isFinite(value) ? value : 0);
}

function buildSparkline(history: number[], fallback: number): number[] {
  if (history.length >= 2) {
    return history.slice(-15);
  }
  const base = fallback > 0 ? fallback : 1;
  return Array.from({ length: 15 }, (_, index) => base * (1 + index * 0.0004));
}

function SortHeader({ label, field, className, activeSortKey, onToggleSort }: SortHeaderProps) {
  return (
    <th
      className={cn('cursor-pointer select-none px-4 py-2.5 font-medium transition-colors hover:text-text-primary', className)}
      onClick={() => onToggleSort(field)}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        <ArrowUpDown size={9} className={cn(activeSortKey === field ? 'text-accent' : 'opacity-30')} />
      </span>
    </th>
  );
}

export default function Markets() {
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<'all' | 'long' | 'short' | 'neutral'>('all');
  const [sortKey, setSortKey] = useState<SortKey>('symbol');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [liveSignals, setLiveSignals] = useState<Record<string, SignalResponse>>({});
  const [priceHistory, setPriceHistory] = useState<Record<string, number[]>>({});
  const [marketOverrides, setMarketOverrides] = useState<Record<string, Partial<MarketResponse>>>({});

  const { data: marketResponse, isLoading } = useApi<MarketResponse[]>('/markets', { pollInterval: 5000 });
  const { isConnected } = useWebSocket(undefined, {
    onMessage: (message) => {
      const data = (message.data ?? {}) as Record<string, unknown>;
      if (message.type === 'market_update') {
        const symbol = String(data.symbol ?? '');
        const price = Number(data.price ?? 0);
        if (symbol) {
          setMarketOverrides((current) => ({
            ...current,
            [symbol]: {
              market_id: symbol,
              question: symbol.replace('USDT', ''),
              mid: price,
              change_24h_pct: Number(data.change_24h_pct ?? 0),
              volume_24h: Number(data.volume_24h ?? 0),
            },
          }));
          setPriceHistory((current) => ({
            ...current,
            [symbol]: [...(current[symbol] ?? []), price].filter((entry) => entry > 0).slice(-15),
          }));
        }
      }

      if (message.type === 'paper_signal') {
        const symbol = String(data.market_id ?? '');
        if (symbol) {
          const decision = String(data.decision ?? 'HOLD').toUpperCase();
          setLiveSignals((current) => ({
            ...current,
            [symbol]: {
              market_id: symbol,
              decision,
              confidence: Number(data.confidence ?? 0),
            },
          }));
        }
      }
    },
  });

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((current) => (current === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const marketRows = useMemo<MarketView[]>(() => {
    return (marketResponse ?? []).map((market) => {
      const merged = {
        ...market,
        ...marketOverrides[market.market_id],
      };
      const signal = liveSignals[market.market_id];
      const decision = signal?.decision ?? 'HOLD';
      return {
        symbol: merged.market_id.replace('USDT', ''),
        name: merged.question,
        marketId: merged.market_id,
        price: merged.mid,
        change24h: merged.change_24h_pct,
        volume: merged.volume_24h,
        sparkline: buildSparkline(priceHistory[merged.market_id] ?? [], merged.mid),
        signal:
          decision === 'BUY' ? 'long' :
          decision === 'SELL' ? 'short' :
          'neutral',
        confidence: signal?.confidence ?? 0,
      };
    });
  }, [liveSignals, marketOverrides, marketResponse, priceHistory]);

  const filtered = useMemo(() => {
    return [...marketRows]
      .filter((asset) => filter === 'all' || asset.signal === filter)
      .filter((asset) => asset.symbol.toLowerCase().includes(search.toLowerCase()) || asset.name.toLowerCase().includes(search.toLowerCase()))
      .sort((left, right) => {
        const direction = sortDir === 'asc' ? 1 : -1;
        if (sortKey === 'symbol') {
          return left.symbol.localeCompare(right.symbol) * direction;
        }
        if (sortKey === 'price') {
          return (left.price - right.price) * direction;
        }
        if (sortKey === 'change24h') {
          return (left.change24h - right.change24h) * direction;
        }
        if (sortKey === 'volume') {
          return (left.volume - right.volume) * direction;
        }
        return (left.confidence - right.confidence) * direction;
      });
  }, [filter, marketRows, search, sortDir, sortKey]);

  const avgConfidence = marketRows.length > 0
    ? marketRows.reduce((sum, asset) => sum + asset.confidence, 0) / marketRows.length
    : 0;
  const topGainer = useMemo(
    () => [...marketRows].sort((left, right) => right.change24h - left.change24h)[0] ?? null,
    [marketRows],
  );
  const topLoser = useMemo(
    () => [...marketRows].sort((left, right) => left.change24h - right.change24h)[0] ?? null,
    [marketRows],
  );
  const highestVolume = useMemo(
    () => [...marketRows].sort((left, right) => right.volume - left.volume)[0] ?? null,
    [marketRows],
  );
  const convictionList = useMemo(
    () => [...marketRows].filter((asset) => asset.confidence > 0).sort((left, right) => right.confidence - left.confidence).slice(0, 4),
    [marketRows],
  );
  const moverList = useMemo(
    () => [...marketRows].sort((left, right) => Math.abs(right.change24h) - Math.abs(left.change24h)).slice(0, 4),
    [marketRows],
  );

  return (
    <div className="space-y-4 animate-slide-up">
      <div className="grid grid-cols-4 gap-3">
        <Card>
          <CardBody>
            <p className="mb-1 text-[10px] font-medium uppercase tracking-wider text-text-muted">Total Assets</p>
            <p className="text-xl font-mono font-semibold text-text-primary">{marketRows.length}</p>
          </CardBody>
        </Card>
        <Card>
          <CardBody>
            <p className="mb-1 text-[10px] font-medium uppercase tracking-wider text-text-muted">Long Signals</p>
            <p className="text-xl font-mono font-semibold text-profit">{marketRows.filter((asset) => asset.signal === 'long').length}</p>
          </CardBody>
        </Card>
        <Card>
          <CardBody>
            <p className="mb-1 text-[10px] font-medium uppercase tracking-wider text-text-muted">Short Signals</p>
            <p className="text-xl font-mono font-semibold text-loss">{marketRows.filter((asset) => asset.signal === 'short').length}</p>
          </CardBody>
        </Card>
        <Card>
          <CardBody>
            <p className="mb-1 text-[10px] font-medium uppercase tracking-wider text-text-muted">Avg Confidence</p>
            <p className="text-xl font-mono font-semibold text-accent">{avgConfidence.toFixed(1)}%</p>
          </CardBody>
        </Card>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Card>
          <CardHeader>
            <CardTitle>Top Gainer</CardTitle>
            <Badge variant="success">{topGainer?.symbol ?? '--'}</Badge>
          </CardHeader>
          <CardBody className="space-y-2">
            <div className="text-lg font-mono font-semibold text-text-primary">
              {topGainer ? formatCurrency(topGainer.price) : '--'}
            </div>
            <div className="flex items-center justify-between text-[11px] text-text-muted">
              <span>24h move</span>
              <span className="font-mono text-profit">
                {topGainer ? `${topGainer.change24h >= 0 ? '+' : ''}${topGainer.change24h.toFixed(2)}%` : '--'}
              </span>
            </div>
            <div className="flex items-center justify-between text-[11px] text-text-muted">
              <span>Signal</span>
              <span className="font-mono text-text-primary">{topGainer?.signal.toUpperCase() ?? '--'}</span>
            </div>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Top Loser</CardTitle>
            <Badge variant="danger">{topLoser?.symbol ?? '--'}</Badge>
          </CardHeader>
          <CardBody className="space-y-2">
            <div className="text-lg font-mono font-semibold text-text-primary">
              {topLoser ? formatCurrency(topLoser.price) : '--'}
            </div>
            <div className="flex items-center justify-between text-[11px] text-text-muted">
              <span>24h move</span>
              <span className="font-mono text-loss">
                {topLoser ? `${topLoser.change24h >= 0 ? '+' : ''}${topLoser.change24h.toFixed(2)}%` : '--'}
              </span>
            </div>
            <div className="flex items-center justify-between text-[11px] text-text-muted">
              <span>Signal</span>
              <span className="font-mono text-text-primary">{topLoser?.signal.toUpperCase() ?? '--'}</span>
            </div>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Highest Volume</CardTitle>
            <Badge variant="info">{highestVolume?.symbol ?? '--'}</Badge>
          </CardHeader>
          <CardBody className="space-y-2">
            <div className="text-lg font-mono font-semibold text-text-primary">
              {highestVolume ? formatCompactNumber(highestVolume.volume) : '--'}
            </div>
            <div className="flex items-center justify-between text-[11px] text-text-muted">
              <span>Price</span>
              <span className="font-mono text-text-primary">{highestVolume ? formatCurrency(highestVolume.price) : '--'}</span>
            </div>
            <div className="flex items-center justify-between text-[11px] text-text-muted">
              <span>Feed</span>
              <span className="font-mono text-text-primary">{isConnected ? 'websocket' : 'polling'}</span>
            </div>
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <CardTitle>Market Data</CardTitle>
            <div className="flex items-center gap-1.5">
              <Chip active={filter === 'all'} onClick={() => setFilter('all')}>All</Chip>
              <Chip active={filter === 'long'} onClick={() => setFilter('long')}>Long</Chip>
              <Chip active={filter === 'short'} onClick={() => setFilter('short')}>Short</Chip>
              <Chip active={filter === 'neutral'} onClick={() => setFilter('neutral')}>Neutral</Chip>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Badge variant={isConnected ? 'accent' : 'warning'}>{isConnected ? 'Live Feed' : 'Stale Feed'}</Badge>
            <div className="relative">
              <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted" />
              <input
                type="text"
                placeholder="Search..."
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                className="w-40 rounded border border-border bg-bg-tertiary py-1.5 pl-7 pr-3 text-xs font-mono text-text-primary placeholder:text-text-muted focus:border-accent/50 focus:outline-none"
              />
            </div>
          </div>
        </CardHeader>
        <CardBody className="p-0">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border text-[10px] uppercase tracking-wider text-text-muted">
                <SortHeader label="Asset" field="symbol" className="text-left" activeSortKey={sortKey} onToggleSort={toggleSort} />
                <SortHeader label="Price" field="price" className="text-right" activeSortKey={sortKey} onToggleSort={toggleSort} />
                <SortHeader label="24h Change" field="change24h" className="text-right" activeSortKey={sortKey} onToggleSort={toggleSort} />
                <th className="px-4 py-2.5 text-center font-medium">Trend</th>
                <SortHeader label="Volume" field="volume" className="text-right" activeSortKey={sortKey} onToggleSort={toggleSort} />
                <th className="px-4 py-2.5 text-left font-medium">Market</th>
                <th className="px-4 py-2.5 text-left font-medium">Signal</th>
                <SortHeader label="Confidence" field="confidence" className="text-right" activeSortKey={sortKey} onToggleSort={toggleSort} />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filtered.length > 0 ? filtered.map((asset) => (
                <tr key={asset.symbol} className="transition-colors hover:bg-bg-hover">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-semibold text-text-primary">{asset.symbol}</span>
                      <span className="text-[10px] text-text-muted">{asset.name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right font-mono tabular-nums text-text-primary">{formatCurrency(asset.price)}</td>
                  <td className={cn('px-4 py-3 text-right font-mono tabular-nums', asset.change24h >= 0 ? 'text-profit' : 'text-loss')}>
                    {asset.change24h >= 0 ? '+' : ''}{asset.change24h.toFixed(2)}%
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-center">
                      <MiniSparkline data={asset.sparkline} color={asset.change24h >= 0 ? 'profit' : 'loss'} width={60} height={20} />
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right font-mono tabular-nums text-text-secondary">{formatCompactNumber(asset.volume)}</td>
                  <td className="px-4 py-3 font-mono text-text-secondary">{isConnected ? 'websocket' : 'polling'}</td>
                  <td className="px-4 py-3">
                    <Badge variant={asset.signal === 'long' ? 'success' : asset.signal === 'short' ? 'danger' : 'default'}>
                      {asset.signal === 'long' ? 'LONG' : asset.signal === 'short' ? 'SHORT' : 'NEUTRAL'}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-2">
                      <div className="h-1 w-16 overflow-hidden rounded-full bg-bg-tertiary">
                        <div
                          className={cn('h-full rounded-full', asset.confidence > 75 ? 'bg-accent' : asset.confidence > 50 ? 'bg-warn' : 'bg-loss')}
                          style={{ width: `${asset.confidence}%` }}
                        />
                      </div>
                      <span className="w-7 text-right font-mono tabular-nums text-text-secondary">{asset.confidence.toFixed(0)}%</span>
                    </div>
                  </td>
                </tr>
              )) : (
                <tr>
                  <td colSpan={8} className="px-4 py-6 text-center text-[11px] font-mono text-text-muted">
                    {isLoading ? 'Loading live markets...' : 'No markets matched the current filters'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </CardBody>
      </Card>

      <div className="grid grid-cols-2 gap-3">
        <Card>
          <CardHeader>
            <CardTitle>High Conviction</CardTitle>
            <Badge variant="accent">{convictionList.length}</Badge>
          </CardHeader>
          <CardBody className="space-y-2">
            {convictionList.map((asset) => (
              <div key={`conviction-${asset.marketId}`} className="flex items-center justify-between border-b border-border/40 pb-2 text-[11px] last:border-b-0 last:pb-0">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-text-primary">{asset.symbol}</span>
                  <Badge variant={asset.signal === 'long' ? 'success' : asset.signal === 'short' ? 'danger' : 'default'}>
                    {asset.signal.toUpperCase()}
                  </Badge>
                </div>
                <div className="text-right">
                  <div className="font-mono text-text-primary">{asset.confidence.toFixed(0)}%</div>
                  <div className={cn('font-mono text-[10px]', asset.change24h >= 0 ? 'text-profit' : 'text-loss')}>
                    {asset.change24h >= 0 ? '+' : ''}{asset.change24h.toFixed(2)}%
                  </div>
                </div>
              </div>
            ))}
            {convictionList.length === 0 ? <div className="text-[11px] text-text-muted">No active signal confidence yet.</div> : null}
          </CardBody>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Fast Movers</CardTitle>
            <Badge variant="warning">{moverList.length}</Badge>
          </CardHeader>
          <CardBody className="space-y-2">
            {moverList.map((asset) => (
              <div key={`mover-${asset.marketId}`} className="flex items-center justify-between border-b border-border/40 pb-2 text-[11px] last:border-b-0 last:pb-0">
                <div>
                  <div className="font-mono text-text-primary">{asset.symbol}</div>
                  <div className="text-text-muted">{formatCurrency(asset.price)}</div>
                </div>
                <div className="flex items-center gap-3">
                  <MiniSparkline data={asset.sparkline} color={asset.change24h >= 0 ? 'profit' : 'loss'} width={48} height={16} />
                  <div className={cn('font-mono text-right', asset.change24h >= 0 ? 'text-profit' : 'text-loss')}>
                    {asset.change24h >= 0 ? '+' : ''}{asset.change24h.toFixed(2)}%
                  </div>
                </div>
              </div>
            ))}
            {moverList.length === 0 ? <div className="text-[11px] text-text-muted">No mover data available yet.</div> : null}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
