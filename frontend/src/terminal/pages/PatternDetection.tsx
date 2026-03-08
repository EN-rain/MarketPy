'use client';

import { Card, CardBody, CardHeader, CardTitle, Badge } from '../components/UI';
import { useMonitoringDashboard } from './monitoringDashboard';

export default function PatternDetection() {
  const { data } = useMonitoringDashboard();
  const patterns = data?.dashboard_panels.pattern_detection.detected ?? [];

  return (
    <div className="space-y-4 animate-slide-up">
      <Card>
        <CardHeader>
          <CardTitle>Detected Patterns</CardTitle>
          <Badge variant="info">{patterns.length}</Badge>
        </CardHeader>
        <CardBody className="space-y-2">
          {patterns.map((pattern) => (
            <div key={`${pattern.symbol}-${pattern.pattern}`} className="rounded border border-border px-3 py-2">
              <div className="flex items-center justify-between">
                <span className="font-mono text-sm text-text-primary">{pattern.symbol}</span>
                <Badge variant="accent">{(pattern.confidence * 100).toFixed(0)}%</Badge>
              </div>
              <p className="text-xs text-text-secondary">{pattern.pattern}</p>
              <p className="text-[11px] text-text-muted">Expected target: ${pattern.target.toLocaleString('en-US')}</p>
            </div>
          ))}
        </CardBody>
      </Card>
    </div>
  );
}
