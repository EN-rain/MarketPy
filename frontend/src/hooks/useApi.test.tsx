// @vitest-environment jsdom

import { act } from 'react';
import { useEffect } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { setMockMode } from '@/components/DevModeToggle';
import { isSystemStatus, SystemStatus } from '@/lib/apiGuards';
import { useApi } from './useApi';

type HookSnapshot = ReturnType<typeof useApi<SystemStatus>>;

function HookHarness({
  endpoint,
  onRender,
}: {
  endpoint: string;
  onRender: (snapshot: HookSnapshot) => void;
}) {
  const snapshot = useApi<SystemStatus>(endpoint, {
    validate: isSystemStatus,
  });

  useEffect(() => {
    onRender(snapshot);
  }, [onRender, snapshot]);

  return null;
}

describe('useApi', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    // React 19 expects the test runtime to opt into act-aware updates.
    globalThis.IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    vi.restoreAllMocks();
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
    setMockMode(true);
  });

  it('surfaces live network failures instead of silently falling back', async () => {
    setMockMode(false);
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));

    let snapshot: HookSnapshot | undefined;

    await act(async () => {
      root.render(<HookHarness endpoint="/status" onRender={(value) => { snapshot = value; }} />);
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(snapshot?.usingMockData).toBe(false);
    expect(snapshot?.data).toBeUndefined();
    expect(snapshot?.error?.kind).toBe('network');
  });

  it('uses demo payloads only when demo mode is explicitly enabled', async () => {
    setMockMode(true);
    vi.stubGlobal('fetch', vi.fn());

    let snapshot: HookSnapshot | undefined;

    await act(async () => {
      root.render(<HookHarness endpoint="/status" onRender={(value) => { snapshot = value; }} />);
      await Promise.resolve();
    });

    expect(snapshot?.usingMockData).toBe(true);
    expect(snapshot?.data?.mode).toBe('BACKTEST');
    expect(snapshot?.error).toBeNull();
  });
});
