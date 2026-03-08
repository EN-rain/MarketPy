# 🤖 Where to Check Autonomous Trading

## Quick Answer

### 🌐 Frontend (Best Option)
**URL:** http://localhost:3000/autonomous

**Steps:**
1. Start: `cd frontend && npm run dev`
2. Open: http://localhost:3000
3. Click: "Autonomous AI" in sidebar (🤖 icon)

---

## All Options

### 1. 🖥️ Frontend Dashboard
- **URL:** http://localhost:3000/autonomous
- **Features:**
  - Real-time PnL updates
  - Live portfolio view
  - Recent trades
  - Start/Stop controls
  - Configuration panel
- **Updates:** Every 2 seconds

### 2. 🔌 API Endpoints

**Status:**
```bash
curl http://localhost:8000/api/autonomous/status
```

**Statistics:**
```bash
curl http://localhost:8000/api/autonomous/stats
```

**Portfolio:**
```bash
curl http://localhost:8000/api/autonomous/portfolio
```

### 3. 📊 API Documentation
- **URL:** http://localhost:8000/docs
- **Search for:** "Autonomous Trading" section
- **Interactive:** Try endpoints directly

### 4. 📝 Backend Logs
- Check terminal where backend is running
- Look for:
  - `🤖 Autonomous trading started`
  - `📊 Performance Update: ...`
  - `Paper trade: BUY/SELL ...`

---

## Quick Start

```bash
# 1. Start everything
cd frontend && npm run dev

# 2. Open browser
# http://localhost:3000/autonomous

# 3. Click "Start Autonomous Trading"

# 4. Watch it trade!
```

---

## What You'll See

### Performance Metrics
- Total PnL: $234.56 (2.35%)
- Win Rate: 58.5%
- Sharpe Ratio: 1.23
- Total Trades: 42

### Live Updates
- ✅ Real-time position tracking
- ✅ Trade notifications
- ✅ Risk alerts
- ✅ Performance charts

---

## Need Help?

See: [AUTONOMOUS_TRADING_GUIDE.md](AUTONOMOUS_TRADING_GUIDE.md)
