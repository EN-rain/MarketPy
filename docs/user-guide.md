# User Guide

## Getting Started

- Open the terminal dashboard frontend.
- Verify backend status on the Overview page.
- Connect live data and monitor websocket connectivity.

## Configure Strategies

- Backtests page:
  - select market(s), strategy, and execution mode.
  - run backtest and review PnL, drawdown, and trade list.
- Paper trading page:
  - start paper engine.
  - submit manual orders or run AI/preset strategies.

## Dashboard Interpretation

- Models: deployment status, comparison, and confidence.
- Feature Store: feature health and drift status.
- Risk Dashboard: VaR/CVaR, drawdown, and risk alerts.
- Execution Quality: slippage, fill rates, implementation shortfall.
- Monitoring: active alerts and system health.

## Risk Controls

- Position and exposure limits are enforced automatically.
- Drawdown limits can halt new entries.
- Circuit breakers stop trading during severe market stress.
- Security limits can block suspicious API activity.
