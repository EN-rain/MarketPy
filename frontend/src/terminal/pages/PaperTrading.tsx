'use client';

import { useMemo, useState } from 'react';
import { postApi, useApi } from '@/hooks/useApi';
import { useWebSocket } from '@/hooks/useWebSocket';
import { InlineNotice } from '@/components/RequestState';
import { Card, CardHeader, CardTitle, CardBody, Badge, Chip, StatValue } from '../components/UI';
import { cn } from '../utils/cn';

type CandlePoint = {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

type MarketDetail = {
  market_id: string;
  question: string;
  mid: number;
  change_24h_pct?: number;
  candles?: CandlePoint[];
};

type PortfolioPosition = {
  side: string;
  size: number;
  avg_entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  realized_pnl: number;
  market_value: number;
};

type PortfolioRecord = {
  cash: number;
  initial_cash: number;
  total_equity: number;
  total_pnl: number;
  total_pnl_pct: number;
  positions_count: number;
  trades_count: number;
  positions: Record<string, PortfolioPosition>;
};

type PaperStatus = {
  is_running: boolean;
  mode: string;
  markets_count: number;
  signal_count: number;
  trade_count: number;
  total_equity: number;
  total_pnl: number;
  total_pnl_pct: number;
};

type ApiTrade = {
  id: string;
  timestamp: string;
  market_id: string;
  action: string;
  price: number;
  size: number;
  fee: number;
  pnl?: number | null;
  strategy: string;
};

type UiTrade = {
  id: string;
  pair: string;
  side: 'buy' | 'sell';
  price: number;
  amount: number;
  total: number;
  time: string;
  status: 'filled' | 'pending' | 'cancelled';
  pnl?: number;
};

type ManualOrderResponse = {
  status: 'filled' | 'rejected';
  market_id: string;
  side: string;
  size: number;
  price?: number | null;
  fee?: number | null;
  pnl?: number | null;
  timestamp?: string | null;
  strategy?: string | null;
  reason?: string | null;
};

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  }).format(Number.isFinite(value) ? value : 0);
}

function formatTime(timestamp: string): string {
  const parsed = new Date(timestamp);
  return Number.isNaN(parsed.valueOf()) ? '--:--:--' : parsed.toISOString().slice(11, 19);
}

function toUiTrade(trade: ApiTrade): UiTrade {
  const side = trade.action.includes('BUY') ? 'buy' : 'sell';
  return {
    id: trade.id,
    pair: trade.market_id.replace('USDT', '/USDT'),
    side,
    price: trade.price,
    amount: trade.size,
    total: trade.price * trade.size,
    time: formatTime(trade.timestamp),
    status: 'filled',
    pnl: trade.pnl == null ? undefined : trade.pnl,
  };
}

function CandlestickChart({ candles }: { candles: CandlePoint[] }) {
  const safeCandles = candles.length > 0
    ? candles
    : [
        { timestamp: '', open: 1, high: 1, low: 1, close: 1, volume: 0 },
        { timestamp: '', open: 1, high: 1, low: 1, close: 1, volume: 0 },
      ];

  const allPrices = safeCandles.flatMap((candle) => [candle.high, candle.low]);
  const min = Math.min(...allPrices);
  const max = Math.max(...allPrices);
  const range = max - min || 1;
  const w = 700;
  const h = 220;
  const padding = 10;
  const candleW = (w - padding * 2) / safeCandles.length;
  const bodyW = candleW * 0.6;

  const scaleY = (price: number) => padding + (1 - (price - min) / range) * (h - padding * 2);

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-full w-full">
      {[0, 0.25, 0.5, 0.75, 1].map((pct) => {
        const y = padding + pct * (h - padding * 2);
        const price = max - pct * range;
        return (
          <g key={pct}>
            <line x1={padding} y1={y} x2={w - padding} y2={y} stroke="#1e2030" strokeWidth="0.5" />
            <text x={w - 5} y={y - 3} fill="#565868" fontSize="7" fontFamily="JetBrains Mono" textAnchor="end">
              {price.toFixed(2)}
            </text>
          </g>
        );
      })}
      {safeCandles.map((candle, index) => {
        const x = padding + index * candleW + candleW / 2;
        const isGreen = candle.close >= candle.open;
        const color = isGreen ? '#00e676' : '#ff4757';
        const bodyTop = scaleY(Math.max(candle.open, candle.close));
        const bodyBot = scaleY(Math.min(candle.open, candle.close));
        const bodyH = Math.max(bodyBot - bodyTop, 1);
        return (
          <g key={`${candle.timestamp}-${index}`}>
            <line x1={x} y1={scaleY(candle.high)} x2={x} y2={scaleY(candle.low)} stroke={color} strokeWidth="1" />
            <rect x={x - bodyW / 2} y={bodyTop} width={bodyW} height={bodyH} fill={color} rx="0.5" opacity="0.85" />
          </g>
        );
      })}
    </svg>
  );
}

