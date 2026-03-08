'use client';

import { useEffect, useMemo, useState, useSyncExternalStore } from 'react';
import { usePathname } from 'next/navigation';
import { useApi } from '@/hooks/useApi';
import { useWebSocket } from '@/hooks/useWebSocket';
import Sidebar, { navItems, type Page } from './Sidebar';
import { formatIsoDate, formatUtcClock } from '../utils/time';

type MarketSummary = {
  market_id: string;
  question: string;
  mid: number;
  change_24h_pct: number;
};

const pageTitles: Record<Page, string> = {
  overview: 'Overview',
  markets: 'Markets',
  'paper-trading': 'Paper Trading',
  backtests: 'Backtests',
  models: 'AI Models',
  database: 'Database',
  features: 'Feature Store',
  patterns: 'Pattern Detection',
  risk: 'Risk Dashboard',
  execution: 'Execution Quality',
  regime: 'Regime Classification',
  exchanges: 'Exchange Monitoring',
  explainability: 'Explainability',
};

const pageDescriptions: Record<Page, string> = {
  overview: 'Portfolio summary and key metrics',
  markets: 'Real-time market data and AI signals',
  'paper-trading': 'Simulated trading environment',
  backtests: 'Strategy backtesting results',
  models: 'Machine learning model management',
  database: 'Data sources and storage management',
  features: 'Feature definitions, lineage, and drift state',
  patterns: 'Detected technical patterns and targets',
  risk: 'Portfolio and position risk analytics',
  execution: 'Slippage, fill quality, and latency trends',
  regime: 'Regime state, confidence, and transitions',
  exchanges: 'Cross-exchange health and arbitrage',
  explainability: 'SHAP contributions and confidence bounds',
};

function pageFromPath(pathname: string): Page {
  const nav = navItems.find((item) => item.href === pathname);
  return nav?.id ?? 'overview';
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(Number.isFinite(value) ? value : 0);
}

function formatPct(value: number): string {
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
}

export default function TerminalShell({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const activePage = useMemo(() => pageFromPath(pathname), [pathname]);
  const hydrated = useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );
  const [now, setNow] = useState<Date | null>(null);
  const [liveOverrides, setLiveOverrides] = useState<Record<string, Partial<MarketSummary>>>({});

  const { data: markets } = useApi<MarketSummary[]>('/markets', { pollInterval: 5000 });

  useWebSocket(undefined, {
    onMessage: (message) => {
      if (message.type !== 'market_update') {
        return;
      }
      const data = (message.data ?? {}) as Record<string, unknown>;
      const symbol = String(data.symbol ?? '');
      if (!symbol) {
        return;
      }
      setLiveOverrides((current) => ({
        ...current,
        [symbol]: {
          market_id: symbol,
          question: symbol.replace('USDT', ''),
          mid: Number(data.price ?? 0),
          change_24h_pct: Number(data.change_24h_pct ?? 0),
        },
      }));
    },
  });

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const effectiveNow = hydrated ? (now ?? new Date()) : null;

  const mergedMarkets = useMemo(
    () =>
      (markets ?? []).map((market) => ({
        ...market,
        ...liveOverrides[market.market_id],
      })),
    [liveOverrides, markets],
  );

  const btc = mergedMarkets.find((market) => market.market_id === 'BTCUSDT');
  const eth = mergedMarkets.find((market) => market.market_id === 'ETHUSDT');

  return (
    <div className="noise-bg flex h-screen w-screen">
      <Sidebar />

      <main className="ml-[220px] flex h-screen flex-1 flex-col overflow-hidden">
        <header className="flex h-12 shrink-0 items-center justify-between border-b border-border bg-bg-secondary/80 px-6 backdrop-blur-sm">
          <div className="flex items-center gap-3">
            <h2 className="text-sm font-semibold text-text-primary">{pageTitles[activePage]}</h2>
            <span className="text-[10px] text-text-muted">-</span>
            <span className="text-[11px] text-text-muted">{pageDescriptions[activePage]}</span>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="font-mono text-[10px] text-text-muted">BTC</span>
              <span className="tabular-nums font-mono text-xs font-semibold text-text-primary">
                {formatCurrency(btc?.mid ?? 0)}
              </span>
              <span className={`tabular-nums font-mono text-[10px] ${(btc?.change_24h_pct ?? 0) >= 0 ? 'text-profit' : 'text-loss'}`}>
                {formatPct(btc?.change_24h_pct ?? 0)}
              </span>
            </div>
            <div className="h-4 w-px bg-border" />
            <div className="flex items-center gap-2">
              <span className="font-mono text-[10px] text-text-muted">ETH</span>
              <span className="tabular-nums font-mono text-xs font-semibold text-text-primary">
                {formatCurrency(eth?.mid ?? 0)}
              </span>
              <span className={`tabular-nums font-mono text-[10px] ${(eth?.change_24h_pct ?? 0) >= 0 ? 'text-profit' : 'text-loss'}`}>
                {formatPct(eth?.change_24h_pct ?? 0)}
              </span>
            </div>
            <div className="h-4 w-px bg-border" />
            <div className="flex items-center gap-1.5">
              <div className="pulse-dot h-1.5 w-1.5 rounded-full bg-accent" />
              <span className="font-mono text-[10px] text-text-muted">Live</span>
            </div>
            <div className="h-4 w-px bg-border" />
            <div className="flex items-center gap-2">
              <span className="font-mono text-[10px] text-text-muted">{effectiveNow ? formatIsoDate(effectiveNow) : '----/--/--'}</span>
              <span className="font-mono text-[10px] text-text-secondary">{effectiveNow ? formatUtcClock(effectiveNow) : '--:--:-- UTC'}</span>
            </div>
          </div>
        </header>

        <div className="grid-bg relative flex-1 overflow-y-auto p-4">
          <div className="relative z-10">{children}</div>
        </div>
      </main>
    </div>
  );
}
