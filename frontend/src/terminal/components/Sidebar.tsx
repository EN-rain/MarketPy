'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  BarChart3,
  Brain,
  ChevronRight,
  Clock,
  Database,
  FlaskConical,
  LayoutDashboard,
  Repeat2,
  User,
  Wifi,
  Zap,
} from 'lucide-react';
import { cn } from '../utils/cn';
import { formatIsoDate, formatUtcClock } from '../utils/time';

export type Page = 'overview' | 'markets' | 'paper-trading' | 'backtests' | 'models' | 'database';

export type NavItem = {
  id: Page;
  label: string;
  href: string;
  icon: React.ElementType;
};

export const navItems: NavItem[] = [
  { id: 'overview', label: 'Overview', href: '/', icon: LayoutDashboard },
  { id: 'markets', label: 'Markets', href: '/markets', icon: BarChart3 },
  { id: 'paper-trading', label: 'Paper Trading', href: '/paper', icon: Repeat2 },
  { id: 'backtests', label: 'Backtests', href: '/backtests', icon: FlaskConical },
  { id: 'models', label: 'Models', href: '/models', icon: Brain },
  { id: 'database', label: 'Database', href: '/data', icon: Database },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [now, setNow] = useState<Date>(() => new Date());
  const [lastUpdateAt, setLastUpdateAt] = useState(() => Date.now());

  useEffect(() => {
    const clockTimer = setInterval(() => setNow(new Date()), 1000);
    const heartbeatTimer = setInterval(() => setLastUpdateAt(Date.now()), 3000);
    return () => {
      clearInterval(clockTimer);
      clearInterval(heartbeatTimer);
    };
  }, []);

  const secondsAgo = Math.max(0, Math.floor((now.getTime() - lastUpdateAt) / 1000));

  return (
    <aside className="fixed top-0 bottom-0 left-0 z-50 flex w-[220px] flex-col border-r border-border bg-bg-secondary">
      <div className="border-b border-border px-5 py-5">
        <div className="flex items-center gap-2.5">
          <div className="glow-accent flex h-8 w-8 items-center justify-center rounded-lg bg-accent/15">
            <Zap size={16} className="text-accent" />
          </div>
          <div>
            <h1 className="text-sm font-semibold tracking-tight text-text-primary">MarketPy</h1>
            <p className="font-mono text-[10px] uppercase tracking-widest text-text-muted">Terminal v2.4</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-3">
        <p className="px-2 py-2 text-[10px] font-medium uppercase tracking-wider text-text-muted">Navigation</p>
        {navItems.map(item => {
          const isActive = pathname === item.href;
          const Icon = item.icon;

          return (
            <Link
              key={item.id}
              href={item.href}
              className={cn(
                'group flex w-full cursor-pointer items-center gap-2.5 rounded-md px-3 py-2 text-[13px] font-medium transition-all duration-150',
                isActive ? 'glow-accent bg-accent/10 text-accent' : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary',
              )}
            >
              <Icon size={15} className={cn(isActive && 'drop-shadow-[0_0_4px_#00d4aa60]')} />
              <span className="flex-1 text-left">{item.label}</span>
              {isActive ? <ChevronRight size={12} className="opacity-60" /> : null}
            </Link>
          );
        })}
      </nav>

      <div className="space-y-3 border-t border-border p-4">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <div className="pulse-dot h-1.5 w-1.5 rounded-full bg-accent" />
            <span className="font-mono text-[11px] text-accent">Connected</span>
            <span className="text-[10px] text-text-muted">|</span>
            <span className="font-mono text-[10px] text-text-muted">Paper Mode</span>
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <Wifi size={10} className="text-text-muted" />
              <span className="font-mono text-[10px] text-text-muted">Latency</span>
            </div>
            <span className="font-mono text-[10px] text-profit">12ms</span>
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <Clock size={10} className="text-text-muted" />
              <span className="font-mono text-[10px] text-text-muted">Last update</span>
            </div>
            <span className="font-mono text-[10px] text-text-secondary">{secondsAgo}s ago</span>
          </div>

          <div className="flex items-center justify-between">
            <span className="font-mono text-[10px] text-text-muted">Clock</span>
            <span className="font-mono text-[10px] text-text-secondary">{formatUtcClock(now)}</span>
          </div>

          <div className="flex items-center justify-between">
            <span className="font-mono text-[10px] text-text-muted">Date</span>
            <span className="font-mono text-[10px] text-text-secondary">{formatIsoDate(now)}</span>
          </div>
        </div>

        <div className="flex items-center gap-2.5 rounded-md bg-bg-tertiary px-2 py-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-full bg-accent/15">
            <User size={12} className="text-accent" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[11px] font-medium text-text-primary">quant_trader</p>
            <p className="font-mono text-[9px] text-text-muted">PRO Plan</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
