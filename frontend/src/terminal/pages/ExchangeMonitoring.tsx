'use client';

import { Card, CardBody, CardHeader, CardTitle, Badge } from '../components/UI';
import { useMonitoringDashboard } from './monitoringDashboard';

export default function ExchangeMonitoring() {
  const { data } = useMonitoringDashboard();
  const panel = data?.dashboard_panels.multi_exchange;

  return (
    <div className="space-y-4 animate-slide-up">
      <Card>
        <CardHeader>
          <CardTitle>Exchange Connectivity</CardTitle>
          <Badge variant="accent">{panel?.exchanges.length ?? 0}</Badge>
        </CardHeader>
        <CardBody className="space-y-2">
          {(panel?.exchanges ?? []).map((exchange) => (
            <div key={exchange.name} className="flex items-center justify-between border-b border-border/40 pb-2 text-xs last:border-b-0 last:pb-0">
              <span className="font-mono text-text-primary">{exchange.name}</span>
              <div className="flex items-center gap-2">
                <span className="font-mono text-text-secondary">${exchange.price.toLocaleString('en-US')}</span>
                <Badge variant={exchange.status === 'connected' ? 'success' : 'warning'}>{exchange.status}</Badge>
              </div>
            </div>
          ))}
        </CardBody>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Arbitrage Opportunities</CardTitle>
          <Badge variant="warning">{panel?.arbitrage.length ?? 0}</Badge>
        </CardHeader>
        <CardBody className="space-y-2">
          {(panel?.arbitrage ?? []).map((arb, index) => (
            <div key={`${arb.symbol}-${index}`} className="text-xs rounded border border-border px-3 py-2">
              <div className="flex items-center justify-between">
                <span className="font-mono text-text-primary">{arb.symbol}</span>
                <span className="font-mono text-profit">+{arb.net_profit_pct.toFixed(2)}%</span>
              </div>
              <p className="text-text-secondary">Buy {arb.buy} / Sell {arb.sell}</p>
            </div>
          ))}
        </CardBody>
      </Card>
    </div>
  );
}
