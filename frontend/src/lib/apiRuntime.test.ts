import { describe, expect, it } from 'vitest';
import {
  DEFAULT_API_BASE_URL,
  getApiUrl,
  getNextBackoff,
  resolvePollingInterval,
} from './apiRuntime';

describe('apiRuntime', () => {
  it('uses a single deterministic api base', () => {
    delete process.env.NEXT_PUBLIC_API_URL;
    expect(getApiUrl('/status')).toBe(`${DEFAULT_API_BASE_URL}/status`);
  });

  it('selects polling interval from websocket state', () => {
    expect(
      resolvePollingInterval({
        pollInterval: 5000,
        fastPollInterval: 2000,
        slowPollInterval: 10000,
        wsConnected: true,
      }),
    ).toBe(10000);

    expect(
      resolvePollingInterval({
        pollInterval: 5000,
        fastPollInterval: 2000,
        slowPollInterval: 10000,
        wsConnected: false,
      }),
    ).toBe(2000);
  });

  it('caps exponential backoff', () => {
    let backoff = 0;

    for (let index = 0; index < 10; index += 1) {
      backoff = getNextBackoff({
        currentBackoffMs: backoff,
        basePollInterval: 2000,
        backoffMultiplier: 1.5,
        maxBackoffMs: 30000,
      });
    }

    expect(backoff).toBeLessThanOrEqual(30000);
  });
});
