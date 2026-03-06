import { HardDrive, RefreshCw, Download, Trash2 } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardBody, Badge, ProgressBar, Chip } from '../components/UI';
import { useEffect, useState } from 'react';
import { cn } from '../utils/cn';
import { formatRelativeTime } from '../utils/time';

interface DatasetInfo {
  id: string;
  name: string;
  type: 'ohlcv' | 'orderbook' | 'social' | 'onchain';
  symbol: string;
  interval: string;
  rows: string;
  size: string;
  lastUpdatedAt: number;
  status: 'synced' | 'syncing' | 'stale';
  coverage: string;
}

const now = Date.now();
const datasets: DatasetInfo[] = [
  { id: 'DS-001', name: 'btc_1m_2y', type: 'ohlcv', symbol: 'BTC/USDT', interval: '1m', rows: '1,051,200', size: '2.4 GB', lastUpdatedAt: now - 2 * 60 * 1000, status: 'synced', coverage: '2022-06 -> 2024-06' },
  { id: 'DS-002', name: 'eth_1m_3y', type: 'ohlcv', symbol: 'ETH/USDT', interval: '1m', rows: '1,576,800', size: '3.6 GB', lastUpdatedAt: now - 2 * 60 * 1000, status: 'synced', coverage: '2021-06 -> 2024-06' },
  { id: 'DS-003', name: 'sol_1m_1y', type: 'ohlcv', symbol: 'SOL/USDT', interval: '1m', rows: '525,600', size: '1.2 GB', lastUpdatedAt: now - 5 * 60 * 1000, status: 'synced', coverage: '2023-06 -> 2024-06' },
  { id: 'DS-004', name: 'multi_1h_2y', type: 'ohlcv', symbol: 'Multiple', interval: '1h', rows: '175,200', size: '820 MB', lastUpdatedAt: now - 15 * 60 * 1000, status: 'synced', coverage: '2022-06 -> 2024-06' },
  { id: 'DS-005', name: 'orderbook_1m', type: 'orderbook', symbol: 'BTC/USDT', interval: '1m', rows: '8,640,000', size: '12.8 GB', lastUpdatedAt: now - 30 * 1000, status: 'syncing', coverage: '2024-01 -> now' },
  { id: 'DS-006', name: 'social_feeds', type: 'social', symbol: 'Multiple', interval: 'real-time', rows: '2,340,000', size: '4.2 GB', lastUpdatedAt: now - 60 * 60 * 1000, status: 'stale', coverage: '2023-01 -> 2024-05' },
  { id: 'DS-007', name: 'btc_onchain', type: 'onchain', symbol: 'BTC', interval: '1d', rows: '3,650', size: '180 MB', lastUpdatedAt: now - 6 * 60 * 60 * 1000, status: 'synced', coverage: '2014-01 -> 2024-06' },
  { id: 'DS-008', name: 'avax_1m_1y', type: 'ohlcv', symbol: 'AVAX/USDT', interval: '1m', rows: '525,600', size: '1.1 GB', lastUpdatedAt: now - 8 * 60 * 1000, status: 'synced', coverage: '2023-06 -> 2024-06' },
];

const storageUsed = 26.3;
const storageTotal = 50;

