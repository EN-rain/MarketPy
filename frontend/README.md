# MarketPy Frontend

Terminal-style UI for the MarketPy crypto trading simulator.

## Quick Start

```bash
npm run dev
```

This automatically starts both backend and frontend servers. Open `http://localhost:3000` in your browser.

## What You'll See

- **Portfolio Dashboard** - Real-time portfolio value, P&L, and positions
- **Equity Curve** - Visual representation of portfolio performance
- **Top Movers** - Markets with highest 24h price changes
- **AI Signals** - Live trading signals from ML models
- **Activity Log** - Real-time feed of trades and signals
- **Recent Trades** - Detailed trade history

## Features

### Real-Time Updates
- WebSocket connection for live market data
- Automatic reconnection on disconnect
- Fallback to polling when WebSocket unavailable

### Mock Mode
Toggle between live and mock data for testing:
- Look for the "Dev Mode" toggle in the UI
- Useful for frontend development without backend

### Responsive Design
- Terminal-inspired dark theme
- Optimized for desktop trading workflows
- Clean, minimal interface

## Tech Stack

- **Framework:** Next.js 16 with React 19
- **Language:** TypeScript 5
- **Styling:** Tailwind CSS 4
- **Charts:** Recharts
- **Icons:** Lucide React
- **Testing:** Vitest

## Available Scripts

- `npm run dev` - Start both backend and frontend (recommended)
- `npm run dev:frontend-only` - Start only frontend
- `npm run build` - Build for production
- `npm run start` - Run production build
- `npm run lint` - Check code quality
- `npm run test` - Run tests

## Configuration

Environment variables in `.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws/live
NEXT_PUBLIC_DEFAULT_MOCK_MODE=false
```

## Project Structure

```
frontend/
├── src/
│   ├── app/              # Next.js app router
│   ├── components/       # Reusable components
│   ├── hooks/            # Custom React hooks
│   ├── lib/              # Utilities and helpers
│   └── terminal/         # Terminal UI components
│       ├── components/   # UI primitives (Card, Badge, etc.)
│       ├── pages/        # Page components (Overview, etc.)
│       └── utils/        # Terminal-specific utilities
├── public/               # Static assets
└── scripts/              # Build and dev scripts
```

## Development

### Hot Reload
Both servers support hot reload:
- Backend: Auto-restarts on Python file changes
- Frontend: Auto-refreshes on TypeScript/React changes

### API Testing
Test backend endpoints directly:
```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/status
curl http://localhost:8000/api/markets
curl http://localhost:8000/api/paper/portfolio
```

### WebSocket Testing
Connect to WebSocket in browser console:
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/live');
ws.onmessage = (e) => console.log(JSON.parse(e.data));
```

## Troubleshooting

### Backend won't start
```bash
# Check Python version (3.11+ required)
python --version

# Install dependencies
pip install -r ../requirements-dev.txt

# Try starting backend manually
python ../start_backend.py
```

### Frontend won't start
```bash
# Install dependencies
npm install

# Clear Next.js cache
rm -rf .next

# Try again
npm run dev
```

### Port already in use
```bash
# Windows
netstat -ano | findstr :3000
taskkill /PID <PID> /F

# Linux/Mac
lsof -ti:3000 | xargs kill -9
```
