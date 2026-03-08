'use client';

import { useMemo, useState } from 'react';
import { Activity, BarChart3, Cpu } from 'lucide-react';
import { useApi } from '@/hooks/useApi';
import { Card, CardHeader, CardBody, Badge, Chip, ProgressBar } from '../components/UI';
import { cn } from '../utils/cn';

type ModelRecord = {
  id: string;
  name: string;
  type: string;
  accuracy: number;
  horizon: string;
  last_trained: string;
  status: string;
  params: string;
  dataset: string;
};

type ModelRegistryResponse = {
  items: ModelRecord[];
};

type ModelAnalyticsResponse = {
  summary?: {
    win_rate?: number;
    directional_accuracy?: number;
    resolved_predictions?: number;
    pending_predictions?: number;
    mean_error_pct?: number;
    by_horizon?: Record<string, {
      resolved_predictions: number;
      pending_predictions: number;
      directional_accuracy: number;
      mean_error_pct: number;
      win_rate: number;
    }>;
  };
  recent_predictions?: Array<{
    market_id: string;
    horizon: string;
    predicted_price: number;
    actual_price: number;
    correct_direction: boolean;
  }>;
  live_preview?: Array<{
    market_id: string;
    horizon: string;
    predicted_price: number;
    current_price: number;
    confidence?: number;
    due_ts: string;
  }>;
};

function statusVariant(status: string) {
  if (status === 'active') return 'accent';
  if (status === 'training') return 'warning';
  return 'default';
}

function statusIcon(status: string) {
  if (status === 'training') {
    return <Activity size={13} className="text-warn" />;
  }
  if (status === 'active') {
    return <Cpu size={13} className="text-accent" />;
  }
  return <BarChart3 size={13} className="text-text-muted" />;
}