export default function Database() {
  const [filter, setFilter] = useState<'all' | 'ohlcv' | 'orderbook' | 'social' | 'onchain'>('all');
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    const timer = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  const filtered = datasets.filter(d => filter === 'all' || d.type === filter);

  return (
    <div className="space-y-4 animate-slide-up">
      <div className="grid grid-cols-4 gap-3">
        <Card>
          <CardBody className="py-3">
            <p className="text-[10px] uppercase tracking-wider text-text-muted font-medium mb-1">Total Datasets</p>
            <p className="text-xl font-mono font-semibold text-text-primary">{datasets.length}</p>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="py-3">
            <p className="text-[10px] uppercase tracking-wider text-text-muted font-medium mb-1">Total Rows</p>
            <p className="text-xl font-mono font-semibold text-accent">14.8M</p>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="py-3 space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-[10px] uppercase tracking-wider text-text-muted font-medium">Storage</p>
              <p className="text-[10px] font-mono text-text-secondary">{storageUsed} / {storageTotal} GB</p>
            </div>
            <ProgressBar value={storageUsed} max={storageTotal} color="accent" className="h-1.5" />
          </CardBody>
        </Card>
        <Card>
          <CardBody className="py-3">
            <p className="text-[10px] uppercase tracking-wider text-text-muted font-medium mb-1">Syncing</p>
            <p className="text-xl font-mono font-semibold text-warn">{datasets.filter(d => d.status === 'syncing').length}</p>
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <CardTitle>Datasets</CardTitle>
            <div className="flex items-center gap-1">
              <Chip active={filter === 'all'} onClick={() => setFilter('all')}>All</Chip>
              <Chip active={filter === 'ohlcv'} onClick={() => setFilter('ohlcv')}>OHLCV</Chip>
              <Chip active={filter === 'orderbook'} onClick={() => setFilter('orderbook')}>Orderbook</Chip>
              <Chip active={filter === 'social'} onClick={() => setFilter('social')}>Social</Chip>
              <Chip active={filter === 'onchain'} onClick={() => setFilter('onchain')}>On-chain</Chip>
            </div>
          </div>
          <button className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-accent/10 text-accent text-[11px] font-medium border border-accent/20 hover:bg-accent/20 transition-all cursor-pointer">
            <Download size={11} /> Import Data
          </button>
        </CardHeader>
        <CardBody className="p-0">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border text-[10px] uppercase tracking-wider text-text-muted">
                <th className="text-left px-4 py-2.5 font-medium">Name</th>
                <th className="text-left px-4 py-2.5 font-medium">Type</th>
                <th className="text-left px-4 py-2.5 font-medium">Symbol</th>
                <th className="text-left px-4 py-2.5 font-medium">Interval</th>
                <th className="text-right px-4 py-2.5 font-medium">Rows</th>
                <th className="text-right px-4 py-2.5 font-medium">Size</th>
                <th className="text-left px-4 py-2.5 font-medium">Coverage</th>
                <th className="text-left px-4 py-2.5 font-medium">Status</th>
                <th className="text-left px-4 py-2.5 font-medium">Updated</th>
                <th className="text-right px-4 py-2.5 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filtered.map(ds => (
                <tr key={ds.id} className="hover:bg-bg-hover transition-colors">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <HardDrive size={12} className="text-text-muted" />
                      <span className="font-mono font-medium text-text-primary">{ds.name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant={ds.type === 'ohlcv' ? 'accent' : ds.type === 'orderbook' ? 'info' : ds.type === 'social' ? 'warning' : 'default'}>
                      {ds.type}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 font-mono text-text-secondary">{ds.symbol}</td>
                  <td className="px-4 py-3 font-mono text-text-muted">{ds.interval}</td>
                  <td className="px-4 py-3 font-mono text-right text-text-secondary tabular-nums">{ds.rows}</td>
                  <td className="px-4 py-3 font-mono text-right text-text-secondary">{ds.size}</td>
                  <td className="px-4 py-3 font-mono text-text-muted text-[10px]">{ds.coverage}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1.5">
                      <div className={cn('w-1.5 h-1.5 rounded-full', ds.status === 'synced' ? 'bg-accent' : ds.status === 'syncing' ? 'bg-warn pulse-dot' : 'bg-text-muted')} />
                      <span className={cn('text-[10px] font-mono', ds.status === 'synced' ? 'text-accent' : ds.status === 'syncing' ? 'text-warn' : 'text-text-muted')}>
                        {ds.status}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 font-mono text-text-muted text-[10px]">{formatRelativeTime(ds.lastUpdatedAt, nowMs)}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1">
                      <button className="p-1 rounded hover:bg-bg-hover text-text-muted hover:text-accent transition-all cursor-pointer" title="Sync">
                        <RefreshCw size={11} />
                      </button>
                      <button className="p-1 rounded hover:bg-bg-hover text-text-muted hover:text-loss transition-all cursor-pointer" title="Delete">
                        <Trash2 size={11} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Schema Preview - btc_1m_2y</CardTitle>
          <Badge variant="accent">OHLCV</Badge>
        </CardHeader>
        <CardBody className="p-0">
          <div className="font-mono text-[11px] text-text-secondary p-4 bg-bg-primary/50 rounded-b-lg">
            <div className="space-y-0.5">
              <p><span className="text-text-muted">CREATE TABLE</span> <span className="text-accent">btc_1m_2y</span> <span className="text-text-muted">(</span></p>
              <p className="pl-6"><span className="text-info">timestamp</span> <span className="text-text-muted">BIGINT NOT NULL,</span></p>
              <p className="pl-6"><span className="text-info">open</span> <span className="text-text-muted">DECIMAL(18,8) NOT NULL,</span></p>
              <p className="pl-6"><span className="text-info">high</span> <span className="text-text-muted">DECIMAL(18,8) NOT NULL,</span></p>
              <p className="pl-6"><span className="text-info">low</span> <span className="text-text-muted">DECIMAL(18,8) NOT NULL,</span></p>
              <p className="pl-6"><span className="text-info">close</span> <span className="text-text-muted">DECIMAL(18,8) NOT NULL,</span></p>
              <p className="pl-6"><span className="text-info">volume</span> <span className="text-text-muted">DECIMAL(24,8) NOT NULL,</span></p>
              <p className="pl-6"><span className="text-warn">PRIMARY KEY</span> <span className="text-text-muted">(timestamp)</span></p>
              <p><span className="text-text-muted">);</span></p>
            </div>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
