'use client';

import { useEffect, useMemo, useState } from 'react';
import { usePathname } from 'next/navigation';
import Sidebar, { navItems, type Page } from './Sidebar';
import { formatIsoDate, formatUtcClock } from '../utils/time';

const pageTitles: Record<Page, string> = {
  overview: 'Overview',
  markets: 'Markets',
  'paper-trading': 'Paper Trading',
  backtests: 'Backtests',
  models: 'AI Models',
  database: 'Database',
};

const pageDescriptions: Record<Page, string> = {
  overview: 'Portfolio summary and key metrics',
  markets: 'Real-time market data and AI signals',
  'paper-trading': 'Simulated trading environment',
  backtests: 'Strategy backtesting results',
  models: 'Machine learning model management',
  database: 'Data sources and storage management',
};

function pageFromPath(pathname: string): Page {
  const nav = navItems.find((item) => item.href === pathname);
  return nav?.id ?? 'overview';
}

export default function TerminalShell({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const activePage = useMemo(() => pageFromPath(pathname), [pathname]);
  const [now, setNow] = useState<Date>(() => new Date());

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

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
              <span className="tabular-nums font-mono text-xs font-semibold text-text-primary">$104,283</span>
              <span className="tabular-nums font-mono text-[10px] text-profit">+2.34%</span>
            </div>
            <div className="h-4 w-px bg-border" />
            <div className="flex items-center gap-2">
              <span className="font-mono text-[10px] text-text-muted">ETH</span>
              <span className="tabular-nums font-mono text-xs font-semibold text-text-primary">$3,847</span>
              <span className="tabular-nums font-mono text-[10px] text-loss">-1.12%</span>
            </div>
            <div className="h-4 w-px bg-border" />
            <div className="flex items-center gap-1.5">
              <div className="pulse-dot h-1.5 w-1.5 rounded-full bg-accent" />
              <span className="font-mono text-[10px] text-text-muted">Live</span>
            </div>
            <div className="h-4 w-px bg-border" />
            <div className="flex items-center gap-2">
              <span className="font-mono text-[10px] text-text-muted">{formatIsoDate(now)}</span>
              <span className="font-mono text-[10px] text-text-secondary">{formatUtcClock(now)}</span>
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
