'use client';

import { Card, CardBody, CardHeader, CardTitle, Badge } from '../components/UI';
import { useMonitoringDashboard } from './monitoringDashboard';

export default function FeatureStore() {
  const { data } = useMonitoringDashboard();
  const panel = data?.dashboard_panels.feature_store;

  return (
    <div className="space-y-4 animate-slide-up">
      <div className="grid grid-cols-3 gap-3">
        <Card><CardBody><p className="text-[10px] uppercase tracking-wider text-text-muted">Feature Count</p><p className="text-xl font-mono">{panel?.feature_count ?? 0}</p></CardBody></Card>
        <Card><CardBody><p className="text-[10px] uppercase tracking-wider text-text-muted">Drift Alerts</p><p className="text-xl font-mono text-warn">{panel?.drift_alerts ?? 0}</p></CardBody></Card>
        <Card><CardBody><p className="text-[10px] uppercase tracking-wider text-text-muted">Lineage</p><p className="text-sm font-mono text-text-secondary">onchain + market + execution</p></CardBody></Card>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Feature Registry and Importance</CardTitle>
          <Badge variant="accent">Live</Badge>
        </CardHeader>
        <CardBody className="space-y-2">
          {(panel?.top_importance ?? []).map((feature) => (
            <div key={feature.name} className="flex items-center justify-between border-b border-border/40 pb-2 text-xs last:border-b-0 last:pb-0">
              <span className="font-mono text-text-primary">{feature.name}</span>
              <span className="font-mono text-accent">{(feature.importance * 100).toFixed(1)}%</span>
            </div>
          ))}
        </CardBody>
      </Card>
    </div>
  );
}