export default function PaperTrading() {
  const [timeframe, setTimeframe] = useState('1H');
  const [orderSide, setOrderSide] = useState<'buy' | 'sell'>('buy');
  const [orderType, setOrderType] = useState<'market' | 'limit'>('market');
  const [tradeFilter, setTradeFilter] = useState<'all' | 'open' | 'filled'>('all');
  const [priceInput, setPriceInput] = useState('');
  const [amountInput, setAmountInput] = useState('0.05');
  const [livePrice, setLivePrice] = useState<number | null>(null);
  const [liveChangePct, setLiveChangePct] = useState<number | null>(null);
  const [actionMessage, setActionMessage] = useState<{ variant: 'success' | 'warning' | 'error'; message: string } | null>(null);
  const [isSubmittingOrder, setIsSubmittingOrder] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [isStopping, setIsStopping] = useState(false);
  const [isResetting, setIsResetting] = useState(false);

  const marketRequest = useApi<MarketDetail>('/market/BTCUSDT', { pollInterval: 5000 });
  const portfolioRequest = useApi<PortfolioRecord>('/paper/portfolio', { pollInterval: 3000 });
  const statusRequest = useApi<PaperStatus>('/paper/status', { pollInterval: 3000 });
  const tradesRequest = useApi<ApiTrade[]>('/trades', { pollInterval: 5000 });

  useWebSocket(undefined, {
    onMessage: (message) => {
      const data = (message.data ?? {}) as Record<string, unknown>;
      if (message.type === 'market_update' && String(data.symbol ?? '') === 'BTCUSDT') {
        setLivePrice(Number(data.price ?? 0));
        setLiveChangePct(Number(data.change_24h_pct ?? 0));
      }
      if (message.type === 'paper_trade') {
        void tradesRequest.refetch();
        void portfolioRequest.refetch();
        void statusRequest.refetch();
      }
      if (message.type === 'paper_portfolio') {
        void portfolioRequest.refetch();
        void statusRequest.refetch();
      }
    },
  });

  const marketPrice = livePrice ?? marketRequest.data?.mid ?? 0;
  const marketChangePct = liveChangePct ?? marketRequest.data?.change_24h_pct ?? 0;
  const availableUsdt = portfolioRequest.data?.cash ?? 0;
  const candles = marketRequest.data?.candles ?? [];
  const orderHistory = useMemo(() => (tradesRequest.data ?? []).map(toUiTrade), [tradesRequest.data]);

  const numericPrice = Number.parseFloat(priceInput.replace(/,/g, '')) || marketPrice;
  const executionPrice = orderType === 'market' ? marketPrice : numericPrice;
  const numericAmount = Number.parseFloat(amountInput) || 0;
  const total = executionPrice * numericAmount;

  const filteredTrades = useMemo(() => {
    if (tradeFilter === 'all') {
      return orderHistory;
    }
    if (tradeFilter === 'open') {
      return orderHistory.filter((trade) => trade.status === 'pending');
    }
    return orderHistory.filter((trade) => trade.status === 'filled');
  }, [orderHistory, tradeFilter]);

  const setQuickAmount = (pct: number) => {
    const amount = executionPrice > 0 ? (availableUsdt * pct) / executionPrice : 0;
    setAmountInput(amount.toFixed(4));
  };

  async function refreshPaperData() {
    await Promise.all([
      portfolioRequest.refetch(),
      statusRequest.refetch(),
      tradesRequest.refetch(),
      marketRequest.refetch(),
    ]);
  }

  async function startPaperTrading() {
    setIsStarting(true);
    setActionMessage(null);
    try {
      await postApi('/paper/start', {
        market_ids: ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'],
        strategy: 'momentum',
        initial_cash: 10000,
        fill_model: 'M2',
        fee_rate: 0.02,
      });
      await refreshPaperData();
      setActionMessage({ variant: 'success', message: 'Paper trading engine started.' });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to start paper trading.';
      setActionMessage({ variant: 'error', message });
    } finally {
      setIsStarting(false);
    }
  }

  async function stopPaperTrading() {
    setIsStopping(true);
    setActionMessage(null);
    try {
      await postApi('/paper/stop', {});
      await refreshPaperData();
      setActionMessage({ variant: 'warning', message: 'Paper trading engine stopped.' });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to stop paper trading.';
      setActionMessage({ variant: 'error', message });
    } finally {
      setIsStopping(false);
    }
  }

  async function resetPaperTrading() {
    setIsResetting(true);
    setActionMessage(null);
    try {
      await postApi('/paper/reset', {});
      await refreshPaperData();
      setActionMessage({ variant: 'success', message: 'Paper trading portfolio reset.' });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to reset paper trading.';
      setActionMessage({ variant: 'error', message });
    } finally {
      setIsResetting(false);
    }
  }

  async function placeOrder() {
    if (!statusRequest.data?.is_running) {
      setActionMessage({ variant: 'warning', message: 'Start the paper trading engine before placing orders.' });
      return;
    }
    if (!Number.isFinite(numericAmount) || numericAmount <= 0 || executionPrice <= 0) {
      setActionMessage({ variant: 'warning', message: 'Enter a valid order size and wait for a live BTC price.' });
      return;
    }

    setIsSubmittingOrder(true);
    setActionMessage(null);
    try {
      const result = await postApi<ManualOrderResponse>('/paper/order', {
        market_id: 'BTCUSDT',
        side: orderSide,
        size: numericAmount,
        order_type: orderType,
        limit_price: orderType === 'limit' ? numericPrice : null,
      });
      await refreshPaperData();
      if (result.status === 'filled') {
        setActionMessage({
          variant: 'success',
          message: `${result.side} ${result.market_id} filled at ${formatCurrency(result.price ?? 0)}.`,
        });
      } else {
        setActionMessage({
          variant: 'warning',
          message: result.reason ?? 'Order was rejected.',
        });
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to place paper order.';
      setActionMessage({ variant: 'error', message });
    } finally {
      setIsSubmittingOrder(false);
    }
  }

  return (
    <div className="space-y-4 animate-slide-up">
      {actionMessage ? <InlineNotice variant={actionMessage.variant} message={actionMessage.message} /> : null}

      <div className="grid grid-cols-5 gap-3">
        <Card>
          <CardBody className="py-3">
            <StatValue label="Balance" value={formatCurrency(portfolioRequest.data?.total_equity ?? 0)} change={portfolioRequest.data?.total_pnl_pct ?? 0} />
          </CardBody>
        </Card>
        <Card>
          <CardBody className="py-3">
            <StatValue label="Available" value={formatCurrency(availableUsdt)} />
          </CardBody>
        </Card>
        <Card>
          <CardBody className="py-3">
            <StatValue label="Day P&L" value={formatCurrency(portfolioRequest.data?.total_pnl ?? 0)} change={portfolioRequest.data?.total_pnl_pct ?? 0} />
          </CardBody>
        </Card>
        <Card>
          <CardBody className="py-3">
            <StatValue label="Open Positions" value={String(portfolioRequest.data?.positions_count ?? 0)} sub={`across ${portfolioRequest.data?.positions_count ?? 0} pairs`} />
          </CardBody>
        </Card>
        <Card>
          <CardBody className="py-3">
            <StatValue label="Today's Trades" value={String(orderHistory.length)} sub={`${orderHistory.filter((trade) => trade.status === 'filled').length} filled`} />
          </CardBody>
        </Card>
      </div>

      <div className="grid grid-cols-4 gap-3">
        <Card className="col-span-3">
          <CardHeader>
            <div className="flex items-center gap-3">
              <CardTitle>BTC/USDT</CardTitle>
              <span className="text-sm font-mono font-semibold text-text-primary tabular-nums">{formatCurrency(marketPrice)}</span>
              <Badge variant={marketChangePct >= 0 ? 'success' : 'danger'}>
                {marketChangePct >= 0 ? '+' : ''}{marketChangePct.toFixed(2)}%
              </Badge>
              <Badge variant={statusRequest.data?.is_running ? 'accent' : 'warning'}>
                {statusRequest.data?.is_running ? 'Engine Running' : 'Engine Stopped'}
              </Badge>
            </div>
            <div className="flex items-center gap-1">
              {['5m', '15m', '1H', '4H', '1D'].map((tf) => (
                <Chip key={tf} active={timeframe === tf} onClick={() => setTimeframe(tf)}>{tf}</Chip>
              ))}
            </div>
          </CardHeader>
          <CardBody className="p-2">
            <div className="mb-3 flex gap-2 px-2">
              <button
                type="button"
                onClick={startPaperTrading}
                disabled={isStarting || statusRequest.data?.is_running}
                className="rounded border border-accent/30 bg-accent/10 px-3 py-1.5 text-[11px] font-semibold text-accent disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isStarting ? 'Starting...' : 'Start Engine'}
              </button>
              <button
                type="button"
                onClick={stopPaperTrading}
                disabled={isStopping || !statusRequest.data?.is_running}
                className="rounded border border-loss/30 bg-loss/10 px-3 py-1.5 text-[11px] font-semibold text-loss disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isStopping ? 'Stopping...' : 'Stop Engine'}
              </button>
              <button
                type="button"
                onClick={resetPaperTrading}
                disabled={isResetting || !statusRequest.data?.is_running}
                className="rounded border border-border px-3 py-1.5 text-[11px] font-semibold text-text-secondary disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isResetting ? 'Resetting...' : 'Reset Portfolio'}
              </button>
            </div>
            <div className="h-[220px]">
              <CandlestickChart candles={candles} />
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>New Order</CardTitle>
            <Badge variant="accent">Paper</Badge>
          </CardHeader>
          <CardBody className="space-y-3">
            <div className="grid grid-cols-2 gap-1 rounded bg-bg-tertiary p-0.5">
              <button
                onClick={() => setOrderSide('buy')}
                className={cn(
                  'cursor-pointer rounded py-1.5 text-xs font-semibold transition-all',
                  orderSide === 'buy' ? 'bg-profit/20 text-profit' : 'text-text-muted hover:text-text-secondary',
                )}
              >BUY</button>
              <button
                onClick={() => setOrderSide('sell')}
                className={cn(
                  'cursor-pointer rounded py-1.5 text-xs font-semibold transition-all',
                  orderSide === 'sell' ? 'bg-loss/20 text-loss' : 'text-text-muted hover:text-text-secondary',
                )}
              >SELL</button>
            </div>

            <div className="flex gap-1">
              <Chip active={orderType === 'market'} onClick={() => setOrderType('market')}>Market</Chip>
              <Chip active={orderType === 'limit'} onClick={() => setOrderType('limit')}>Limit</Chip>
            </div>

            <div className="space-y-2">
              {orderType === 'limit' ? (
                <div>
                  <label className="mb-1 block text-[10px] font-medium uppercase tracking-wider text-text-muted">Price</label>
                  <input
                    type="text"
                    value={priceInput}
                    onChange={(event) => setPriceInput(event.target.value)}
                    className="w-full rounded border border-border bg-bg-tertiary px-3 py-2 text-xs font-mono tabular-nums text-text-primary focus:border-accent/50 focus:outline-none"
                  />
                </div>
              ) : null}
              <div>
                <label className="mb-1 block text-[10px] font-medium uppercase tracking-wider text-text-muted">Amount (BTC)</label>
                <input
                  type="text"
                  value={amountInput}
                  onChange={(event) => setAmountInput(event.target.value)}
                  className="w-full rounded border border-border bg-bg-tertiary px-3 py-2 text-xs font-mono tabular-nums text-text-primary focus:border-accent/50 focus:outline-none"
                />
              </div>
              <div>
                <label className="mb-1 block text-[10px] font-medium uppercase tracking-wider text-text-muted">Total (USDT)</label>
                <input
                  type="text"
                  value={formatCurrency(total)}
                  className="w-full rounded border border-border bg-bg-tertiary px-3 py-2 text-xs font-mono tabular-nums text-text-primary focus:border-accent/50 focus:outline-none"
                  readOnly
                />
              </div>

              <div className="flex gap-1">
                <button onClick={() => setQuickAmount(0.25)} className="flex-1 cursor-pointer rounded border border-border bg-bg-tertiary py-1 text-[10px] font-mono text-text-muted transition-all hover:border-border-light hover:text-text-secondary">25%</button>
                <button onClick={() => setQuickAmount(0.5)} className="flex-1 cursor-pointer rounded border border-border bg-bg-tertiary py-1 text-[10px] font-mono text-text-muted transition-all hover:border-border-light hover:text-text-secondary">50%</button>
                <button onClick={() => setQuickAmount(0.75)} className="flex-1 cursor-pointer rounded border border-border bg-bg-tertiary py-1 text-[10px] font-mono text-text-muted transition-all hover:border-border-light hover:text-text-secondary">75%</button>
                <button onClick={() => setQuickAmount(1)} className="flex-1 cursor-pointer rounded border border-border bg-bg-tertiary py-1 text-[10px] font-mono text-text-muted transition-all hover:border-border-light hover:text-text-secondary">100%</button>
              </div>
            </div>

            <button
              onClick={placeOrder}
              disabled={isSubmittingOrder || !statusRequest.data?.is_running}
              className={cn(
                'w-full rounded border py-2.5 text-xs font-semibold transition-all disabled:cursor-not-allowed disabled:opacity-50',
                orderSide === 'buy'
                  ? 'border-profit/30 bg-profit/20 text-profit hover:bg-profit/30'
                  : 'border-loss/30 bg-loss/20 text-loss hover:bg-loss/30',
              )}
            >
              {isSubmittingOrder ? 'Submitting...' : `${orderSide === 'buy' ? 'BUY' : 'SELL'} BTC`}
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
                <th className="px-4 py-2 text-left font-medium">ID</th>
                <th className="px-4 py-2 text-left font-medium">Pair</th>
                <th className="px-4 py-2 text-left font-medium">Side</th>
                <th className="px-4 py-2 text-right font-medium">Price</th>
                <th className="px-4 py-2 text-right font-medium">Amount</th>
                <th className="px-4 py-2 text-right font-medium">Total</th>
                <th className="px-4 py-2 text-left font-medium">Time</th>
                <th className="px-4 py-2 text-left font-medium">Status</th>
                <th className="px-4 py-2 text-right font-medium">P&L</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filteredTrades.map((trade) => (
                <tr key={`${trade.id}-${trade.time}`} className="transition-colors hover:bg-bg-hover">
                  <td className="px-4 py-2.5 font-mono text-text-muted">{trade.id}</td>
                  <td className="px-4 py-2.5 font-mono font-medium text-text-primary">{trade.pair}</td>
                  <td className="px-4 py-2.5">
                    <Badge variant={trade.side === 'buy' ? 'success' : 'danger'}>{trade.side.toUpperCase()}</Badge>
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono tabular-nums text-text-primary">{formatCurrency(trade.price)}</td>
                  <td className="px-4 py-2.5 text-right font-mono tabular-nums text-text-secondary">{trade.amount}</td>
                  <td className="px-4 py-2.5 text-right font-mono tabular-nums text-text-primary">{formatCurrency(trade.total)}</td>
                  <td className="px-4 py-2.5 font-mono text-text-muted">{trade.time}</td>
                  <td className="px-4 py-2.5">
                    <Badge variant={trade.status === 'filled' ? 'accent' : trade.status === 'pending' ? 'warning' : 'default'}>
                      {trade.status}
                    </Badge>
                  </td>
                  <td className={cn(
                    'px-4 py-2.5 text-right font-mono tabular-nums',
                    trade.pnl === undefined ? 'text-text-muted' : trade.pnl >= 0 ? 'text-profit' : 'text-loss',
                  )}>
                    {trade.pnl !== undefined ? `${trade.pnl >= 0 ? '+' : ''}${formatCurrency(trade.pnl)}` : '--'}
                  </td>
                </tr>
              ))}
              {filteredTrades.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-4 py-6 text-center text-[11px] font-mono text-text-muted">
                    No paper trades yet.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </CardBody>
      </Card>
    </div>
  );
}
