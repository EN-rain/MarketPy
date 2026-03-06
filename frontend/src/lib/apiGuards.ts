export interface Trade {
  id: string;
  market_id: string;
  action: 'BUY' | 'SELL';
  price: number;
  timestamp: string;
  pnl?: number | null;
  size?: number;
}

export interface SystemStatus {
  mode: string;
  is_running: boolean;
  connected_markets: string[];
  connected_markets_count: number;
}

export interface DashboardPortfolio {
  cash: number;
  total_equity: number;
  positions: Record<string, unknown>;
  unrealized_pnl: number;
  realized_pnl: number;
  max_drawdown: number;
  win_rate: number;
  trade_count: number;
  initial_cash?: number;
}

export interface PaperStatus {
  is_running: boolean;
  mode: string;
  markets_count: number;
  signal_count: number;
  trade_count: number;
  total_equity: number;
  total_pnl: number;
  total_pnl_pct: number;
}

export interface PositionSnapshot {
  side?: string;
  size: number;
  avg_entry_price?: number;
  entry_price?: number;
  current_price: number;
  unrealized_pnl: number;
}

export interface PaperPortfolio {
  cash: number;
  total_equity: number;
  total_pnl: number;
  total_pnl_pct: number;
  unrealized_pnl: number;
  realized_pnl: number;
  max_drawdown: number;
  win_rate: number;
  positions_count: number;
  trades_count: number;
  positions: Record<string, PositionSnapshot>;
  trades: Trade[];
}

export interface MarketSummary {
  market_id: string;
  question: string;
}

export interface ModelsAnalyticsResponse {
  summary: {
    resolved_predictions: number;
    pending_predictions: number;
    directional_accuracy: number;
    mean_error_pct: number;
    adaptive_kelly_multiplier: number;
  };
  recent_predictions: Array<{
    market_id: string;
    horizon: string;
    signal_ts: string;
    resolved_ts: string;
    base_price: number;
    predicted_price: number;
    actual_price: number;
    abs_error: number;
    error_pct: number;
    correct_direction: boolean;
  }>;
  live_preview: Array<{
    market_id: string;
    horizon: string;
    signal_ts: string;
    due_ts: string;
    base_price: number;
    predicted_price: number;
    current_price: number;
    provisional_error: number;
    provisional_error_pct: number;
  }>;
  chart: Array<{
    t: string;
    predicted: number;
    actual: number;
    market_id: string;
    horizon: string;
  }>;
  filters: {
    market_id?: string;
    horizon?: string;
    limit: number;
  };
}

