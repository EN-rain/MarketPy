export const DEFAULT_API_BASE_URL = 'http://localhost:8000/api';
export const DEFAULT_WS_URL = 'ws://localhost:8000/ws/live';

export type ApiErrorKind = 'network' | 'http' | 'timeout' | 'parse' | 'validation';

export class ApiClientError extends Error {
  kind: ApiErrorKind;
  endpoint: string;
  url: string;
  statusCode?: number;

  constructor(params: {
    kind: ApiErrorKind;
    message: string;
    endpoint: string;
    url: string;
    statusCode?: number;
  }) {
    super(params.message);
    this.name = 'ApiClientError';
    this.kind = params.kind;
    this.endpoint = params.endpoint;
    this.url = params.url;
    this.statusCode = params.statusCode;
  }
}

function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/, '');
}

export function getApiBaseUrl(): string {
  return trimTrailingSlash(process.env.NEXT_PUBLIC_API_URL ?? DEFAULT_API_BASE_URL);
}

export function getApiUrl(endpoint: string): string {
  if (!endpoint.startsWith('/')) {
    throw new Error(`API endpoint must start with "/": ${endpoint}`);
  }

  return `${getApiBaseUrl()}${endpoint}`;
}

export function getWebSocketUrl(): string {
  return process.env.NEXT_PUBLIC_WS_URL ?? DEFAULT_WS_URL;
}

export function resolvePollingInterval(params: {
  pollInterval?: number;
  fastPollInterval?: number;
  slowPollInterval?: number;
  wsConnected?: boolean;
}): number | undefined {
  const { pollInterval, fastPollInterval, slowPollInterval, wsConnected } = params;

  if (wsConnected == null) {
    return pollInterval;
  }

  return wsConnected
    ? (slowPollInterval ?? pollInterval)
    : (fastPollInterval ?? pollInterval);
}

export function getNextBackoff(params: {
  currentBackoffMs: number;
  basePollInterval: number;
  backoffMultiplier: number;
  maxBackoffMs: number;
}): number {
  const { currentBackoffMs, basePollInterval, backoffMultiplier, maxBackoffMs } = params;
  const seed = currentBackoffMs > 0 ? currentBackoffMs : basePollInterval;
  return Math.min(maxBackoffMs, Math.round(seed * backoffMultiplier));
}
