export interface CryptoAsset {
  symbol: string;
  name: string;
  price: number;
  change24h: number;
  volume: string;
  marketCap: string;
  sparkline: number[];
  signal: 'long' | 'short' | 'neutral';
  confidence: number;
}

export const cryptoAssets: CryptoAsset[] = [
  { symbol: 'BTC', name: 'Bitcoin', price: 104283.42, change24h: 2.34, volume: '38.2B', marketCap: '2.04T', sparkline: [30, 35, 28, 40, 45, 42, 50, 55, 48, 60, 58, 65, 62, 68, 70], signal: 'long', confidence: 87 },
  { symbol: 'ETH', name: 'Ethereum', price: 3847.18, change24h: -1.12, volume: '18.7B', marketCap: '462B', sparkline: [60, 55, 50, 52, 48, 45, 42, 40, 38, 35, 37, 33, 30, 32, 28], signal: 'short', confidence: 72 },
  { symbol: 'SOL', name: 'Solana', price: 178.94, change24h: 5.67, volume: '4.2B', marketCap: '78.3B', sparkline: [20, 25, 30, 28, 35, 40, 38, 45, 50, 55, 52, 60, 58, 65, 70], signal: 'long', confidence: 91 },
  { symbol: 'BNB', name: 'BNB', price: 712.33, change24h: 0.89, volume: '2.1B', marketCap: '104B', sparkline: [40, 42, 45, 43, 47, 50, 48, 52, 50, 55, 53, 56, 54, 58, 57], signal: 'neutral', confidence: 54 },
  { symbol: 'XRP', name: 'Ripple', price: 2.47, change24h: -3.21, volume: '3.8B', marketCap: '134B', sparkline: [65, 60, 55, 58, 50, 48, 45, 42, 40, 38, 35, 32, 30, 28, 25], signal: 'short', confidence: 79 },
  { symbol: 'ADA', name: 'Cardano', price: 0.812, change24h: 1.45, volume: '890M', marketCap: '28.4B', sparkline: [35, 38, 40, 42, 45, 43, 48, 50, 47, 52, 55, 53, 58, 56, 60], signal: 'long', confidence: 65 },
  { symbol: 'AVAX', name: 'Avalanche', price: 42.18, change24h: 4.23, volume: '1.2B', marketCap: '15.8B', sparkline: [25, 30, 28, 35, 40, 38, 42, 48, 45, 50, 55, 52, 58, 62, 65], signal: 'long', confidence: 83 },
  { symbol: 'DOT', name: 'Polkadot', price: 8.94, change24h: -0.45, volume: '520M', marketCap: '12.1B', sparkline: [50, 48, 45, 47, 43, 40, 42, 38, 40, 37, 35, 38, 36, 34, 35], signal: 'neutral', confidence: 48 },
  { symbol: 'LINK', name: 'Chainlink', price: 18.72, change24h: 3.11, volume: '780M', marketCap: '11.2B', sparkline: [30, 32, 35, 38, 40, 42, 45, 48, 46, 50, 53, 55, 58, 60, 62], signal: 'long', confidence: 76 },
  { symbol: 'DOGE', name: 'Dogecoin', price: 0.184, change24h: -2.88, volume: '1.8B', marketCap: '26.5B', sparkline: [55, 50, 48, 45, 42, 40, 38, 35, 33, 30, 28, 25, 27, 24, 22], signal: 'short', confidence: 68 },
];

export interface Trade {
  id: string;
  pair: string;
  side: 'buy' | 'sell';
  price: number;
  amount: number;
  total: number;
  time: string;
  status: 'filled' | 'pending' | 'cancelled';
  pnl?: number;
}

const baseNow = Date.now();
const hhmmssAgo = (minutesAgo: number): string => new Date(baseNow - minutesAgo * 60 * 1000).toISOString().slice(11, 19);

