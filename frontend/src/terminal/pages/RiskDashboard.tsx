'use client';

import { Card, CardBody, CardHeader, CardTitle, Badge } from '../components/UI';
import { useMonitoringDashboard } from './monitoringDashboard';

export default function RiskDashboard() {
  const { data } = useMonitoringDashboard();
  const risk = data?.dashboard_panels.risk_dashboard;

  return (
    <div className="space-y-4 animate-slide-up">
      <div className="grid grid-cols-5 gap-3">
        <Card><CardBody><p className="text-[10px] uppercase tracking-wider text-text-muted">VaR</p><p className="text-lg font-mono">{((risk?.var ?? 0) * 100).toFixed(2)}%</p></CardBody></Card>
        <Card><CardBody><p className="text-[10px] uppercase tracking-wider text-text-muted">CVaR</p><p className="text-lg font-mono">{((risk?.cvar ?? 0) * 100).toFixed(2)}%</p></CardBody></Card>
        <Card><CardBody><p className="text-[10px] uppercase tracking-wider text-text-muted">Drawdown</p><p className="text-lg font-mono text-warn">{((risk?.drawdown ?? 0) * 100).toFixed(2)}%</p></CardBody></Card>
        <Card><CardBody><p className="text-[10px] uppercase tracking-wider text-text-muted">Leverage</p><p className="text-lg font-mono">{(risk?.leverage ?? 0).toFixed(2)}x</p></CardBody></Card>
        <Card><CardBody><p className="text-[10px] uppercase tracking-wider text-text-muted">Alerts</p><p className="text-lg font-mono text-loss">{risk?.active_risk_alerts ?? 0}</p></CardBody></Card>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Risk Limits and Usage</CardTitle>
          <Badge variant="warning">Live</Badge>
        </CardHeader>
        <CardBody className="space-y-2 text-xs text-text-secondary">
          <p>Portfolio risk is monitored continuously with adaptive limits from regime classifier.</p>
          <p>Correlation matrix and leverage constraints are enforced at order sizing time.</p>
        </CardBody>
      </Card>
    </div>
  );
}
