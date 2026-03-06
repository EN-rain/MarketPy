import { useState } from 'react';
import { Search, ArrowUpDown } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardBody, Badge, MiniSparkline, Chip } from '../components/UI';
import { cryptoAssets, formatCurrency } from '../data/mock';
import { cn } from '../utils/cn';

type SortKey = 'symbol' | 'price' | 'change24h' | 'volume' | 'confidence';

type SortHeaderProps = {
  label: string;
  field: SortKey;
  className?: string;
  activeSortKey: SortKey;
  onToggleSort: (key: SortKey) => void;
};

function SortHeader({ label, field, className, activeSortKey, onToggleSort }: SortHeaderProps) {
  return (
    <th
      className={cn('px-4 py-2.5 font-medium cursor-pointer hover:text-text-primary transition-colors select-none', className)}
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

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(d => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const filtered = cryptoAssets
    .filter(a => filter === 'all' || a.signal === filter)
    .filter(a => a.symbol.toLowerCase().includes(search.toLowerCase()) || a.name.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => {
      const dir = sortDir === 'asc' ? 1 : -1;
      if (sortKey === 'symbol') return a.symbol.localeCompare(b.symbol) * dir;
      return ((a[sortKey] as number) - (b[sortKey] as number)) * dir;
    });

  return (
    <div className="space-y-4 animate-slide-up">
      <div className="grid grid-cols-4 gap-3">
        <Card>
          <CardBody>
            <p className="text-[10px] uppercase tracking-wider text-text-muted font-medium mb-1">Total Assets</p>
            <p className="text-xl font-mono font-semibold text-text-primary">{cryptoAssets.length}</p>
          </CardBody>
        </Card>
        <Card>
          <CardBody>
            <p className="text-[10px] uppercase tracking-wider text-text-muted font-medium mb-1">Long Signals</p>
            <p className="text-xl font-mono font-semibold text-profit">{cryptoAssets.filter(a => a.signal === 'long').length}</p>
          </CardBody>
        </Card>
        <Card>
          <CardBody>
            <p className="text-[10px] uppercase tracking-wider text-text-muted font-medium mb-1">Short Signals</p>
            <p className="text-xl font-mono font-semibold text-loss">{cryptoAssets.filter(a => a.signal === 'short').length}</p>
          </CardBody>
        </Card>
        <Card>
          <CardBody>
            <p className="text-[10px] uppercase tracking-wider text-text-muted font-medium mb-1">Avg Confidence</p>
            <p className="text-xl font-mono font-semibold text-accent">
              {(cryptoAssets.reduce((s, a) => s + a.confidence, 0) / cryptoAssets.length).toFixed(1)}%
            </p>
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
          <div className="relative">
            <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted" />
            <input
              type="text"
              placeholder="Search..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="bg-bg-tertiary border border-border rounded text-xs pl-7 pr-3 py-1.5 text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent/50 w-40 font-mono"
            />
          </div>
        </CardHeader>
        <CardBody className="p-0">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border text-[10px] uppercase tracking-wider text-text-muted">
                <SortHeader label="Asset" field="symbol" className="text-left" activeSortKey={sortKey} onToggleSort={toggleSort} />
                <SortHeader label="Price" field="price" className="text-right" activeSortKey={sortKey} onToggleSort={toggleSort} />
                <SortHeader label="24h Change" field="change24h" className="text-right" activeSortKey={sortKey} onToggleSort={toggleSort} />
                <th className="text-center px-4 py-2.5 font-medium">Trend</th>
                <SortHeader label="Volume" field="volume" className="text-right" activeSortKey={sortKey} onToggleSort={toggleSort} />
                <th className="text-left px-4 py-2.5 font-medium">Market Cap</th>
                <th className="text-left px-4 py-2.5 font-medium">Signal</th>
                <SortHeader label="Confidence" field="confidence" className="text-right" activeSortKey={sortKey} onToggleSort={toggleSort} />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filtered.map(asset => (
                <tr key={asset.symbol} className="hover:bg-bg-hover transition-colors">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-semibold text-text-primary">{asset.symbol}</span>
                      <span className="text-text-muted text-[10px]">{asset.name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 font-mono text-right text-text-primary tabular-nums">{formatCurrency(asset.price)}</td>
                  <td className={cn('px-4 py-3 font-mono text-right tabular-nums', asset.change24h >= 0 ? 'text-profit' : 'text-loss')}>
                    {asset.change24h >= 0 ? '+' : ''}{asset.change24h.toFixed(2)}%
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-center">
                      <MiniSparkline data={asset.sparkline} color={asset.change24h >= 0 ? 'profit' : 'loss'} width={60} height={20} />
                    </div>
                  </td>
                  <td className="px-4 py-3 font-mono text-right text-text-secondary tabular-nums">{asset.volume}</td>
                  <td className="px-4 py-3 font-mono text-text-secondary">{asset.marketCap}</td>
                  <td className="px-4 py-3">
                    <Badge variant={asset.signal === 'long' ? 'success' : asset.signal === 'short' ? 'danger' : 'default'}>
                      {asset.signal === 'long' ? 'LONG' : asset.signal === 'short' ? 'SHORT' : 'NEUTRAL'}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-2">
                      <div className="w-16 h-1 rounded-full bg-bg-tertiary overflow-hidden">
                        <div
                          className={cn('h-full rounded-full', asset.confidence > 75 ? 'bg-accent' : asset.confidence > 50 ? 'bg-warn' : 'bg-loss')}
                          style={{ width: `${asset.confidence}%` }}
                        />
                      </div>
                      <span className="font-mono text-text-secondary tabular-nums w-7 text-right">{asset.confidence}%</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardBody>
      </Card>
    </div>
  );
}
