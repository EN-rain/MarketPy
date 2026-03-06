import { useEffect, useMemo, useState } from 'react';
import { Card, CardHeader, CardTitle, CardBody, Badge, Chip, StatValue } from '../components/UI';
import { cryptoAssets, portfolioData, recentTrades, type Trade, formatCurrency } from '../data/mock';
import { cn } from '../utils/cn';

function CandlestickChart() {
  const candles = [
    { o: 103200, h: 104100, l: 102800, c: 103900 },
    { o: 103900, h: 104500, l: 103600, c: 103700 },
    { o: 103700, h: 104200, l: 103100, c: 104000 },
    { o: 104000, h: 104800, l: 103800, c: 104600 },
    { o: 104600, h: 105100, l: 104200, c: 104400 },
    { o: 104400, h: 104900, l: 103900, c: 104800 },
    { o: 104800, h: 105500, l: 104500, c: 105200 },
    { o: 105200, h: 105800, l: 104900, c: 105000 },
    { o: 105000, h: 105400, l: 104600, c: 105300 },
    { o: 105300, h: 105900, l: 105000, c: 105600 },
    { o: 105600, h: 106200, l: 105300, c: 105500 },
    { o: 105500, h: 106000, l: 105100, c: 105800 },
    { o: 105800, h: 106400, l: 105500, c: 106100 },
    { o: 106100, h: 106700, l: 105800, c: 106500 },
    { o: 106500, h: 107000, l: 106200, c: 106400 },
    { o: 106400, h: 106800, l: 105900, c: 106700 },
    { o: 106700, h: 107300, l: 106400, c: 107100 },
    { o: 107100, h: 107600, l: 106800, c: 106900 },
    { o: 106900, h: 107400, l: 106600, c: 107200 },
    { o: 107200, h: 107800, l: 107000, c: 104283 },
  ];

  const allPrices = candles.flatMap(c => [c.h, c.l]);
  const min = Math.min(...allPrices);
  const max = Math.max(...allPrices);
  const range = max - min;
  const w = 700;
  const h = 220;
  const padding = 10;
  const candleW = (w - padding * 2) / candles.length;
  const bodyW = candleW * 0.6;

  const scaleY = (price: number) => padding + (1 - (price - min) / range) * (h - padding * 2);

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-full">
      {[0, 0.25, 0.5, 0.75, 1].map(pct => {
        const y = padding + pct * (h - padding * 2);
        const price = max - pct * range;
        return (
          <g key={pct}>
            <line x1={padding} y1={y} x2={w - padding} y2={y} stroke="#1e2030" strokeWidth="0.5" />
            <text x={w - 5} y={y - 3} fill="#565868" fontSize="7" fontFamily="JetBrains Mono" textAnchor="end">
              {price.toFixed(0)}
            </text>
          </g>
        );
      })}
      {candles.map((c, i) => {
        const x = padding + i * candleW + candleW / 2;
        const isGreen = c.c >= c.o;
        const color = isGreen ? '#00e676' : '#ff4757';
        const bodyTop = scaleY(Math.max(c.o, c.c));
        const bodyBot = scaleY(Math.min(c.o, c.c));
        const bodyH = Math.max(bodyBot - bodyTop, 1);
        return (
          <g key={i}>
            <line x1={x} y1={scaleY(c.h)} x2={x} y2={scaleY(c.l)} stroke={color} strokeWidth="1" />
            <rect x={x - bodyW / 2} y={bodyTop} width={bodyW} height={bodyH} fill={color} rx="0.5" opacity="0.85" />
          </g>
        );
      })}
    </svg>
  );
}

function buildTradeId(existing: Trade[]): string {
  const maxNum = existing.reduce((max, t) => {
    const num = Number.parseInt(t.id.replace('T-', ''), 10);
    return Number.isFinite(num) ? Math.max(max, num) : max;
  }, 0);
  return `T-${String(maxNum + 1).padStart(3, '0')}`;
}

function simulatedPnl(total: number, seed: number): number {
  const wave = Math.sin(seed) * 0.5;
  return Number.parseFloat((wave * total * 0.02).toFixed(2));
}

