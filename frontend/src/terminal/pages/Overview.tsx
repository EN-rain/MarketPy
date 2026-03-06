import { TrendingUp, Activity, DollarSign, BarChart3, AlertTriangle } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardBody, Badge, MiniSparkline, StatValue, ProgressBar } from '../components/UI';
import { cryptoAssets, portfolioData, equityCurve, logEntries, recentTrades, formatCurrency } from '../data/mock';
import { cn } from '../utils/cn';

function EquityChart() {
  const data = equityCurve;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const w = 600;
  const h = 140;
  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = h - ((v - min) / range) * (h - 10) - 5;
    return `${x},${y}`;
  });
  const line = points.join(' ');
  const areaPoints = `0,${h} ${line} ${w},${h}`;

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-full" preserveAspectRatio="none">
      <defs>
        <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#00d4aa" stopOpacity="0.15" />
          <stop offset="100%" stopColor="#00d4aa" stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={areaPoints} fill="url(#eqGrad)" />
      <polyline points={line} fill="none" stroke="#00d4aa" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default function Overview() {
  return (
    <div className="space-y-4 animate-slide-up">
      <div className="grid grid-cols-4 gap-3">
        <Card>
          <CardBody className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center shrink-0">
              <DollarSign size={14} className="text-accent" />
            </div>
            <StatValue label="Portfolio Value" value={formatCurrency(portfolioData.totalValue)} change={portfolioData.dayPnlPercent} sub="today" />
          </CardBody>
        </Card>
        <Card>
          <CardBody className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-lg bg-profit/10 flex items-center justify-center shrink-0">
              <TrendingUp size={14} className="text-profit" />
            </div>
            <StatValue label="Total P&L" value={formatCurrency(portfolioData.totalPnl)} change={portfolioData.totalPnlPercent} sub="all time" />
          </CardBody>
        </Card>
        <Card>
          <CardBody className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-lg bg-info/10 flex items-center justify-center shrink-0">
              <Activity size={14} className="text-info" />
            </div>
            <StatValue label="Active Models" value="4" sub="of 6 total" />
          </CardBody>
        </Card>
        <Card>
          <CardBody className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-lg bg-warn/10 flex items-center justify-center shrink-0">
              <BarChart3 size={14} className="text-warn" />
            </div>
            <StatValue label="Win Rate" value="67.8%" sub="last 30d" />
          </CardBody>
        </Card>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Card className="col-span-2">
          <CardHeader>
            <CardTitle>Equity Curve</CardTitle>
            <div className="flex items-center gap-2">
              <Badge variant="accent">Paper</Badge>
              <span className="text-[10px] font-mono text-text-muted">25 data points</span>
            </div>
          </CardHeader>
          <CardBody className="p-2">
            <div className="h-[140px]">
              <EquityChart />
            </div>
            <div className="flex justify-between px-2 mt-1">
              <span className="text-[9px] font-mono text-text-muted">Day 1</span>
              <span className="text-[9px] font-mono text-text-muted">Day 25</span>
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Positions</CardTitle>
            <Badge>{portfolioData.positions.length} assets</Badge>
          </CardHeader>
          <CardBody className="p-0">
            <div className="divide-y divide-border max-h-[190px] overflow-y-auto">
              {portfolioData.positions.map(pos => (
                <div key={pos.symbol} className="px-4 py-2.5 flex items-center justify-between hover:bg-bg-hover transition-colors">
                  <div className="flex items-center gap-2.5">
                    <span className="text-xs font-mono font-semibold text-text-primary">{pos.symbol}</span>
                    <span className="text-[10px] font-mono text-text-muted">{pos.allocation}%</span>
                  </div>
                  <div className="text-right">
                    <p className="text-xs font-mono text-text-primary tabular-nums">{formatCurrency(pos.value)}</p>
                    <p className={cn('text-[10px] font-mono tabular-nums', pos.pnl >= 0 ? 'text-profit' : 'text-loss')}>
                      {pos.pnl >= 0 ? '+' : ''}{formatCurrency(pos.pnl)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Card>
          <CardHeader>
            <CardTitle>Top Movers</CardTitle>
            <Badge variant="info">24h</Badge>
          </CardHeader>
          <CardBody className="p-0">
            <div className="divide-y divide-border">
              {cryptoAssets.slice(0, 5).sort((a, b) => Math.abs(b.change24h) - Math.abs(a.change24h)).map(asset => (
                <div key={asset.symbol} className="px-4 py-2.5 flex items-center justify-between hover:bg-bg-hover transition-colors">
                  <div className="flex items-center gap-2.5">
                    <span className="text-xs font-mono font-semibold text-text-primary">{asset.symbol}</span>
                    <MiniSparkline data={asset.sparkline} color={asset.change24h >= 0 ? 'profit' : 'loss'} width={50} height={16} />
                  </div>
                  <div className="text-right">
                    <p className="text-xs font-mono text-text-primary tabular-nums">{formatCurrency(asset.price)}</p>
                    <p className={cn('text-[10px] font-mono tabular-nums', asset.change24h >= 0 ? 'text-profit' : 'text-loss')}>
                      {asset.change24h >= 0 ? '+' : ''}{asset.change24h.toFixed(2)}%
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>AI Signals</CardTitle>
            <Badge variant="accent">Live</Badge>
          </CardHeader>
          <CardBody className="p-0">
            <div className="divide-y divide-border">
              {cryptoAssets.filter(a => a.signal !== 'neutral').slice(0, 5).map(asset => (
                <div key={asset.symbol} className="px-4 py-2.5 flex items-center justify-between hover:bg-bg-hover transition-colors">
                  <div className="flex items-center gap-2.5">
                    <span className="text-xs font-mono font-semibold text-text-primary">{asset.symbol}</span>
                    <Badge variant={asset.signal === 'long' ? 'success' : 'danger'}>
                      {asset.signal === 'long' ? 'LONG' : 'SHORT'}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-2">
                    <ProgressBar value={asset.confidence} color={asset.confidence > 75 ? 'accent' : 'warn'} className="w-12" />
                    <span className="text-[10px] font-mono text-text-secondary tabular-nums w-7 text-right">{asset.confidence}%</span>
                  </div>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Activity Log</CardTitle>
            <div className="w-1.5 h-1.5 rounded-full bg-accent pulse-dot" />
          </CardHeader>
          <CardBody className="p-0">
            <div className="divide-y divide-border max-h-[195px] overflow-y-auto">
              {logEntries.map((entry, i) => (
                <div key={i} className="px-4 py-2 hover:bg-bg-hover transition-colors">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-[9px] font-mono text-text-muted">{entry.time}</span>
                    {entry.level === 'warn' && <AlertTriangle size={9} className="text-warn" />}
                    {entry.level === 'error' && <AlertTriangle size={9} className="text-loss" />}
                  </div>
                  <p className="text-[11px] font-mono text-text-secondary leading-tight">{entry.msg}</p>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent Trades</CardTitle>
          <span className="text-[10px] font-mono text-text-muted">{recentTrades.length} trades today</span>
        </CardHeader>
        <CardBody className="p-0">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border text-[10px] uppercase tracking-wider text-text-muted">
                <th className="text-left px-4 py-2 font-medium">ID</th>
                <th className="text-left px-4 py-2 font-medium">Pair</th>
                <th className="text-left px-4 py-2 font-medium">Side</th>
                <th className="text-right px-4 py-2 font-medium">Price</th>
                <th className="text-right px-4 py-2 font-medium">Amount</th>
                <th className="text-right px-4 py-2 font-medium">Total</th>
                <th className="text-left px-4 py-2 font-medium">Time</th>
                <th className="text-left px-4 py-2 font-medium">Status</th>
                <th className="text-right px-4 py-2 font-medium">P&L</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {recentTrades.slice(0, 6).map(trade => (
                <tr key={trade.id} className="hover:bg-bg-hover transition-colors">
                  <td className="px-4 py-2 font-mono text-text-muted">{trade.id}</td>
                  <td className="px-4 py-2 font-mono font-medium text-text-primary">{trade.pair}</td>
                  <td className="px-4 py-2">
                    <Badge variant={trade.side === 'buy' ? 'success' : 'danger'}>{trade.side.toUpperCase()}</Badge>
                  </td>
                  <td className="px-4 py-2 font-mono text-right text-text-primary tabular-nums">{formatCurrency(trade.price)}</td>
                  <td className="px-4 py-2 font-mono text-right text-text-secondary tabular-nums">{trade.amount}</td>
                  <td className="px-4 py-2 font-mono text-right text-text-primary tabular-nums">{formatCurrency(trade.total)}</td>
                  <td className="px-4 py-2 font-mono text-text-muted">{trade.time}</td>
                  <td className="px-4 py-2">
                    <Badge variant={trade.status === 'filled' ? 'accent' : trade.status === 'pending' ? 'warning' : 'default'}>
                      {trade.status}
                    </Badge>
                  </td>
                  <td className={cn('px-4 py-2 font-mono text-right tabular-nums',
                    trade.pnl === undefined ? 'text-text-muted' : trade.pnl >= 0 ? 'text-profit' : 'text-loss',
                  )}>
                    {trade.pnl !== undefined ? `${trade.pnl >= 0 ? '+' : ''}${formatCurrency(trade.pnl)}` : '--'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardBody>
      </Card>
    </div>
  );
}
