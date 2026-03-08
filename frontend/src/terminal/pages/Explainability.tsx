'use client';

import { useEffect } from 'react';
import { useWebSocket } from '@/hooks/useWebSocket';
import { Card, CardBody, CardHeader, CardTitle, Badge } from '../components/UI';
import { useMonitoringDashboard } from './monitoringDashboard';

export default function Explainability() {
  const { data } = useMonitoringDashboard();
  const explainability = data?.dashboard_panels.explainability;
  const { isConnected, sendMessage } = useWebSocket();

  useEffect(() => {
    if (isConnected) {
      sendMessage({ type: 'subscribe_channels', channels: ['predictions'] });
    }
  }, [isConnected, sendMessage]);

  return (
    <div className="space-y-4 animate-slide-up">
      <Card>
        <CardHeader>
          <CardTitle>Prediction With Confidence Interval</CardTitle>
          <Badge variant={isConnected ? 'accent' : 'warning'}>{isConnected ? 'Live' : 'Offline'}</Badge>
        </CardHeader>
        <CardBody className="space-y-2">
          <p className="text-sm font-mono text-text-primary">{explainability?.prediction.symbol ?? '--'}: ${explainability?.prediction.value.toLocaleString('en-US') ?? '--'}</p>
          <p className="text-xs text-text-secondary">
            Interval: {explainability ? `$${explainability.prediction.lower.toLocaleString('en-US')} - $${explainability.prediction.upper.toLocaleString('en-US')}` : '--'}
          </p>
        </CardBody>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Top SHAP Feature Contributions</CardTitle>
          <Badge variant="info">{explainability?.top_shap.length ?? 0}</Badge>
        </CardHeader>
        <CardBody className="space-y-2">
          {(explainability?.top_shap ?? []).map((item) => (
            <div key={item.feature} className="flex items-center justify-between border-b border-border/40 pb-2 text-xs last:border-b-0 last:pb-0">
              <span className="font-mono text-text-primary">{item.feature}</span>
              <span className="font-mono text-accent">{(item.contribution * 100).toFixed(1)}%</span>
            </div>
          ))}
        </CardBody>
      </Card>
    </div>
  );
}
