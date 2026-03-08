'use client';

import { Card, CardBody, CardHeader, CardTitle, Badge } from '../components/UI';
import { useMonitoringDashboard } from './monitoringDashboard';

export default function ExecutionQuality() {
  const { data } = useMonitoringDashboard();
  const execution = data?.dashboard_panels.execution_quality;

  return (
    <div className="space-y-4 animate-slide-up">
      <div className="grid grid-cols-3 gap-3">
        <Card><CardBody><p className="text-[10px] uppercase tracking-wider text-text-muted">Avg Slippage</p><p className="text-xl font-mono">{(execution?.avg_slippage_bps ?? 0).toFixed(2)} bps</p></CardBody></Card>
        <Card><CardBody><p className="text-[10px] uppercase tracking-wider text-text-muted">Fill Rate</p><p className="text-xl font-mono">{((execution?.fill_rate ?? 0) * 100).toFixed(1)}%</p></CardBody></Card>
        <Card><CardBody><p className="text-[10px] uppercase tracking-wider text-text-muted">Latency p95</p><p className="text-xl font-mono">{(execution?.latency_p95_ms ?? 0).toFixed(1)}ms</p></CardBody></Card>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>TCA and Fill Analytics</CardTitle>
          <Badge variant="info">By Exchange</Badge>
        </CardHeader>
        <CardBody className="space-y-2 text-xs text-text-secondary">
          <p>Execution quality is aggregated by route and time-of-day from the TCA analyzer.</p>
          <p>Consecutive slippage spikes trigger warning alerts and execution throttling.</p>
        </CardBody>
      </Card>
    </div>
  );
}
