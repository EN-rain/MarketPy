# OpenClaw Command Patterns

## Price and positions

- `Check BTC price`
- `What's ETH trading at?`
- `Show my positions`

## Order placement

- `Buy 0.1 BTC`
- `Sell 2 ETH`
- `Buy BTC if RSI < 30`

## Backtesting and strategy

- `Run backtest on momentum strategy with last 90 days`
- `Create a new mean reversion strategy`
- `Analyze my backtest results`

## Monitoring and analysis

- `Alert me if BTC crosses 45000`
- `Analyze BTC market structure`
- `List my active conditions`
- `Remove condition <condition-id>`

## Error recovery tips

- If parsing fails, include explicit `symbol`, `action`, and `quantity`.
- If risk violations occur, reduce order size or close positions.
- If API errors persist, verify `/health` and upstream MarketPy availability.
