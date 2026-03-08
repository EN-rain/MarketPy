"use client";

import { useEffect, useState } from "react";
import { useApi } from "@/hooks/useApi";

interface AutonomousStats {
  total_pnl: number;
  total_pnl_pct: number;
  total_trades: number;
  win_rate: number;
  sharpe_ratio: number;
  max_drawdown: number;
  total_equity: number;
  cash: number;
  current_positions: number;
  runtime_hours: number;
  is_running: boolean;
  markets_tracked: number;
}

interface Position {
  size: number;
  avg_price: number;
  current_price: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
}

interface Trade {
  market_id: string;
  action: string;
  size: number;
  price: number;
  pnl: number;
  timestamp: string;
  strategy: string;
}

interface Portfolio {
  cash: number;
  total_equity: number;
  positions_value: number;
  positions: Record<string, Position>;
  recent_trades: Trade[];
}

export default function AutonomousPage() {
  const { get, post } = useApi();
  const [isRunning, setIsRunning] = useState(false);
  const [stats, setStats] = useState<AutonomousStats | null>(null);
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Configuration state
  const [config, setConfig] = useState({
    initial_cash: 10000,
    markets: ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
    edge_buffer: 0.001,
    kelly_fraction: 0.25,
    order_size: 0.1,
    max_position_per_market: 5000,
    max_total_exposure: 8000,
    max_daily_loss: 500,
  });

  const fetchStatus = async () => {
    try {
      const response = await get("/autonomous/status");
      setIsRunning(response.is_running);
      if (response.is_running) {
        setStats(response.stats);
        setPortfolio(response.portfolio);
      }
    } catch (err) {
      console.error("Failed to fetch status:", err);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 2000); // Update every 2 seconds
    return () => clearInterval(interval);
  }, []);

  const handleStart = async () => {
    setLoading(true);
    setError(null);
    try {
      await post("/autonomous/start", config);
      await fetchStatus();
    } catch (err: any) {
      setError(err.message || "Failed to start autonomous trading");
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async () => {
    setLoading(true);
    setError(null);
    try {
      await post("/autonomous/stop", {});
      await fetchStatus();
    } catch (err: any) {
      setError(err.message || "Failed to stop autonomous trading");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">🤖 Autonomous AI Trading</h1>
          <p className="text-gray-400 mt-1">
            Fully automated trading with ML models
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div
            className={`px-4 py-2 rounded-lg font-semibold ${
              isRunning
                ? "bg-green-500/20 text-green-400"
                : "bg-gray-500/20 text-gray-400"
            }`}
          >
            {isRunning ? "● RUNNING" : "○ STOPPED"}
          </div>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/50 text-red-400 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      {/* Control Panel */}
      {!isRunning && (
        <div className="bg-gray-800/50 rounded-lg p-6 border border-gray-700">
          <h2 className="text-xl font-semibold mb-4">Configuration</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">
                Initial Cash ($)
              </label>
              <input
                type="number"
                value={config.initial_cash}
                onChange={(e) =>
                  setConfig({ ...config, initial_cash: Number(e.target.value) })
                }
                className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">
                Markets (comma-separated)
              </label>
              <input
                type="text"
                value={config.markets.join(", ")}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    markets: e.target.value.split(",").map((m) => m.trim()),
                  })
                }
                className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">
                Edge Buffer (%)
              </label>
              <input
                type="number"
                step="0.001"
                value={config.edge_buffer}
                onChange={(e) =>
                  setConfig({ ...config, edge_buffer: Number(e.target.value) })
                }
                className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">
                Kelly Fraction
              </label>
              <input
                type="number"
                step="0.05"
                value={config.kelly_fraction}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    kelly_fraction: Number(e.target.value),
                  })
                }
                className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">
                Max Daily Loss ($)
              </label>
              <input
                type="number"
                value={config.max_daily_loss}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    max_daily_loss: Number(e.target.value),
                  })
                }
                className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">
                Max Total Exposure ($)
              </label>
              <input
                type="number"
                value={config.max_total_exposure}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    max_total_exposure: Number(e.target.value),
                  })
                }
                className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2"
              />
            </div>
          </div>
          <button
            onClick={handleStart}
            disabled={loading}
            className="mt-6 w-full bg-green-600 hover:bg-green-700 disabled:bg-gray-600 text-white font-semibold py-3 rounded-lg transition-colors"
          >
            {loading ? "Starting..." : "🚀 Start Autonomous Trading"}
          </button>
        </div>
      )}

      {/* Statistics Dashboard */}
      {isRunning && stats && (
        <>
          {/* Performance Metrics */}
          <div className="grid grid-cols-4 gap-4">
            <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700">
              <div className="text-sm text-gray-400">Total PnL</div>
              <div
                className={`text-2xl font-bold mt-1 ${
                  stats.total_pnl >= 0 ? "text-green-400" : "text-red-400"
                }`}
              >
                ${stats.total_pnl.toFixed(2)}
              </div>
              <div className="text-xs text-gray-500 mt-1">
                {stats.total_pnl_pct.toFixed(2)}%
              </div>
            </div>

            <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700">
              <div className="text-sm text-gray-400">Total Equity</div>
              <div className="text-2xl font-bold mt-1">
                ${stats.total_equity.toFixed(2)}
              </div>
              <div className="text-xs text-gray-500 mt-1">
                Cash: ${stats.cash.toFixed(2)}
              </div>
            </div>

            <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700">
              <div className="text-sm text-gray-400">Win Rate</div>
              <div className="text-2xl font-bold mt-1">
                {stats.win_rate.toFixed(1)}%
              </div>
              <div className="text-xs text-gray-500 mt-1">
                {stats.total_trades} trades
              </div>
            </div>

            <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700">
              <div className="text-sm text-gray-400">Sharpe Ratio</div>
              <div className="text-2xl font-bold mt-1">
                {stats.sharpe_ratio.toFixed(2)}
              </div>
              <div className="text-xs text-gray-500 mt-1">
                Max DD: {stats.max_drawdown.toFixed(2)}%
              </div>
            </div>
          </div>

          {/* Runtime Info */}
          <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-gray-400">Runtime:</span>{" "}
                <span className="font-semibold">
                  {stats.runtime_hours.toFixed(1)} hours
                </span>
              </div>
              <div>
                <span className="text-gray-400">Markets:</span>{" "}
                <span className="font-semibold">{stats.markets_tracked}</span>
              </div>
              <div>
                <span className="text-gray-400">Positions:</span>{" "}
                <span className="font-semibold">{stats.current_positions}</span>
              </div>
              <button
                onClick={handleStop}
                disabled={loading}
                className="bg-red-600 hover:bg-red-700 disabled:bg-gray-600 text-white font-semibold px-6 py-2 rounded-lg transition-colors"
              >
                {loading ? "Stopping..." : "Stop Trading"}
              </button>
            </div>
          </div>

          {/* Positions */}
          {portfolio && Object.keys(portfolio.positions).length > 0 && (
            <div className="bg-gray-800/50 rounded-lg p-6 border border-gray-700">
              <h2 className="text-xl font-semibold mb-4">Open Positions</h2>
              <div className="space-y-3">
                {Object.entries(portfolio.positions).map(([market, pos]) => (
                  <div
                    key={market}
                    className="bg-gray-900/50 rounded-lg p-4 border border-gray-700"
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="font-semibold">{market}</div>
                        <div className="text-sm text-gray-400">
                          Size: {pos.size.toFixed(4)} @ $
                          {pos.avg_price.toFixed(2)}
                        </div>
                      </div>
                      <div className="text-right">
                        <div
                          className={`font-semibold ${
                            pos.unrealized_pnl >= 0
                              ? "text-green-400"
                              : "text-red-400"
                          }`}
                        >
                          ${pos.unrealized_pnl.toFixed(2)}
                        </div>
                        <div className="text-sm text-gray-400">
                          {pos.unrealized_pnl_pct.toFixed(2)}%
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Recent Trades */}
          {portfolio && portfolio.recent_trades.length > 0 && (
            <div className="bg-gray-800/50 rounded-lg p-6 border border-gray-700">
              <h2 className="text-xl font-semibold mb-4">Recent Trades</h2>
              <div className="space-y-2">
                {portfolio.recent_trades.map((trade, idx) => (
                  <div
                    key={idx}
                    className="bg-gray-900/50 rounded-lg p-3 border border-gray-700 flex items-center justify-between"
                  >
                    <div className="flex items-center gap-4">
                      <div
                        className={`px-3 py-1 rounded font-semibold text-sm ${
                          trade.action === "BUY"
                            ? "bg-green-500/20 text-green-400"
                            : "bg-red-500/20 text-red-400"
                        }`}
                      >
                        {trade.action}
                      </div>
                      <div>
                        <div className="font-semibold">{trade.market_id}</div>
                        <div className="text-sm text-gray-400">
                          {trade.size.toFixed(4)} @ ${trade.price.toFixed(2)}
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div
                        className={`font-semibold ${
                          trade.pnl >= 0 ? "text-green-400" : "text-red-400"
                        }`}
                      >
                        ${trade.pnl.toFixed(2)}
                      </div>
                      <div className="text-xs text-gray-500">
                        {new Date(trade.timestamp).toLocaleTimeString()}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* Instructions */}
      {!isRunning && (
        <div className="bg-blue-500/10 border border-blue-500/50 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-blue-400 mb-2">
            How Autonomous Trading Works
          </h3>
          <ul className="space-y-2 text-gray-300">
            <li>
              ✓ <strong>Continuous Monitoring:</strong> Watches live market
              data 24/7
            </li>
            <li>
              ✓ <strong>ML Predictions:</strong> Uses trained models to predict
              price movements
            </li>
            <li>
              ✓ <strong>Automated Execution:</strong> Executes trades when edge
              conditions are met
            </li>
            <li>
              ✓ <strong>Risk Management:</strong> Enforces position limits and
              stop-loss
            </li>
            <li>
              ✓ <strong>Performance Tracking:</strong> Monitors PnL and metrics
              in real-time
            </li>
          </ul>
        </div>
      )}
    </div>
  );
}
