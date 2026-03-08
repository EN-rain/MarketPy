# 🤖 Autonomous AI Trading Guide

## Where to Check Autonomous Trading

### 1. **Frontend UI** (Recommended)

Navigate to: **http://localhost:3000/autonomous**

The autonomous trading page provides:
- ✅ Real-time status (Running/Stopped)
- ✅ Performance metrics (PnL, Win Rate, Sharpe Ratio)
- ✅ Live portfolio view with open positions
- ✅ Recent trade history
- ✅ Configuration controls
- ✅ Start/Stop buttons

**Steps:**
1. Start your servers: `cd frontend && npm run dev`
2. Open browser: http://localhost:3000
3. Click "Autonomous AI" in the sidebar (🤖 icon)
4. Configure settings and click "Start Autonomous Trading"
5. Monitor real-time performance

---

### 2. **API Endpoints**

#### Check Status
```bash
curl http://localhost:8000/api/autonomous/status
```

**Response:**
```json
{
  "is_running": true,
  "stats": {
    "total_pnl": 234.56,
    "total_pnl_pct": 2.35,
    "total_trades": 42,
    "win_rate": 58.5,
    "sharpe_ratio": 1.23,
    "max_drawdown": -3.2,
    "current_positions": 2,
    "runtime_hours": 12.5
  },
  "portfolio": {
    "cash": 9765.44,
    "total_equity": 10234.56,
    "positions": {...},
    "recent_trades": [...]
  }
}
```

#### Get Detailed Statistics
```bash
curl http://localhost:8000/api/autonomous/stats
```

#### Get Portfolio
```bash
curl http://localhost:8000/api/autonomous/portfolio
```

---

### 3. **Python API**

```python
from backend.app.autonomous import AutonomousTrader, AutonomousConfig

# Create trader
config = AutonomousConfig(
    initial_cash=10000.0,
    markets=["BTCUSDT", "ETHUSDT"],
    edge_buffer=0.001,
    kelly_fraction=0.25,
)

trader = AutonomousTrader(config)

# Start trading
await trader.start()

# Check status
print(f"Running: {trader.is_running}")

# Get statistics
stats = trader.get_stats()
print(f"Total PnL: ${stats['total_pnl']:.2f}")
print(f"Win Rate: {stats['win_rate']:.1f}%")
print(f"Total Trades: {stats['total_trades']}")

# Get portfolio
portfolio = trader.get_portfolio()
print(f"Cash: ${portfolio['cash']:.2f}")
print(f"Positions: {len(portfolio['positions'])}")

# Stop trading
await trader.stop()
```

---

### 4. **Backend Logs**

Check the backend console for real-time logs:

```
🤖 Autonomous trading started
📊 Performance Update: PnL: $234.56 (2.35%), Trades: 42, Win Rate: 58.5%
Paper trade: BUY 0.1 BTCUSDT @ 45000.0000
Paper trade: SELL 0.1 ETHUSDT @ 2500.0000
Reloading ML model...
🛑 Autonomous trading stopped. Total PnL: $234.56 (2.35%)
```

---

## Quick Start

### Option 1: Via Frontend (Easiest)

1. **Start servers:**
   ```bash
   cd frontend
   npm run dev
   ```

2. **Open browser:**
   - Go to: http://localhost:3000/autonomous

3. **Configure and start:**
   - Set initial cash, markets, and risk limits
   - Click "🚀 Start Autonomous Trading"

4. **Monitor:**
   - Watch real-time PnL updates
   - View open positions
   - See recent trades

5. **Stop:**
   - Click "Stop Trading" button

---

### Option 2: Via API

1. **Start servers:**
   ```bash
   # Terminal 1: Backend
   python start_backend.py
   
   # Terminal 2: Frontend (optional)
   cd frontend && npm run dev
   ```

2. **Start autonomous trading:**
   ```bash
   curl -X POST http://localhost:8000/api/autonomous/start \
     -H "Content-Type: application/json" \
     -d '{
       "initial_cash": 10000,
       "markets": ["BTCUSDT", "ETHUSDT"],
       "edge_buffer": 0.001,
       "kelly_fraction": 0.25,
       "max_daily_loss": 500
     }'
   ```

