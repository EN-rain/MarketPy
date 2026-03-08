# 🚀 MarketPy - Start Here

## Get Your UI Running in 10 Seconds

### Step 1: Open Terminal

Navigate to the frontend directory:
```bash
cd frontend
```

### Step 2: Run One Command

```bash
npm run dev
```

### Step 3: Wait for Magic ✨

You'll see:
```
🔧 MarketPy Full Stack Startup
================================

🚀 Starting backend server...
⏳ Waiting for backend...
✅ Backend is ready!

🎨 Starting frontend server...

================================
✨ Both servers are running!

   Backend:  http://localhost:8000
   Frontend: http://localhost:3000

Press Ctrl+C to stop both servers
```

### Step 4: Open Browser

Go to: **http://localhost:3000**

That's it! 🎉

---

## What Just Happened?

The `npm run dev` command:
1. ✅ Started your Python backend server
2. ✅ Waited for it to be healthy
3. ✅ Started your Next.js frontend
4. ✅ Connected them together

Both servers run in the same terminal and stop together when you press `Ctrl+C`.

---

## First Time Setup

If this is your first time, make sure you have:

### Python Dependencies
```bash
pip install -r requirements-dev.txt
```

### Node Dependencies
```bash
cd frontend
npm install
```

---

## What You'll See

Your browser will show:

📊 **Portfolio Dashboard**
- Real-time portfolio value and P&L
- Open positions with unrealized gains/losses
- Equity curve visualization

📈 **Market Data**
- Top moving crypto pairs
- Live price updates via WebSocket
- 24-hour price changes

🤖 **AI Signals**
- Live trading signals from ML models
- Confidence scores
- Buy/Sell recommendations

📝 **Activity Feed**
- Real-time trade notifications
- Signal updates
- System status messages

📋 **Trade History**
- Recent executed trades
- P&L per trade
- Detailed trade information

---

## Troubleshooting

### "Backend failed to start"

**Check Python:**
```bash
python --version
# Should be 3.11 or higher
```

**Install dependencies:**
```bash
pip install -r requirements-dev.txt
```

### "Port already in use"

**Kill the process:**
```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/Mac
lsof -ti:8000 | xargs kill -9
```

### "npm: command not found"

**Install Node.js:**
- Download from: https://nodejs.org/
- Version 18 or higher recommended

---

## Advanced Usage

### Run Servers Separately

**Backend only:**
```bash
python start_backend.py
```

**Frontend only:**
```bash
cd frontend
npm run dev:frontend-only
```

### Production Build

```bash
cd frontend
npm run build
npm run start
```

### Run Tests

```bash
# Backend tests
pytest backend/tests -v

# Frontend tests
cd frontend
npm run test
```

---

## Need Help?

- 📖 Frontend docs: `frontend/README.md`
- 📖 Main README: `README.md`

---

## Quick Commands Reference

| Command | Description |
|---------|-------------|
| `cd frontend && npm run dev` | Start everything |
| `python start_backend.py` | Backend only |
| `npm run dev:frontend-only` | Frontend only |
| `npm run build` | Production build |
| `npm run lint` | Check code quality |
| `npm test` | Run tests |

---

**Happy Trading! 📈**
