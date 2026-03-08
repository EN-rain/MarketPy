import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

function readSource(relativePath: string): string {
  return readFileSync(resolve(process.cwd(), relativePath), 'utf-8');
}

describe('terminal live data bindings', () => {
  it('Overview uses live API and websocket hooks instead of terminal mock data', () => {
    const source = readSource('src/terminal/pages/Overview.tsx');

    expect(source).toContain("useApi<MarketRecord[]>('/markets'");
    expect(source).toContain("useApi<PortfolioRecord>('/paper/portfolio'");
    expect(source).toContain("useApi<TradeRecord[]>('/trades'");
    expect(source).toContain('useWebSocket(');
    expect(source).not.toContain("../data/mock");
  });

  it('Markets uses live API and websocket hooks instead of terminal mock data', () => {
    const source = readSource('src/terminal/pages/Markets.tsx');

    expect(source).toContain("useApi<MarketResponse[]>('/markets'");
    expect(source).toContain('useWebSocket(');
    expect(source).not.toContain("../data/mock");
  });

  it('PaperTrading uses live API and websocket hooks instead of terminal mock data', () => {
    const source = readSource('src/terminal/pages/PaperTrading.tsx');

    expect(source).toContain("useApi<MarketDetail>('/market/BTCUSDT'");
    expect(source).toContain("useApi<PortfolioRecord>('/paper/portfolio'");
    expect(source).toContain("useApi<PaperStatus>('/paper/status'");
    expect(source).toContain("useApi<ApiTrade[]>('/trades'");
    expect(source).toContain('/paper/order');
    expect(source).toContain("postApi('/paper/start'");
    expect(source).toContain("postApi('/paper/stop'");
    expect(source).toContain("postApi('/paper/reset'");
    expect(source).toContain('useWebSocket(');
    expect(source).not.toContain("../data/mock");
  });

  it('Terminal shell header reads live market data instead of hardcoded BTC and ETH values', () => {
    const source = readSource('src/terminal/components/TerminalShell.tsx');

    expect(source).toContain("useApi<MarketSummary[]>('/markets'");
    expect(source).toContain('useWebSocket(');
    expect(source).not.toContain('$104,283');
    expect(source).not.toContain('$3,847');
  });

  it('Backtests uses live backend endpoints instead of terminal mock data', () => {
    const source = readSource('src/terminal/pages/Backtests.tsx');

    expect(source).toContain("useApi<RecentBacktestResponse>('/backtest/recent'");
    expect(source).toContain("useApi<BacktestCapabilities>('/backtest/capabilities'");
    expect(source).toContain("postApi<RunBacktestResponse>('/backtest/run'");
    expect(source).not.toContain("../data/mock");
  });

  it('Models uses live registry and analytics endpoints instead of terminal mock data', () => {
    const source = readSource('src/terminal/pages/Models.tsx');

    expect(source).toContain("useApi<ModelRegistryResponse>('/models/registry'");
    expect(source).toContain("useApi<ModelAnalyticsResponse>(`/models/analytics?horizon=${encodeURIComponent(normalizedHorizon)}&limit=120`");
    expect(source).not.toContain("../data/mock");
  });

  it('Database uses data health endpoint instead of static dataset arrays', () => {
    const source = readSource('src/terminal/pages/Database.tsx');

    expect(source).toContain("useApi<DataHealthResponse>('/data/health'");
    expect(source).not.toContain("const datasets: DatasetInfo[] = [");
  });
});