3. **Monitor status:**
   ```bash
   # Check every few seconds
   watch -n 2 'curl -s http://localhost:8000/api/autonomous/stats | jq'
   ```

4. **Stop trading:**
   ```bash
   curl -X POST http://localhost:8000/api/autonomous/stop
   ```

---

## What You'll See

### Performance Metrics
- **Total PnL** - Profit/Loss in dollars and percentage
- **Total Equity** - Current portfolio value
- **Win Rate** - Percentage of profitable trades
- **Sharpe Ratio** - Risk-adjusted return
- **Max Drawdown** - Largest peak-to-trough decline
- **Runtime** - Hours since trading started

### Portfolio View
- **Cash** - Available cash balance
- **Positions** - Open positions with unrealized PnL
- **Recent Trades** - Last 10 trades with details

### Real-time Updates
- Updates every 2 seconds
- Live position tracking
- Instant trade notifications
- Risk alert monitoring

---

## Configuration Options

| Parameter | Description | Default | Range |
|-----------|-------------|---------|-------|
| `initial_cash` | Starting capital | $10,000 | > 0 |
| `markets` | Markets to trade | ["BTCUSDT", "ETHUSDT", "SOLUSDT"] | Any valid symbols |
| `edge_buffer` | Minimum edge required | 0.001 (0.1%) | 0 - 0.1 |
| `kelly_fraction` | Kelly sizing fraction | 0.25 | 0 - 1.0 |
| `order_size` | Order size fraction | 0.1 (10%) | 0 - 1.0 |
| `max_position_per_market` | Max position per market | $5,000 | > 0 |
| `max_total_exposure` | Max total exposure | $8,000 | > 0 |
| `max_daily_loss` | Max daily loss | $500 | > 0 |

---

## Safety Features

### Automatic Risk Controls
- ✅ Position size limits per market
- ✅ Total exposure limits
- ✅ Daily loss limits (auto-stops trading)
- ✅ Minimum edge requirements
- ✅ Kelly criterion position sizing
- ✅ Adaptive cooldown periods

### Monitoring & Alerts
- ✅ Real-time performance tracking
- ✅ Discord notifications (optional)
- ✅ Risk violation alerts
- ✅ Trade execution logs
- ✅ Model reload notifications

---

## Troubleshooting

### "Autonomous trading not running"
- Check if backend is running: `curl http://localhost:8000/health`
- Start trading via API or frontend
- Check backend logs for errors

### "No trades being executed"
- Verify markets have live data
- Check edge_buffer isn't too high
- Ensure ML model is loaded
- Review backend logs for signals

### "Trading stopped automatically"
- Check if daily loss limit was hit
- Review risk violation logs
- Check portfolio equity

### "Frontend not updating"
- Verify backend is running
- Check browser console for errors
- Refresh the page
- Check WebSocket connection

---

## Best Practices

1. **Start Small** - Begin with low initial_cash to test
2. **Monitor Closely** - Watch first few hours of trading
3. **Set Conservative Limits** - Use strict risk limits initially
4. **Review Performance** - Check stats regularly
5. **Adjust Parameters** - Fine-tune based on results
6. **Enable Notifications** - Set up Discord alerts
7. **Keep Models Updated** - Retrain models periodically

---

## Example Workflow

```bash
# 1. Start backend
python start_backend.py

# 2. Start autonomous trading (conservative settings)
curl -X POST http://localhost:8000/api/autonomous/start \
  -H "Content-Type: application/json" \
  -d '{
    "initial_cash": 5000,
    "markets": ["BTCUSDT"],
    "edge_buffer": 0.002,
    "kelly_fraction": 0.1,
    "max_daily_loss": 100
  }'

# 3. Monitor in real-time
watch -n 5 'curl -s http://localhost:8000/api/autonomous/stats | jq ".total_pnl, .win_rate, .total_trades"'

# 4. Check portfolio
curl http://localhost:8000/api/autonomous/portfolio | jq

# 5. Stop when satisfied
curl -X POST http://localhost:8000/api/autonomous/stop
```

---

## Support

- **Documentation:** [README.md](README.md)
- **API Reference:** http://localhost:8000/docs
- **Frontend:** http://localhost:3000/autonomous
- **Logs:** Check backend console output

---

**Happy Autonomous Trading! 🤖📈**
