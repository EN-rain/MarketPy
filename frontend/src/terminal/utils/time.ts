export function formatUtcClock(date: Date): string {
  return date.toISOString().slice(11, 19) + ' UTC';
}

export function formatIsoDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

export function formatTimeFromMs(ms: number): string {
  return new Date(ms).toISOString().slice(11, 19);
}

export function formatRelativeTime(fromMs: number, nowMs: number): string {
  const delta = Math.max(0, nowMs - fromMs);
  const seconds = Math.floor(delta / 1000);
  if (seconds < 5) return 'just now';
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}
