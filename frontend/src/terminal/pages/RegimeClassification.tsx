'use client';

import { Card, CardBody, CardHeader, CardTitle, Badge } from '../components/UI';
import { useMonitoringDashboard } from './monitoringDashboard';

export default function RegimeClassification() {
  const { data } = useMonitoringDashboard();
  const regime = data?.dashboard_panels.regime_classification;

  return (
    <div className="space-y-4 animate-slide-up">
      <Card>
        <CardHeader>
          <CardTitle>Current Market Regime</CardTitle>
          <Badge variant="accent">{regime?.current_regime ?? 'unknown'}</Badge>
        </CardHeader>
        <CardBody>
          <p className="text-sm font-mono text-text-primary">Confidence {(regime ? regime.confidence * 100 : 0).toFixed(1)}%</p>
        </CardBody>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Regime History and Transitions</CardTitle>
          <Badge variant="info">{regime?.history.length ?? 0}</Badge>
        </CardHeader>
        <CardBody className="space-y-2">
          {(regime?.history ?? []).map((row, index) => (
            <div key={`${row.regime}-${index}`} className="flex items-center justify-between text-xs border-b border-border/40 pb-2 last:border-b-0 last:pb-0">
              <span className="font-mono text-text-primary">{row.regime}</span>
              <span className="text-text-secondary">{row.duration_hours}h</span>
            </div>
          ))}
        </CardBody>
      </Card>
    </div>
  );
}
