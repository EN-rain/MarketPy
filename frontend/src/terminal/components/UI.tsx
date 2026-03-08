import { cn } from '../utils/cn';

export function Card({ children, className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn('bg-bg-card border border-border rounded-lg', className)} {...props}>
      {children}
    </div>
  );
}

export function CardHeader({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn('px-4 py-3 border-b border-border flex items-center justify-between', className)}>
      {children}
    </div>
  );
}

export function CardTitle({ children, className }: { children: React.ReactNode; className?: string }) {
  return <h3 className={cn('text-xs font-semibold text-text-secondary uppercase tracking-wider', className)}>{children}</h3>;
}

export function CardBody({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn('p-4', className)}>{children}</div>;
}

export function Badge({ children, variant = 'default', className }: {
  children: React.ReactNode;
  variant?: 'default' | 'success' | 'danger' | 'warning' | 'info' | 'accent';
  className?: string;
}) {
  const variants = {
    default: 'bg-bg-tertiary text-text-secondary',
    success: 'bg-profit/10 text-profit',
    danger: 'bg-loss/10 text-loss',
    warning: 'bg-warn/10 text-warn',
    info: 'bg-info/10 text-info',
    accent: 'bg-accent/10 text-accent',
  };
  return (
    <span className={cn('inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-medium', variants[variant], className)}>
      {children}
    </span>
  );
}

export function Chip({ children, active, onClick, className }: {
  children: React.ReactNode;
  active?: boolean;
  onClick?: () => void;
  className?: string;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'px-2.5 py-1 rounded text-[11px] font-medium transition-all cursor-pointer',
        active
          ? 'bg-accent/15 text-accent border border-accent/30'
          : 'bg-bg-tertiary text-text-secondary border border-border hover:border-border-light hover:text-text-primary',
        className
      )}
    >
      {children}
    </button>
  );
}

export function MiniSparkline({ data, color = 'accent', width = 80, height = 24 }: {
  data: number[];
  color?: 'accent' | 'profit' | 'loss';
  width?: number;
  height?: number;
}) {
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((v - min) / range) * height;
    return `${x},${y}`;
  }).join(' ');

  const colorMap = {
    accent: '#00d4aa',
    profit: '#00e676',
    loss: '#ff4757',
  };

  return (
    <svg width={width} height={height} className="overflow-visible">
      <polyline
        points={points}
        fill="none"
        stroke={colorMap[color]}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function ProgressBar({ value, max = 100, color = 'accent', className }: {
  value: number;
  max?: number;
  color?: 'accent' | 'profit' | 'loss' | 'warn' | 'info';
  className?: string;
}) {
  const pct = Math.min((value / max) * 100, 100);
  const colorMap = {
    accent: 'bg-accent',
    profit: 'bg-profit',
    loss: 'bg-loss',
    warn: 'bg-warn',
    info: 'bg-info',
  };
  return (
    <div className={cn('h-1 rounded-full bg-bg-tertiary overflow-hidden', className)}>
      <div className={cn('h-full rounded-full transition-all duration-500', colorMap[color])} style={{ width: `${pct}%` }} />
    </div>
  );
}

export function StatValue({ label, value, sub, change, className }: {
  label: string;
  value: string;
  sub?: string;
  change?: number;
  className?: string;
}) {
  return (
    <div className={cn('space-y-1', className)}>
      <p className="text-[10px] uppercase tracking-wider text-text-muted font-medium">{label}</p>
      <p className="text-lg font-mono font-semibold text-text-primary tabular-nums">{value}</p>
      {(sub || change !== undefined) && (
        <div className="flex items-center gap-1.5">
          {change !== undefined && (
            <span className={cn('text-[11px] font-mono font-medium tabular-nums', change >= 0 ? 'text-profit' : 'text-loss')}>
              {change >= 0 ? '+' : ''}{change.toFixed(2)}%
            </span>
          )}
          {sub && <span className="text-[10px] text-text-muted">{sub}</span>}
        </div>
      )}
    </div>
  );
}