export const recentTrades: Trade[] = [
  { id: 'T-001', pair: 'BTC/USDT', side: 'buy', price: 103842.50, amount: 0.05, total: 5192.13, time: hhmmssAgo(1), status: 'filled', pnl: 224.50 },
  { id: 'T-002', pair: 'ETH/USDT', side: 'sell', price: 3891.20, amount: 2.0, total: 7782.40, time: hhmmssAgo(5), status: 'filled', pnl: -89.30 },
  { id: 'T-003', pair: 'SOL/USDT', side: 'buy', price: 172.45, amount: 25.0, total: 4311.25, time: hhmmssAgo(18), status: 'filled', pnl: 162.25 },
  { id: 'T-004', pair: 'BNB/USDT', side: 'buy', price: 708.90, amount: 1.5, total: 1063.35, time: hhmmssAgo(34), status: 'pending' },
  { id: 'T-005', pair: 'XRP/USDT', side: 'sell', price: 2.52, amount: 1000, total: 2520.00, time: hhmmssAgo(51), status: 'filled', pnl: -45.80 },
  { id: 'T-006', pair: 'AVAX/USDT', side: 'buy', price: 40.12, amount: 15, total: 601.80, time: hhmmssAgo(72), status: 'filled', pnl: 30.90 },
  { id: 'T-007', pair: 'ADA/USDT', side: 'sell', price: 0.798, amount: 5000, total: 3990.00, time: hhmmssAgo(96), status: 'cancelled' },
  { id: 'T-008', pair: 'LINK/USDT', side: 'buy', price: 17.85, amount: 50, total: 892.50, time: hhmmssAgo(121), status: 'filled', pnl: 43.50 },
];

export interface BacktestResult {
  id: string;
  strategy: string;
  pair: string;
  period: string;
  trades: number;
  winRate: number;
  totalReturn: number;
  sharpe: number;
  maxDrawdown: number;
  status: 'completed' | 'running' | 'queued';
  duration: string;
}

export const backtestResults: BacktestResult[] = [
  { id: 'BT-001', strategy: 'LSTM Momentum', pair: 'BTC/USDT', period: '2024-01 -> 2024-06', trades: 342, winRate: 67.8, totalReturn: 34.2, sharpe: 2.14, maxDrawdown: -8.3, status: 'completed', duration: '2m 14s' },
  { id: 'BT-002', strategy: 'Mean Reversion', pair: 'ETH/USDT', period: '2024-01 -> 2024-06', trades: 518, winRate: 54.2, totalReturn: 12.8, sharpe: 1.42, maxDrawdown: -15.1, status: 'completed', duration: '3m 08s' },
  { id: 'BT-003', strategy: 'Transformer Ensemble', pair: 'SOL/USDT', period: '2024-03 -> 2024-06', trades: 189, winRate: 72.5, totalReturn: 48.7, sharpe: 2.89, maxDrawdown: -6.2, status: 'completed', duration: '5m 42s' },
  { id: 'BT-004', strategy: 'RSI + MACD Cross', pair: 'BTC/USDT', period: '2023-06 -> 2024-06', trades: 876, winRate: 51.3, totalReturn: 8.4, sharpe: 0.92, maxDrawdown: -22.7, status: 'completed', duration: '1m 33s' },
  { id: 'BT-005', strategy: 'GAN Predictor v3', pair: 'AVAX/USDT', period: '2024-01 -> 2024-06', trades: 256, winRate: 63.1, totalReturn: 28.9, sharpe: 1.98, maxDrawdown: -11.4, status: 'running', duration: '--' },
  { id: 'BT-006', strategy: 'Multi-horizon MLP', pair: 'BNB/USDT', period: '2024-04 -> 2024-06', trades: 0, winRate: 0, totalReturn: 0, sharpe: 0, maxDrawdown: 0, status: 'queued', duration: '--' },
];

export interface Model {
  id: string;
  name: string;
  type: string;
  accuracy: number;
  horizon: string;
  lastTrained: string;
  status: 'active' | 'training' | 'inactive';
  params: string;
  dataset: string;
}

