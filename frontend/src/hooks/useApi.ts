'use client';

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from 'react';
import { subscribeToMockMode, getMockMode } from '@/components/DevModeToggle';
import { mockDataHealth, mockMarkets, mockPortfolio } from '@/lib/mockData';
import {
  ApiClientError,
  getApiUrl,
  getNextBackoff,
  resolvePollingInterval,
} from '@/lib/apiRuntime';

type Validator<T> = (value: unknown) => value is T;
type MockDataFactory<T> = () => T | undefined;

interface UseApiOptions<T> {
  initialData?: T;
  pollInterval?: number;
  fastPollInterval?: number;
  slowPollInterval?: number;
  wsConnected?: boolean;
  enableBackoff?: boolean;
  backoffMultiplier?: number;
  maxBackoffMs?: number;
  enabled?: boolean;
  timeoutMs?: number;
  validate?: Validator<T>;
  mockData?: T | MockDataFactory<T>;
}

const apiCache = new Map<string, { data: unknown; usingMockData: boolean; updatedAt: number }>();

function getDefaultMockData<T>(endpoint: string): T | undefined {
  if (endpoint === '/markets') {
    return mockMarkets as T;
  }

  if (endpoint === '/portfolio') {
    return mockPortfolio as T;
  }

  if (endpoint === '/paper/status') {
    return {
      is_running: false,
      mode: 'BACKTEST',
      markets_count: mockMarkets.length,
      signal_count: 0,
      trade_count: mockPortfolio.trades.length,
      total_equity: mockPortfolio.total_equity,
      total_pnl: mockPortfolio.total_pnl,
      total_pnl_pct: mockPortfolio.total_pnl_pct * 100,
    } as T;
  }

  if (endpoint === '/paper/portfolio') {
    return {
      ...mockPortfolio,
      positions_count: Object.keys(mockPortfolio.positions).length,
      trades_count: mockPortfolio.trades.length,
    } as T;
  }

  if (endpoint.startsWith('/trades')) {
    return [...mockPortfolio.trades].reverse() as T;
  }

  if (endpoint === '/status') {
    return {
      mode: 'BACKTEST',
      is_running: false,
      connected_markets: mockMarkets.map((market) => market.market_id),
      connected_markets_count: mockMarkets.length,
    } as T;
  }

  if (endpoint === '/data/health') {
    return mockDataHealth as T;
  }

  if (endpoint.startsWith('/models/analytics')) {
    const now = Date.now();
    const rows = Array.from({ length: 20 }, (_, index) => ({
      market_id: 'BTCUSDT',
      horizon: '1h',
      signal_ts: new Date(now - (index + 2) * 3600_000).toISOString(),
      resolved_ts: new Date(now - index * 600_000).toISOString(),
      base_price: 67000 + index * 10,
      predicted_price: 67100 + index * 8,
      actual_price: 67080 + index * 9,
      abs_error: 20 + (index % 4),
      error_pct: 0.001 + (index % 5) * 0.0001,
      correct_direction: index % 3 !== 0,
    }));

    return {
      summary: {
        resolved_predictions: rows.length,
        pending_predictions: 8,
        directional_accuracy: 0.67,
        mean_error_pct: 0.0014,
        adaptive_kelly_multiplier: 1.12,
      },
      recent_predictions: rows.slice(0, 12),
      live_preview: rows.slice(0, 8).map((row) => ({
        market_id: row.market_id,
        horizon: row.horizon,
        signal_ts: row.signal_ts,
        due_ts: new Date(new Date(row.signal_ts).getTime() + 3600_000).toISOString(),
        base_price: row.base_price,
        predicted_price: row.predicted_price,
        current_price: row.actual_price,
        provisional_error: row.predicted_price - row.actual_price,
        provisional_error_pct: (row.predicted_price - row.actual_price) / row.base_price,
      })),
      chart: rows.map((row) => ({
        t: row.resolved_ts,
        predicted: row.predicted_price,
        actual: row.actual_price,
        market_id: row.market_id,
        horizon: row.horizon,
      })),
      filters: { horizon: '1h', limit: 120 },
    } as T;
  }

  return undefined;
}

function buildMockData<T>(endpoint: string, mockData?: T | MockDataFactory<T>): T | undefined {
  if (typeof mockData === 'function') {
    return (mockData as MockDataFactory<T>)();
  }

  if (mockData !== undefined) {
    return mockData;
  }

  return getDefaultMockData<T>(endpoint);
}

async function readJsonResponse<T>(
  endpoint: string,
  init: RequestInit,
  options: { timeoutMs: number; validate?: Validator<T> },
): Promise<T> {
  const url = getApiUrl(endpoint);
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), options.timeoutMs);

  try {
    const response = await fetch(url, {
      ...init,
      signal: controller.signal,
      headers: {
        Accept: 'application/json',
        ...(init.headers ?? {}),
      },
    });

    if (!response.ok) {
      throw new ApiClientError({
        kind: 'http',
        message: `Request failed with HTTP ${response.status}`,
        endpoint,
        url,
        statusCode: response.status,
      });
    }

    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      throw new ApiClientError({
        kind: 'parse',
        message: 'Response body was not valid JSON',
        endpoint,
        url,
      });
    }

    if (options.validate && !options.validate(payload)) {
      throw new ApiClientError({
        kind: 'validation',
        message: 'Response shape did not match the expected contract',
        endpoint,
        url,
      });
    }

    return payload as T;
  } catch (error) {
    if (error instanceof ApiClientError) {
      throw error;
    }

    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiClientError({
        kind: 'timeout',
        message: `Request timed out after ${options.timeoutMs}ms`,
        endpoint,
        url,
      });
    }

    throw new ApiClientError({
      kind: 'network',
      message: error instanceof Error ? error.message : 'Network request failed',
      endpoint,
      url,
    });
  } finally {
    clearTimeout(timeoutId);
  }
}

