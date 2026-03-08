'use client';

import { useApi } from '@/hooks/useApi';

export type MonitoringDashboardResponse = {
  system_health: {
    status: string;
    cpu_load_1m: number;
    memory_bytes: number;
    disk_used_bytes: number;
    api_latency_p95_ms: number;
    timestamp: string;
  };
  active_alerts: Array<{
    rule_id: string;
    severity: string;
    metric: string;
    observed: number;
    channel: string;
    timestamp: string;
  }>;
  dashboard_panels: {
    model_management: {
      versions: Array<{ id: string; status: string; accuracy: number }>;
      comparison: { best_model: string; delta_accuracy: number };
    };
    feature_store: {
      feature_count: number;
      drift_alerts: number;
      top_importance: Array<{ name: string; importance: number }>;
    };
    pattern_detection: {
      detected: Array<{ symbol: string; pattern: string; confidence: number; target: number }>;
    };
    risk_dashboard: {
      var: number;
      cvar: number;
      drawdown: number;
      leverage: number;
      active_risk_alerts: number;
    };
    execution_quality: {
      avg_slippage_bps: number;
      fill_rate: number;
      latency_p95_ms: number;
    };
    regime_classification: {
      current_regime: string;
      confidence: number;
      history: Array<{ regime: string; duration_hours: number }>;
    };
    multi_exchange: {
      exchanges: Array<{ name: string; status: string; price: number }>;
      arbitrage: Array<{ symbol: string; buy: string; sell: string; net_profit_pct: number }>;
    };
    explainability: {
      prediction: { symbol: string; value: number; lower: number; upper: number };
      top_shap: Array<{ feature: string; contribution: number }>;
    };
  };
};

export function useMonitoringDashboard() {
  return useApi<MonitoringDashboardResponse>('/monitoring/dashboard', { pollInterval: 4000 });
}
