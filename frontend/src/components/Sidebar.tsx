'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Activity,
  BarChart3,
  Bot,
  BrainCircuit,
  ChevronRight,
  Database,
  LineChart,
  Menu,
  Shield,
  X,
  Zap,
} from 'lucide-react';
import DevModeToggle from './DevModeToggle';
import ConnectionStatus from './ConnectionStatus';
import KillSwitch from './AutomationHub/KillSwitch';
import styles from './Sidebar.module.css';

const links = [
  { href: '/', label: 'Overview', icon: BarChart3, badge: 'CORE' },
  { href: '/markets', label: 'Markets', icon: Activity, badge: 'LIVE' },
  { href: '/paper', label: 'Paper Trading', icon: Zap, badge: 'SIM' },
  { href: '/autonomous', label: 'Autonomous AI', icon: Bot, badge: 'AUTO' },
  { href: '/backtests', label: 'Backtests', icon: LineChart, badge: 'LAB' },
  { href: '/models', label: 'Models', icon: BrainCircuit, badge: 'ML' },
  { href: '/data', label: 'Data', icon: Database, badge: 'OPS' },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [isOpen, setIsOpen] = useState(true);

  useEffect(() => {
    const syncViewport = () => setIsOpen(window.innerWidth > 768);
    syncViewport();
    window.addEventListener('resize', syncViewport);
    return () => window.removeEventListener('resize', syncViewport);
  }, []);

  return (
    <>
      <button
        className={styles.hamburger}
        onClick={() => setIsOpen((current) => !current)}
        aria-label={isOpen ? 'Close navigation' : 'Open navigation'}
      >
        {isOpen ? <X size={20} /> : <Menu size={20} />}
      </button>

      {isOpen ? <div className={styles.overlay} onClick={() => setIsOpen(false)} /> : null}

      <aside className={`${styles.sidebar} ${isOpen ? styles.open : ''}`}>
        <div className={styles.logoBlock}>
          <div className={styles.logoMark}>
            <BarChart3 size={18} />
          </div>
          <div className={styles.logoCopy}>
            <span className={styles.kicker}>MarketPy</span>
            <h2>Control Room</h2>
            <p>Trading simulator and model operations</p>
          </div>
        </div>

        <div className={styles.navSection}>
          <div className="terminalLabel">Navigation Matrix</div>
          <nav className={styles.nav}>
            {links.map((link) => {
              const Icon = link.icon;
              const isActive = pathname === link.href || (link.href !== '/' && pathname.startsWith(link.href));

              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`${styles.navLink} ${isActive ? styles.active : ''}`}
                  onClick={() => {
                    if (window.innerWidth <= 768) {
                      setIsOpen(false);
                    }
                  }}
                >
                  <span className={styles.navIcon}>
                    <Icon size={16} />
                  </span>
                  <span className={styles.navText}>{link.label}</span>
                  <span className={styles.navBadge}>{link.badge}</span>
                  {isActive ? <ChevronRight size={15} className={styles.navArrow} /> : null}
                </Link>
              );
            })}
          </nav>
        </div>

        <div className={styles.stack}>
          <div className={styles.systemCard}>
            <div className={styles.systemHeader}>
              <span className="terminalLabel">
                <Shield size={13} />
                System State
              </span>
              <span className={styles.statusChip}>Stable</span>
            </div>
            <ConnectionStatus />
          </div>

          <DevModeToggle />
          <KillSwitch />
        </div>
      </aside>
    </>
  );
}