export default function PaperTrading() {
  const btc = cryptoAssets.find(a => a.symbol === 'BTC');
  const marketPrice = btc?.price ?? 104283.42;
  const availableUsdt = 5524.17;

  const [timeframe, setTimeframe] = useState('1H');
  const [orderSide, setOrderSide] = useState<'buy' | 'sell'>('buy');
  const [orderType, setOrderType] = useState<'market' | 'limit'>('market');
  const [tradeFilter, setTradeFilter] = useState<'all' | 'open' | 'filled'>('all');
  const [priceInput, setPriceInput] = useState(marketPrice.toFixed(2));
  const [amountInput, setAmountInput] = useState('0.05');
  const [orderHistory, setOrderHistory] = useState<Trade[]>(recentTrades);

  const numericPrice = Number.parseFloat(priceInput.replace(/,/g, '')) || marketPrice;
  const executionPrice = orderType === 'market' ? marketPrice : numericPrice;
  const numericAmount = Number.parseFloat(amountInput) || 0;
  const total = executionPrice * numericAmount;

  const filteredTrades = useMemo(() => {
    if (tradeFilter === 'all') return orderHistory;
    if (tradeFilter === 'open') return orderHistory.filter(t => t.status === 'pending');
    return orderHistory.filter(t => t.status === 'filled');
  }, [orderHistory, tradeFilter]);

  useEffect(() => {
    const timer = setInterval(() => {
      setOrderHistory(prev => {
        const nextPending = prev.find(t => t.status === 'pending');
        if (!nextPending) return prev;

        return prev.map(t => {
          if (t.id !== nextPending.id) return t;
          const pnl = simulatedPnl(t.total, Date.now() + Number.parseInt(t.id.replace('T-', ''), 10));
          return { ...t, status: 'filled', pnl: Number.parseFloat(pnl.toFixed(2)) };
        });
      });
    }, 5000);

    return () => clearInterval(timer);
  }, []);

  const setQuickAmount = (pct: number) => {
    const amount = (availableUsdt * pct) / executionPrice;
    setAmountInput(amount.toFixed(4));
  };

  const placeOrder = () => {
    if (!Number.isFinite(numericAmount) || numericAmount <= 0) return;

    const now = new Date();
    setOrderHistory(prev => {
      const trade: Trade = {
        id: buildTradeId(prev),
        pair: 'BTC/USDT',
        side: orderSide,
        price: executionPrice,
        amount: numericAmount,
        total: Number.parseFloat(total.toFixed(2)),
        time: now.toISOString().slice(11, 19),
        status: orderType === 'limit' ? 'pending' : 'filled',
        pnl: orderType === 'market' ? simulatedPnl(total, now.getTime()) : undefined,
      };
      return [trade, ...prev];
    });
  };

  return (
    <div className="space-y-4 animate-slide-up">
      <div className="grid grid-cols-5 gap-3">
        <Card>
          <CardBody className="py-3">
            <StatValue label="Balance" value={formatCurrency(portfolioData.totalValue)} change={portfolioData.dayPnlPercent} />
          </CardBody>
        </Card>
        <Card>
          <CardBody className="py-3">
            <StatValue label="Available" value={formatCurrency(availableUsdt)} />
          </CardBody>
        </Card>
        <Card>
          <CardBody className="py-3">
            <StatValue label="Day P&L" value={formatCurrency(portfolioData.dayPnl)} change={portfolioData.dayPnlPercent} />
          </CardBody>
        </Card>
        <Card>
          <CardBody className="py-3">
            <StatValue label="Open Positions" value="5" sub="across 5 pairs" />
          </CardBody>
        </Card>
        <Card>
          <CardBody className="py-3">
            <StatValue label="Today's Trades" value={String(orderHistory.length)} sub={`${orderHistory.filter(t => t.status === 'filled').length} filled`} />
          </CardBody>
        </Card>
      </div>

      <div className="grid grid-cols-4 gap-3">
        <Card className="col-span-3">
          <CardHeader>
            <div className="flex items-center gap-3">
              <CardTitle>BTC/USDT</CardTitle>
              <span className="text-sm font-mono font-semibold text-text-primary tabular-nums">{formatCurrency(marketPrice)}</span>
              <Badge variant="success">+2.34%</Badge>
            </div>
            <div className="flex items-center gap-1">
              {['5m', '15m', '1H', '4H', '1D'].map(tf => (
                <Chip key={tf} active={timeframe === tf} onClick={() => setTimeframe(tf)}>{tf}</Chip>
              ))}
            </div>
          </CardHeader>
          <CardBody className="p-2">
            <div className="h-[220px]">
              <CandlestickChart />
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>New Order</CardTitle>
            <Badge variant="accent">Paper</Badge>
          </CardHeader>
          <CardBody className="space-y-3">
            <div className="grid grid-cols-2 gap-1 bg-bg-tertiary rounded p-0.5">
              <button
                onClick={() => setOrderSide('buy')}
                className={cn(
                  'py-1.5 rounded text-xs font-semibold transition-all cursor-pointer',
                  orderSide === 'buy' ? 'bg-profit/20 text-profit' : 'text-text-muted hover:text-text-secondary',
                )}
              >BUY</button>
              <button
                onClick={() => setOrderSide('sell')}
                className={cn(
                  'py-1.5 rounded text-xs font-semibold transition-all cursor-pointer',
                  orderSide === 'sell' ? 'bg-loss/20 text-loss' : 'text-text-muted hover:text-text-secondary',
                )}
              >SELL</button>
            </div>

            <div className="flex gap-1">
              <Chip active={orderType === 'market'} onClick={() => setOrderType('market')}>Market</Chip>
              <Chip active={orderType === 'limit'} onClick={() => setOrderType('limit')}>Limit</Chip>
            </div>

            <div className="space-y-2">
              {orderType === 'limit' && (
                <div>
                  <label className="text-[10px] uppercase tracking-wider text-text-muted font-medium block mb-1">Price</label>
                  <input
                    type="text"
                    value={priceInput}
                    onChange={e => setPriceInput(e.target.value)}
                    className="w-full bg-bg-tertiary border border-border rounded text-xs px-3 py-2 font-mono text-text-primary focus:outline-none focus:border-accent/50 tabular-nums"
                  />
                </div>
              )}
              <div>
                <label className="text-[10px] uppercase tracking-wider text-text-muted font-medium block mb-1">Amount (BTC)</label>
                <input
                  type="text"
                  value={amountInput}
                  onChange={e => setAmountInput(e.target.value)}
                  className="w-full bg-bg-tertiary border border-border rounded text-xs px-3 py-2 font-mono text-text-primary focus:outline-none focus:border-accent/50 tabular-nums"
                />
              </div>
              <div>
                <label className="text-[10px] uppercase tracking-wider text-text-muted font-medium block mb-1">Total (USDT)</label>
                <input
                  type="text"
                  value={formatCurrency(total)}
                  className="w-full bg-bg-tertiary border border-border rounded text-xs px-3 py-2 font-mono text-text-primary focus:outline-none focus:border-accent/50 tabular-nums"
                  readOnly
                />
              </div>

              <div className="flex gap-1">
                <button onClick={() => setQuickAmount(0.25)} className="flex-1 py-1 rounded text-[10px] font-mono text-text-muted bg-bg-tertiary border border-border hover:border-border-light hover:text-text-secondary transition-all cursor-pointer">25%</button>
                <button onClick={() => setQuickAmount(0.5)} className="flex-1 py-1 rounded text-[10px] font-mono text-text-muted bg-bg-tertiary border border-border hover:border-border-light hover:text-text-secondary transition-all cursor-pointer">50%</button>
                <button onClick={() => setQuickAmount(0.75)} className="flex-1 py-1 rounded text-[10px] font-mono text-text-muted bg-bg-tertiary border border-border hover:border-border-light hover:text-text-secondary transition-all cursor-pointer">75%</button>
                <button onClick={() => setQuickAmount(1)} className="flex-1 py-1 rounded text-[10px] font-mono text-text-muted bg-bg-tertiary border border-border hover:border-border-light hover:text-text-secondary transition-all cursor-pointer">100%</button>
              </div>
            </div>

            <button
              onClick={placeOrder}
              className={cn(
                'w-full py-2.5 rounded text-xs font-semibold transition-all cursor-pointer',
                orderSide === 'buy'
                  ? 'bg-profit/20 text-profit border border-profit/30 hover:bg-profit/30'
                  : 'bg-loss/20 text-loss border border-loss/30 hover:bg-loss/30',
              )}
            >
              {orderSide === 'buy' ? 'BUY' : 'SELL'} BTC
            </button>
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Order History</CardTitle>
          <div className="flex items-center gap-1">
            <Chip active={tradeFilter === 'all'} onClick={() => setTradeFilter('all')}>All</Chip>
            <Chip active={tradeFilter === 'open'} onClick={() => setTradeFilter('open')}>Open</Chip>
            <Chip active={tradeFilter === 'filled'} onClick={() => setTradeFilter('filled')}>Filled</Chip>
          </div>
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
              {filteredTrades.map(trade => (
                <tr key={trade.id} className="hover:bg-bg-hover transition-colors">
                  <td className="px-4 py-2.5 font-mono text-text-muted">{trade.id}</td>
                  <td className="px-4 py-2.5 font-mono font-medium text-text-primary">{trade.pair}</td>
                  <td className="px-4 py-2.5">
                    <Badge variant={trade.side === 'buy' ? 'success' : 'danger'}>{trade.side.toUpperCase()}</Badge>
                  </td>
                  <td className="px-4 py-2.5 font-mono text-right text-text-primary tabular-nums">{formatCurrency(trade.price)}</td>
                  <td className="px-4 py-2.5 font-mono text-right text-text-secondary tabular-nums">{trade.amount}</td>
                  <td className="px-4 py-2.5 font-mono text-right text-text-primary tabular-nums">{formatCurrency(trade.total)}</td>
                  <td className="px-4 py-2.5 font-mono text-text-muted">{trade.time}</td>
                  <td className="px-4 py-2.5">
                    <Badge variant={trade.status === 'filled' ? 'accent' : trade.status === 'pending' ? 'warning' : 'default'}>
                      {trade.status}
                    </Badge>
                  </td>
                  <td className={cn('px-4 py-2.5 font-mono text-right tabular-nums',
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