export const models: Model[] = [
  { id: 'M-001', name: 'BTC Price Predictor', type: 'LSTM', accuracy: 78.4, horizon: '1h', lastTrained: '2h ago', status: 'active', params: '2.4M', dataset: 'btc_1m_2y' },
  { id: 'M-002', name: 'ETH Volatility Model', type: 'Transformer', accuracy: 82.1, horizon: '4h', lastTrained: '6h ago', status: 'active', params: '8.7M', dataset: 'eth_1m_3y' },
  { id: 'M-003', name: 'SOL Momentum Net', type: 'CNN-LSTM', accuracy: 85.3, horizon: '15m', lastTrained: '45m ago', status: 'active', params: '1.2M', dataset: 'sol_1m_1y' },
  { id: 'M-004', name: 'Multi-Asset Ensemble', type: 'Ensemble', accuracy: 74.8, horizon: '1d', lastTrained: '1d ago', status: 'training', params: '15.2M', dataset: 'multi_1h_2y' },
  { id: 'M-005', name: 'Sentiment Analyzer', type: 'BERT-ft', accuracy: 71.2, horizon: '6h', lastTrained: '3d ago', status: 'inactive', params: '110M', dataset: 'social_feeds' },
  { id: 'M-006', name: 'Order Flow Predictor', type: 'GRU', accuracy: 69.5, horizon: '5m', lastTrained: '12h ago', status: 'active', params: '890K', dataset: 'orderbook_1m' },
];

export const portfolioData = {
  totalValue: 127843.52,
  totalPnl: 12843.52,
  totalPnlPercent: 11.17,
  dayPnl: 1247.83,
  dayPnlPercent: 0.98,
  positions: [
    { symbol: 'BTC', amount: 0.85, value: 88640.91, allocation: 69.3, pnl: 8420.12, pnlPercent: 10.5 },
    { symbol: 'ETH', amount: 5.2, value: 20005.34, allocation: 15.6, pnl: 1230.45, pnlPercent: 6.5 },
    { symbol: 'SOL', amount: 45, value: 8052.30, allocation: 6.3, pnl: 2105.80, pnlPercent: 35.4 },
    { symbol: 'AVAX', amount: 80, value: 3374.40, allocation: 2.6, pnl: 412.30, pnlPercent: 13.9 },
    { symbol: 'LINK', amount: 120, value: 2246.40, allocation: 1.8, pnl: -124.50, pnlPercent: -5.3 },
    { symbol: 'USDT', amount: 5524.17, value: 5524.17, allocation: 4.3, pnl: 0, pnlPercent: 0 },
  ],
};

export const equityCurve = [
  100000, 101200, 99800, 102400, 104100, 103200, 105800, 107400, 106100, 109200,
  111800, 110500, 113200, 115400, 114100, 117800, 119200, 118400, 120100, 122800,
  121500, 124200, 125800, 124600, 127843,
];

export const logEntries = [
  { time: hhmmssAgo(1), level: 'info' as const, msg: 'Order filled: BUY 0.05 BTC @ $103,842.50' },
  { time: hhmmssAgo(1), level: 'info' as const, msg: 'Signal generated: BTC LONG (conf: 87%)' },
  { time: hhmmssAgo(5), level: 'warn' as const, msg: 'Order filled: SELL 2.0 ETH @ $3,891.20' },
  { time: hhmmssAgo(8), level: 'info' as const, msg: 'Model M-003 prediction updated: SOL UP $182.40 (15m)' },
  { time: hhmmssAgo(13), level: 'info' as const, msg: 'Backtest BT-005 progress: 68% complete' },
  { time: hhmmssAgo(18), level: 'info' as const, msg: 'Order filled: BUY 25.0 SOL @ $172.45' },
  { time: hhmmssAgo(23), level: 'error' as const, msg: 'WebSocket reconnection attempt #2 resolved' },
  { time: hhmmssAgo(28), level: 'info' as const, msg: 'Daily risk check passed - exposure within limits' },
];

export function formatNumber(n: number, decimals = 2): string {
  return n.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

export function formatCurrency(n: number, decimals = 2): string {
  return '$' + formatNumber(n, decimals);
}