export interface DataHealthResponse {
  total_markets: number;
  active_markets: number;
  total_records: number;
  storage_size_gb: number;
  last_ingestion: string | null;
  data_quality_score: number;
  datasets: Array<{
    name: string;
    records: number;
    size_mb: number;
    last_update: string;
    status: 'healthy' | 'warning' | 'error';
  }>;
  ingestion_status: {
    ws_connected: boolean;
    rest_api_healthy: boolean;
    parquet_writer_healthy: boolean;
    duckdb_healthy: boolean;
  };
  recent_errors: Array<{
    timestamp: string;
    message: string;
    severity: 'info' | 'warning' | 'error';
  }>;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

function isString(value: unknown): value is string {
  return typeof value === 'string';
}

function isBoolean(value: unknown): value is boolean {
  return typeof value === 'boolean';
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every(isString);
}

export function isTrade(value: unknown): value is Trade {
  if (!isRecord(value)) {
    return false;
  }

  return (
    isString(value.id) &&
    isString(value.market_id) &&
    (value.action === 'BUY' || value.action === 'SELL') &&
    isNumber(value.price) &&
    isString(value.timestamp) &&
    (value.pnl === undefined || value.pnl === null || isNumber(value.pnl)) &&
    (value.size === undefined || isNumber(value.size))
  );
}

export function isTradeList(value: unknown): value is Trade[] {
  return Array.isArray(value) && value.every(isTrade);
}

export function isSystemStatus(value: unknown): value is SystemStatus {
  if (!isRecord(value)) {
    return false;
  }

  return (
    isString(value.mode) &&
    isBoolean(value.is_running) &&
    isStringArray(value.connected_markets) &&
    isNumber(value.connected_markets_count)
  );
}

export function isDashboardPortfolio(value: unknown): value is DashboardPortfolio {
  if (!isRecord(value) || !isRecord(value.positions)) {
    return false;
  }

  return (
    isNumber(value.cash) &&
    isNumber(value.total_equity) &&
    isNumber(value.unrealized_pnl) &&
    isNumber(value.realized_pnl) &&
    isNumber(value.max_drawdown) &&
    isNumber(value.win_rate) &&
    isNumber(value.trade_count)
  );
}

export function isPaperStatus(value: unknown): value is PaperStatus {
  if (!isRecord(value)) {
    return false;
  }

  return (
    isBoolean(value.is_running) &&
    isString(value.mode) &&
    isNumber(value.markets_count) &&
    isNumber(value.signal_count) &&
    isNumber(value.trade_count) &&
    isNumber(value.total_equity) &&
    isNumber(value.total_pnl) &&
    isNumber(value.total_pnl_pct)
  );
}

function isPositionSnapshot(value: unknown): value is PositionSnapshot {
  if (!isRecord(value)) {
    return false;
  }

  return (
    isNumber(value.size) &&
    isNumber(value.current_price) &&
    isNumber(value.unrealized_pnl) &&
    (value.side === undefined || isString(value.side)) &&
    (value.avg_entry_price === undefined || isNumber(value.avg_entry_price)) &&
    (value.entry_price === undefined || isNumber(value.entry_price))
  );
}

export function isPaperPortfolio(value: unknown): value is PaperPortfolio {
  if (!isRecord(value) || !isRecord(value.positions) || !Array.isArray(value.trades)) {
    return false;
  }

  return (
    isNumber(value.cash) &&
    isNumber(value.total_equity) &&
    isNumber(value.total_pnl) &&
    isNumber(value.total_pnl_pct) &&
    isNumber(value.unrealized_pnl) &&
    isNumber(value.realized_pnl) &&
    isNumber(value.max_drawdown) &&
    isNumber(value.win_rate) &&
    isNumber(value.positions_count) &&
    isNumber(value.trades_count) &&
    Object.values(value.positions).every(isPositionSnapshot) &&
    value.trades.every(isTrade)
  );
}

export function isMarketSummaryList(value: unknown): value is MarketSummary[] {
  return (
    Array.isArray(value) &&
    value.every(
      (item) => isRecord(item) && isString(item.market_id) && isString(item.question),
    )
  );
}

export function isModelsAnalyticsResponse(value: unknown): value is ModelsAnalyticsResponse {
  if (!isRecord(value) || !isRecord(value.summary) || !isRecord(value.filters)) {
    return false;
  }

  return (
    isNumber(value.summary.resolved_predictions) &&
    isNumber(value.summary.pending_predictions) &&
    isNumber(value.summary.directional_accuracy) &&
    isNumber(value.summary.mean_error_pct) &&
    isNumber(value.summary.adaptive_kelly_multiplier) &&
    Array.isArray(value.recent_predictions) &&
    Array.isArray(value.live_preview) &&
    Array.isArray(value.chart) &&
    isNumber(value.filters.limit)
  );
}

export function isDataHealthResponse(value: unknown): value is DataHealthResponse {
  if (!isRecord(value) || !isRecord(value.ingestion_status)) {
    return false;
  }

  return (
    isNumber(value.total_markets) &&
    isNumber(value.active_markets) &&
    isNumber(value.total_records) &&
    isNumber(value.storage_size_gb) &&
    (value.last_ingestion === null || isString(value.last_ingestion)) &&
    isNumber(value.data_quality_score) &&
    Array.isArray(value.datasets) &&
    value.datasets.every(
      (item) =>
        isRecord(item) &&
        isString(item.name) &&
        isNumber(item.records) &&
        isNumber(item.size_mb) &&
        isString(item.last_update) &&
        (item.status === 'healthy' || item.status === 'warning' || item.status === 'error'),
    ) &&
    isBoolean(value.ingestion_status.ws_connected) &&
    isBoolean(value.ingestion_status.rest_api_healthy) &&
    isBoolean(value.ingestion_status.parquet_writer_healthy) &&
    isBoolean(value.ingestion_status.duckdb_healthy) &&
    Array.isArray(value.recent_errors)
  );
}
