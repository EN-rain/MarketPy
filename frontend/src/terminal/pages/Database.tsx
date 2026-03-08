'use client';

import { Download, HardDrive, RefreshCw, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useApi } from '@/hooks/useApi';
import { Card, CardHeader, CardTitle, CardBody, Badge, ProgressBar, Chip } from '../components/UI';
import { cn } from '../utils/cn';
import { formatRelativeTime } from '../utils/time';

interface DatasetInfo {
  name: string;
  type: 'ohlcv';
  symbol: string;
  interval: string;
  rows: string;
  size: string;
  lastUpdatedAt: number;
  status: 'synced' | 'stale';
  coverage: string;
}

type DataHealthResponse = {
  total_markets: number;
  active_markets: number;
  total_records: number;
  storage_size_gb: number;
  last_ingestion: string | null;
  data_quality_score: number;
  datasets: Array<{
    name: string;
    records: number;
    size_mb: number;
    last_update: string;
    status: 'healthy' | 'warning';
  }>;
  ingestion_status: {
    ws_connected: boolean;
    rest_api_healthy: boolean;
    parquet_writer_healthy: boolean;
    duckdb_healthy: boolean;
  };
};

function parseRelativeTimestamp(value: string, nowMs: number): number {
  if (value === 'just now') {
    return nowMs;
  }
  const match = value.match(/^(\d+)\s+(min|h|d)\s+ago$/);
  if (!match) {
    return nowMs;
  }
  const amount = Number.parseInt(match[1], 10);
  const unit = match[2];
  const multiplier = unit === 'min' ? 60_000 : unit === 'h' ? 3_600_000 : 86_400_000;
  return nowMs - amount * multiplier;
}

export default function Database() {
  const healthRequest = useApi<DataHealthResponse>('/data/health', { pollInterval: 5000 });
  const [filter, setFilter] = useState<'all' | 'ohlcv'>('all');
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    const timer = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  const datasets: DatasetInfo[] = (healthRequest.data?.datasets ?? []).map((dataset) => ({
    name: dataset.name,
    type: 'ohlcv',
    symbol: dataset.name.replace('USDT', '/USDT'),
    interval: 'live',
    rows: dataset.records.toLocaleString('en-US'),
    size: `${dataset.size_mb.toFixed(1)} MB`,
    lastUpdatedAt: parseRelativeTimestamp(dataset.last_update, nowMs),
    status: dataset.status === 'healthy' ? 'synced' : 'stale',
    coverage: dataset.last_update,
  }));

  const filtered = datasets.filter((dataset) => filter === 'all' || dataset.type === filter);
  const storageUsed = healthRequest.data?.storage_size_gb ?? 0;
  const storageTotal = Math.max(Math.ceil(storageUsed || 1), 1);
  const qualityScore = Math.round((healthRequest.data?.data_quality_score ?? 0) * 100);

  return (
    <div className="space-y-4 animate-slide-up">
      <div className="grid grid-cols-4 gap-3">
        <Card>
          <CardBody className="py-3">
            <p className="text-[10px] uppercase tracking-wider text-text-muted font-medium mb-1">Total Datasets</p>
            <p className="text-xl font-mono font-semibold text-text-primary">{healthRequest.data?.total_markets ?? 0}</p>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="py-3">
            <p className="text-[10px] uppercase tracking-wider text-text-muted font-medium mb-1">Total Rows</p>
            <p className="text-xl font-mono font-semibold text-accent">{(healthRequest.data?.total_records ?? 0).toLocaleString('en-US')}</p>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="py-3 space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-[10px] uppercase tracking-wider text-text-muted font-medium">Storage</p>
              <p className="text-[10px] font-mono text-text-secondary">{storageUsed.toFixed(2)} / {storageTotal} GB</p>
            </div>
            <ProgressBar value={storageUsed} max={storageTotal} color="accent" className="h-1.5" />
          </CardBody>
        </Card>
        <Card>
          <CardBody className="py-3">
            <p className="text-[10px] uppercase tracking-wider text-text-muted font-medium mb-1">Data Quality</p>
            <p className="text-xl font-mono font-semibold text-warn">{qualityScore}%</p>
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
              {filtered.map((dataset) => (
                <tr key={dataset.name} className="hover:bg-bg-hover transition-colors">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <HardDrive size={12} className="text-text-muted" />
                      <span className="font-mono font-medium text-text-primary">{dataset.name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant="accent">{dataset.type}</Badge>
                  </td>
                  <td className="px-4 py-3 font-mono text-text-secondary">{dataset.symbol}</td>
                  <td className="px-4 py-3 font-mono text-text-muted">{dataset.interval}</td>
                  <td className="px-4 py-3 font-mono text-right text-text-secondary tabular-nums">{dataset.rows}</td>
                  <td className="px-4 py-3 font-mono text-right text-text-secondary">{dataset.size}</td>
                  <td className="px-4 py-3 font-mono text-text-muted text-[10px]">{dataset.coverage}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1.5">
                      <div className={cn('w-1.5 h-1.5 rounded-full', dataset.status === 'synced' ? 'bg-accent' : 'bg-text-muted')} />
                      <span className={cn('text-[10px] font-mono', dataset.status === 'synced' ? 'text-accent' : 'text-text-muted')}>
                        {dataset.status}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 font-mono text-text-muted text-[10px]">{formatRelativeTime(dataset.lastUpdatedAt, nowMs)}</td>
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
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={10} className="px-4 py-8 text-center text-text-muted">
                    No live datasets reported by `/data/health`.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Ingestion Health</CardTitle>
          <Badge variant={(healthRequest.data?.ingestion_status.ws_connected ?? false) ? 'accent' : 'warning'}>Live</Badge>
        </CardHeader>
        <CardBody>
          <div className="grid grid-cols-2 gap-4 font-mono text-[11px] text-text-secondary">
            <div className="space-y-1">
              <p>ws_connected: <span className={healthRequest.data?.ingestion_status.ws_connected ? 'text-accent' : 'text-loss'}>{String(healthRequest.data?.ingestion_status.ws_connected ?? false)}</span></p>
              <p>rest_api_healthy: <span className={healthRequest.data?.ingestion_status.rest_api_healthy ? 'text-accent' : 'text-loss'}>{String(healthRequest.data?.ingestion_status.rest_api_healthy ?? false)}</span></p>
            </div>
            <div className="space-y-1">
              <p>parquet_writer_healthy: <span className={healthRequest.data?.ingestion_status.parquet_writer_healthy ? 'text-accent' : 'text-loss'}>{String(healthRequest.data?.ingestion_status.parquet_writer_healthy ?? false)}</span></p>
              <p>duckdb_healthy: <span className={healthRequest.data?.ingestion_status.duckdb_healthy ? 'text-accent' : 'text-loss'}>{String(healthRequest.data?.ingestion_status.duckdb_healthy ?? false)}</span></p>
            </div>
          </div>
          <div className="mt-4 text-[10px] text-text-muted">
            Last ingestion: {healthRequest.data?.last_ingestion ? new Date(healthRequest.data.last_ingestion).toLocaleString('en-US') : 'n/a'}
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