export default function Models() {
  const [selectedHorizon, setSelectedHorizon] = useState('5m');
  const quickHorizons = ['1m', '3m', '5m', '15m', '30m', '1h', '4h', '1d'];
  const registryRequest = useApi<ModelRegistryResponse>('/models/registry', { pollInterval: 10000 });
  const normalizedHorizon = selectedHorizon.trim() || '5m';
  const analyticsRequest = useApi<ModelAnalyticsResponse>(`/models/analytics?horizon=${encodeURIComponent(normalizedHorizon)}&limit=120`, { pollInterval: 10000 });
  const modelRows = useMemo(() => registryRequest.data?.items ?? [], [registryRequest.data?.items]);
  const horizonOptions = useMemo(() => {
    const values = new Set<string>(['1m', '5m', '15m', '1h', '4h', '1d']);
    for (const model of modelRows) {
      if (model.horizon) {
        values.add(model.horizon);
      }
    }
    for (const key of Object.keys(analyticsRequest.data?.summary?.by_horizon ?? {})) {
      values.add(key);
    }
    for (const row of analyticsRequest.data?.live_preview ?? []) {
      if (row.horizon) {
        values.add(row.horizon);
      }
    }
    for (const row of analyticsRequest.data?.recent_predictions ?? []) {
      if (row.horizon) {
        values.add(row.horizon);
      }
    }
    return Array.from(values);
  }, [
    analyticsRequest.data?.live_preview,
    analyticsRequest.data?.recent_predictions,
    analyticsRequest.data?.summary?.by_horizon,
    modelRows,
  ]);

  const active = useMemo(() => modelRows.filter((model) => model.status === 'active').length, [modelRows]);
  const training = useMemo(() => modelRows.filter((model) => model.status === 'training').length, [modelRows]);
  const avgError = analyticsRequest.data?.summary?.mean_error_pct ?? 0;
  const overallWinRate = (analyticsRequest.data?.summary?.win_rate ?? analyticsRequest.data?.summary?.directional_accuracy ?? 0) * 100;
  const selectedHorizonMetrics = analyticsRequest.data?.summary?.by_horizon?.[normalizedHorizon];
  const topModel = useMemo(
    () =>
      modelRows.reduce<ModelRecord | null>((best, model) => {
        if (!best || model.accuracy > best.accuracy) {
          return model;
        }
        return best;
      }, null),
    [modelRows],
  );
  const deployableModels = useMemo(() => modelRows.filter((model) => model.status !== 'active'), [modelRows]);
  const comparisonRows = useMemo(
    () =>
      [...modelRows]
        .sort((left, right) => right.accuracy - left.accuracy)
        .slice(0, 4)
        .map((model) => ({
          id: model.id,
          accuracy: model.accuracy,
          delta: topModel ? model.accuracy - topModel.accuracy : 0,
        })),
    [modelRows, topModel],
  );
  const recentPredictions = analyticsRequest.data?.recent_predictions ?? [];
  const livePreview = useMemo(() => analyticsRequest.data?.live_preview ?? [], [analyticsRequest.data?.live_preview]);
  const latestPredictionsByMarket = useMemo(() => {
    const marketMap = new Map<string, { market_id: string; predicted_price: number; current_price: number; confidence?: number; due_ts: string }>();
    for (const row of livePreview) {
      if (row.horizon !== normalizedHorizon || marketMap.has(row.market_id)) {
        continue;
      }
      marketMap.set(row.market_id, row);
    }
    return Array.from(marketMap.values());
  }, [livePreview, normalizedHorizon]);
  const filteredRecentPredictions = useMemo(
    () => recentPredictions.filter((prediction) => prediction.horizon === normalizedHorizon),
    [normalizedHorizon, recentPredictions],
  );
  const supportedHorizonRows = useMemo(() => {
    return horizonOptions
      .map((horizon) => ({
        horizon,
        models: modelRows.filter((model) => model.horizon === horizon).length,
        resolved: analyticsRequest.data?.summary?.by_horizon?.[horizon]?.resolved_predictions ?? 0,
        pending: analyticsRequest.data?.summary?.by_horizon?.[horizon]?.pending_predictions ?? 0,
      }))
      .sort((left, right) => left.horizon.localeCompare(right.horizon));
  }, [analyticsRequest.data?.summary?.by_horizon, horizonOptions, modelRows]);

  return (
    <div className="space-y-4 animate-slide-up">
      <div className="grid grid-cols-4 gap-3">
        <Card>
          <CardBody className="py-3">
            <p className="text-[10px] uppercase tracking-wider text-text-muted font-medium mb-1">Total Models</p>
            <p className="text-xl font-mono font-semibold text-text-primary">{modelRows.length}</p>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="py-3">
            <p className="text-[10px] uppercase tracking-wider text-text-muted font-medium mb-1">Active</p>
            <p className="text-xl font-mono font-semibold text-accent">{active}</p>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="py-3">
            <p className="text-[10px] uppercase tracking-wider text-text-muted font-medium mb-1">Training</p>
            <p className="text-xl font-mono font-semibold text-warn">{training}</p>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="py-3">
            <p className="text-[10px] uppercase tracking-wider text-text-muted font-medium mb-1">Win Rate</p>
            <p className="text-xl font-mono font-semibold text-profit">{overallWinRate.toFixed(1)}%</p>
          </CardBody>
        </Card>
      </div>

      <div className="grid grid-cols-3 gap-3">
        {modelRows.map((model) => (
          <Card
            key={model.id}
            className={cn(
              'transition-all',
              model.status === 'active' && 'border-accent/20',
              model.status === 'training' && 'border-warn/20',
            )}
          >
            <CardHeader>
              <div className="flex items-center gap-2">
                <div
                  className={cn(
                    'w-7 h-7 rounded-lg flex items-center justify-center',
                    model.status === 'active' ? 'bg-accent/10' : model.status === 'training' ? 'bg-warn/10' : 'bg-bg-tertiary',
                  )}
                >
                  {statusIcon(model.status)}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-semibold text-text-primary truncate">{model.name}</p>
                  <p className="text-[10px] font-mono text-text-muted">{model.id}</p>
                </div>
              </div>
              <Badge variant={statusVariant(model.status)}>{model.status}</Badge>
            </CardHeader>
            <CardBody className="space-y-3">
              <div className="grid grid-cols-2 gap-x-4 gap-y-2">
                <div>
                  <p className="text-[9px] uppercase tracking-wider text-text-muted">Type</p>
                  <p className="text-[11px] font-mono text-text-secondary">{model.type}</p>
                </div>
                <div>
                  <p className="text-[9px] uppercase tracking-wider text-text-muted">Horizon</p>
                  <p className="text-[11px] font-mono text-text-secondary">{model.horizon}</p>
                </div>
                <div>
                  <p className="text-[9px] uppercase tracking-wider text-text-muted">Parameters</p>
                  <p className="text-[11px] font-mono text-text-secondary">{model.params}</p>
                </div>
                <div>
                  <p className="text-[9px] uppercase tracking-wider text-text-muted">Dataset</p>
                  <p className="text-[11px] font-mono text-text-secondary truncate">{model.dataset}</p>
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[9px] uppercase tracking-wider text-text-muted">Accuracy</span>
                  <span
                    className={cn(
                      'text-[11px] font-mono font-medium tabular-nums',
                      model.accuracy >= 80 ? 'text-profit' : model.accuracy >= 70 ? 'text-accent' : 'text-warn',
                    )}
                  >
                    {model.accuracy.toFixed(1)}%
                  </span>
                </div>
                <ProgressBar
                  value={model.accuracy}
                  color={model.accuracy >= 80 ? 'profit' : model.accuracy >= 70 ? 'accent' : 'warn'}
                  className="h-1"
                />
              </div>

              <div className="flex items-center justify-between pt-1 border-t border-border">
                <span className="text-[10px] text-text-muted">Trained {model.last_trained}</span>
                <span className="text-[10px] font-mono text-text-muted">{model.accuracy.toFixed(1)}% confidence</span>
              </div>
            </CardBody>
          </Card>
        ))}
        {modelRows.length === 0 ? (
          <Card className="col-span-3">
            <CardBody className="py-8 text-center text-text-muted">
              No model artifacts are currently available in `models/`.
            </CardBody>
          </Card>
        ) : null}
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Card>
          <CardHeader>
            <span className="text-xs font-semibold text-text-primary">Deployment Controls</span>
            <Badge variant="accent">Registry</Badge>
          </CardHeader>
          <CardBody className="space-y-2">
            <div className="flex flex-wrap gap-2">
              <button className="rounded border border-accent/30 bg-accent/10 px-2.5 py-1.5 text-[11px] font-medium text-accent transition-colors hover:bg-accent/20">
                Deploy {deployableModels[0]?.id ?? 'candidate'}
              </button>
              <button className="rounded border border-warn/30 bg-warn/10 px-2.5 py-1.5 text-[11px] font-medium text-warn transition-colors hover:bg-warn/20">
                Rollback
              </button>
            </div>
            <p className="text-[11px] text-text-muted">Deployment actions are guarded by shadow validation and rollback policy.</p>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>
            <span className="text-xs font-semibold text-text-primary">Model Comparison</span>
            <Badge variant="info">Top 4</Badge>
          </CardHeader>
          <CardBody className="space-y-2">
            {comparisonRows.map((row) => (
              <div key={row.id} className="space-y-1">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="font-mono text-text-primary">{row.id}</span>
                  <span className="font-mono text-text-secondary">{row.accuracy.toFixed(1)}%</span>
                </div>
                <div className="h-1.5 overflow-hidden rounded bg-bg-tertiary">
                  <div className="h-full rounded bg-accent" style={{ width: `${Math.min(row.accuracy, 100)}%` }} />
                </div>
              </div>
            ))}
          </CardBody>
        </Card>
        <Card>
          <CardHeader>
            <span className="text-xs font-semibold text-text-primary">Deployment Status</span>
            <Badge variant="warning">A/B</Badge>
          </CardHeader>
          <CardBody className="space-y-2 text-[11px] text-text-secondary">
            <p>Active: <span className="font-mono text-text-primary">{topModel?.id ?? '--'}</span></p>
            <p>Shadow: <span className="font-mono text-text-primary">{deployableModels[0]?.id ?? '--'}</span></p>
            <p>Accuracy delta: <span className="font-mono text-accent">{comparisonRows[1]?.delta.toFixed(2) ?? '0.00'}%</span></p>
          </CardBody>
        </Card>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Card>
          <CardHeader>
            <span className="text-xs font-semibold text-text-primary">Prediction Horizon</span>
            <Badge variant="info">{normalizedHorizon}</Badge>
          </CardHeader>
          <CardBody className="space-y-2">
            <div className="flex flex-wrap gap-1.5">
              {quickHorizons.map((horizon) => (
                <Chip key={horizon} active={normalizedHorizon === horizon} onClick={() => setSelectedHorizon(horizon)}>
                  {horizon}
                </Chip>
              ))}
            </div>
            <div className="space-y-1.5">
              <label htmlFor="models-horizon" className="text-[10px] uppercase tracking-wider text-text-muted">
                Editable Horizon
              </label>
              <input
                id="models-horizon"
                list="models-horizon-options"
                value={selectedHorizon}
                onChange={(event) => setSelectedHorizon(event.target.value)}
                placeholder="e.g. 1m, 5m, 1h"
                className="w-full rounded border border-border bg-bg-tertiary px-2.5 py-2 text-xs font-mono text-text-primary placeholder:text-text-muted focus:border-accent/50 focus:outline-none"
              />
              <datalist id="models-horizon-options">
                {horizonOptions.map((horizon) => (
                  <option key={horizon} value={horizon} />
                ))}
              </datalist>
            </div>
            <div className="flex items-center justify-between text-[11px] text-text-muted">
              <span>Resolved {normalizedHorizon}</span>
              <span className="font-mono text-text-primary">{selectedHorizonMetrics?.resolved_predictions ?? 0}</span>
            </div>
            <div className="flex items-center justify-between text-[11px] text-text-muted">
              <span>Pending {normalizedHorizon}</span>
              <span className="font-mono text-text-primary">{selectedHorizonMetrics?.pending_predictions ?? 0}</span>
            </div>
            <div className="flex items-center justify-between text-[11px] text-text-muted">
              <span>{normalizedHorizon} win rate</span>
              <span className="font-mono text-text-primary">{(((selectedHorizonMetrics?.win_rate ?? 0) * 100)).toFixed(1)}%</span>
            </div>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>
            <span className="text-xs font-semibold text-text-primary">Model Fitness</span>
            <Badge variant="success">Past Results</Badge>
          </CardHeader>
          <CardBody className="space-y-2">
            <div className="text-sm font-semibold text-text-primary">{topModel?.name ?? '--'}</div>
            <div className="text-[11px] text-text-muted">Horizon {topModel?.horizon ?? '--'}</div>
            <div className="text-[11px] text-text-muted">Dataset {topModel?.dataset ?? '--'}</div>
            <div className="text-[11px] text-text-muted">Mean error {(avgError <= 1 ? avgError * 100 : avgError).toFixed(2)}%</div>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>
            <span className="text-xs font-semibold text-text-primary">Supported Horizons</span>
            <Badge variant="info">{supportedHorizonRows.length}</Badge>
          </CardHeader>
          <CardBody className="space-y-2">
            {supportedHorizonRows.slice(0, 6).map((row) => (
              <div key={row.horizon} className="flex items-center justify-between text-[11px]">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-text-primary">{row.horizon}</span>
                  <span className="text-text-muted">{row.models} models</span>
                </div>
                <span className="font-mono text-text-secondary">{row.resolved}/{row.pending}</span>
              </div>
            ))}
            {supportedHorizonRows.length === 0 ? <div className="text-[11px] text-text-muted">No horizon metadata loaded yet.</div> : null}
          </CardBody>
        </Card>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Card>
          <CardHeader>
            <span className="text-xs font-semibold text-text-primary">Latest {normalizedHorizon} Predictions</span>
            <Badge variant="accent">{latestPredictionsByMarket.length}</Badge>
          </CardHeader>
          <CardBody className="space-y-2">
            {latestPredictionsByMarket.slice(0, 3).map((prediction) => (
              <div key={`${prediction.market_id}-${prediction.due_ts}`} className="space-y-1 text-[11px]">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-text-secondary">{prediction.market_id}</span>
                  <span className="text-text-muted">${prediction.predicted_price.toFixed(2)}</span>
                </div>
                <div className="flex items-center justify-between text-[10px] text-text-muted">
                  <span>Now ${prediction.current_price.toFixed(2)}</span>
                  <span>{((prediction.confidence ?? 0) * 100).toFixed(0)}% conf</span>
                </div>
              </div>
            ))}
            {latestPredictionsByMarket.length === 0 ? <div className="text-[11px] text-text-muted">No live {normalizedHorizon} predictions recorded yet.</div> : null}
          </CardBody>
        </Card>
        <Card>
          <CardHeader>
            <span className="text-xs font-semibold text-text-primary">{normalizedHorizon} Snapshot</span>
            <Badge variant="warning">Live Stats</Badge>
          </CardHeader>
          <CardBody className="space-y-2">
            <div className="flex items-center justify-between text-[11px] text-text-muted">
              <span>Models on horizon</span>
              <span className="font-mono text-text-primary">{modelRows.filter((model) => model.horizon === normalizedHorizon).length}</span>
            </div>
            <div className="flex items-center justify-between text-[11px] text-text-muted">
              <span>Recent resolved</span>
              <span className="font-mono text-text-primary">{filteredRecentPredictions.length}</span>
            </div>
            <div className="flex items-center justify-between text-[11px] text-text-muted">
              <span>Live markets</span>
              <span className="font-mono text-text-primary">{latestPredictionsByMarket.length}</span>
            </div>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>
            <span className="text-xs font-semibold text-text-primary">Analytics Feed</span>
            <Badge variant={analyticsRequest.error ? 'warning' : 'accent'}>
              {analyticsRequest.error ? 'Stale' : 'Live'}
            </Badge>
          </CardHeader>
          <CardBody className="space-y-2">
            <div className="text-[11px] text-text-muted">
              Tracking <span className="font-mono text-text-primary">{normalizedHorizon}</span> from `/models/analytics`.
            </div>
            <div className="text-[11px] text-text-muted">
              Poll interval <span className="font-mono text-text-primary">{analyticsRequest.activePollInterval ?? 0}ms</span>
            </div>
            <div className="text-[11px] text-text-muted">
              {analyticsRequest.error ? analyticsRequest.error.message : 'Analytics endpoint responding normally.'}
            </div>
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <span className="text-xs font-semibold text-text-primary">Recent Resolved Predictions</span>
          <Badge variant="info">{filteredRecentPredictions.length}</Badge>
        </CardHeader>
        <CardBody className="space-y-2">
          {filteredRecentPredictions.slice(0, 6).map((prediction, index) => (
            <div key={`${prediction.market_id}-${prediction.horizon}-${index}`} className="flex items-center justify-between border-b border-border/40 pb-2 text-[11px] last:border-b-0 last:pb-0">
              <div>
                <div className="font-mono text-text-secondary">{prediction.market_id} {prediction.horizon}</div>
                <div className="text-text-muted">
                  Pred ${prediction.predicted_price.toFixed(2)} vs Actual ${prediction.actual_price.toFixed(2)}
                </div>
              </div>
              <Badge variant={prediction.correct_direction ? 'success' : 'warning'}>
                {prediction.correct_direction ? 'WIN' : 'MISS'}
              </Badge>
            </div>
          ))}
          {filteredRecentPredictions.length === 0 ? <div className="text-[11px] text-text-muted">No resolved {normalizedHorizon} predictions yet.</div> : null}
        </CardBody>
      </Card>
    </div>
  );
}