export function useApi<T>(endpoint: string, options: UseApiOptions<T> = {}) {
  const {
    initialData,
    pollInterval,
    fastPollInterval,
    slowPollInterval,
    wsConnected,
    enableBackoff = true,
    backoffMultiplier = 1.5,
    maxBackoffMs = 30000,
    enabled = true,
    timeoutMs = 8000,
    validate,
    mockData,
  } = options;

  const isMockMode = useSyncExternalStore(subscribeToMockMode, () => getMockMode(), () => true);
  const cacheKey = `${isMockMode ? 'mock' : 'live'}:${endpoint}`;
  const cachedEntry = apiCache.get(cacheKey);
  const [data, setData] = useState<T | undefined>(() => (cachedEntry?.data as T | undefined) ?? initialData);
  const [isLoading, setIsLoading] = useState(() => cachedEntry == null && initialData == null);
  const [error, setError] = useState<ApiClientError | null>(null);
  const [usingMockData, setUsingMockData] = useState(() => cachedEntry?.usingMockData ?? false);
  const [backoffMs, setBackoffMs] = useState(0);
  const [lastUpdated, setLastUpdated] = useState<number | null>(() => cachedEntry?.updatedAt ?? null);
  const dataRef = useRef<T | undefined>((cachedEntry?.data as T | undefined) ?? initialData);

  useEffect(() => {
    dataRef.current = data;
  }, [data]);

  useEffect(() => {
    const cached = apiCache.get(cacheKey);
    if (cached) {
      setData(cached.data as T);
      setUsingMockData(cached.usingMockData);
      setLastUpdated(cached.updatedAt);
      setIsLoading(false);
      setError(null);
      return;
    }

    setData(initialData);
    setUsingMockData(false);
    setLastUpdated(null);
    setIsLoading(initialData === undefined);
    setError(null);
  }, [cacheKey, initialData]);

  const fetchData = useCallback(async (params?: { silent?: boolean }) => {
    if (!enabled || !endpoint) {
      return;
    }

    const silent = params?.silent ?? false;
    if (!silent || dataRef.current == null) {
      setIsLoading(true);
    }

    if (isMockMode) {
      const nextMockData = buildMockData(endpoint, mockData);
      if (nextMockData === undefined) {
        setError(
          new ApiClientError({
            kind: 'validation',
            message: 'Demo mode is enabled, but no demo payload exists for this endpoint.',
            endpoint,
            url: endpoint,
          }),
        );
        setUsingMockData(false);
        setIsLoading(false);
        return;
      }

      const updatedAt = Date.now();
      setData(nextMockData);
      setUsingMockData(true);
      setError(null);
      setBackoffMs(0);
      setLastUpdated(updatedAt);
      apiCache.set(cacheKey, { data: nextMockData, usingMockData: true, updatedAt });
      setIsLoading(false);
      return;
    }

    try {
      const nextData = await readJsonResponse<T>(endpoint, {}, { timeoutMs, validate });
      const updatedAt = Date.now();
      setData(nextData);
      setUsingMockData(false);
      setError(null);
      setBackoffMs(0);
      setLastUpdated(updatedAt);
      apiCache.set(cacheKey, { data: nextData, usingMockData: false, updatedAt });
    } catch (nextError) {
      const normalizedError =
        nextError instanceof ApiClientError
          ? nextError
          : new ApiClientError({
              kind: 'network',
              message: 'Network request failed',
              endpoint,
              url: getApiUrl(endpoint),
            });

      setUsingMockData(false);
      setError(normalizedError);
      if (enableBackoff && pollInterval) {
        setBackoffMs((current) =>
          getNextBackoff({
            currentBackoffMs: current,
            basePollInterval: fastPollInterval ?? pollInterval,
            backoffMultiplier,
            maxBackoffMs,
          }),
        );
      }
    } finally {
      setIsLoading(false);
    }
  }, [
    backoffMultiplier,
    cacheKey,
    enableBackoff,
    endpoint,
    fastPollInterval,
    isMockMode,
    maxBackoffMs,
    mockData,
    pollInterval,
    timeoutMs,
    validate,
    enabled,
  ]);

  const activePollInterval = resolvePollingInterval({
    pollInterval,
    fastPollInterval,
    slowPollInterval,
    wsConnected,
  });

  useEffect(() => {
    if (!enabled || !endpoint) {
      return;
    }

    void fetchData({ silent: dataRef.current !== undefined });

    const intervalMs = activePollInterval ? activePollInterval + backoffMs : undefined;
    if (!intervalMs) {
      return;
    }

    const timer = setInterval(() => {
      void fetchData({ silent: true });
    }, intervalMs);

    return () => clearInterval(timer);
  }, [activePollInterval, backoffMs, enabled, endpoint, fetchData]);

  const refetch = useCallback(() => fetchData({ silent: false }), [fetchData]);

  return {
    data,
    isLoading,
    error,
    refetch,
    usingMockData,
    isMockMode,
    activePollInterval: activePollInterval ? activePollInterval + backoffMs : undefined,
    wsConnected: wsConnected ?? null,
    lastUpdated,
  };
}

export async function postApi<T>(
  endpoint: string,
  body: unknown,
  options?: { validate?: Validator<T>; timeoutMs?: number },
): Promise<T> {
  if (getMockMode()) {
    throw new ApiClientError({
      kind: 'validation',
      message: 'Mutating requests are disabled while Demo mode is active.',
      endpoint,
      url: endpoint,
    });
  }

  return readJsonResponse<T>(
    endpoint,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    },
    {
      timeoutMs: options?.timeoutMs ?? 10000,
      validate: options?.validate,
    },
  );
}
