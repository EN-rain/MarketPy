# MarketPy

**AI-Powered Crypto Trading Simulator** with backtesting, paper trading, real-time monitoring, and ML research tools.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![Next.js 16](https://img.shields.io/badge/Next.js-16-black.svg)](https://nextjs.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🚀 Quick Start

### One Command to Rule Them All

```bash
cd frontend
npm run dev
```

This automatically:
- ✅ Starts the Python backend (FastAPI)
- ✅ Waits for backend health check
- ✅ Starts the Next.js frontend
- ✅ Opens http://localhost:3000

Both servers run together and stop with `Ctrl+C`.

**First time?** See [START_HERE.md](START_HERE.md) for detailed setup.

---

## 📋 Table of Contents

- [Features](#-features)
- [Architecture](#-architecture)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [API Documentation](#-api-documentation)
- [Data Pipeline](#-data-pipeline)
- [Trading Strategies](#-trading-strategies)
- [Machine Learning](#-machine-learning)
- [Deployment](#-deployment)
- [Development](#-development)
- [Documentation](#-documentation)

---

## ✨ Features

### 🎯 Core Capabilities

- **🤖 Autonomous AI Trading** - Fully automated trading with ML models (NEW!)
- **Backtesting Engine** - Vectorized simulation with realistic fill models and slippage
- **Paper Trading** - Live trading simulation with real market data
- **Real-time Monitoring** - WebSocket-based live updates and dashboards
- **ML Pipeline** - XGBoost/LightGBM/CatBoost models with drift detection
- **Multi-Exchange Support** - Binance, Coinbase, Kraken, Bybit, and more via CCXT
- **Risk Management** - VaR, drawdown limits, position sizing, correlation analysis
- **Pattern Detection** - Candlestick patterns, support/resistance, technical indicators
- **Regime Classification** - Market state detection for adaptive strategies
- **Feature Store** - Cached technical indicators and alternative data
- **Strategy Lab** - Visual strategy composer with drag-and-drop blocks

### 🔧 Advanced Features

- **Alternative Data Integration** - On-chain metrics, funding rates, liquidations, sentiment
- **Execution Quality Monitoring** - Slippage tracking, latency analysis, TCA
- **Model Governance** - Feature importance tracking, SHAP values, version control
- **Automated Alerts** - Discord notifications for trades, signals, and system events
- **Market Replay** - Historical data playback for strategy testing
- **Walk-Forward Analysis** - Out-of-sample validation with rolling windows
- **Stress Testing** - Portfolio resilience under extreme market conditions
- **Security** - JWT auth, API key management, rate limiting, HTTPS enforcement

---

## 🏗️ Architecture

```
MarketPy/
├── backend/                    # Python FastAPI backend
│   ├── app/                    # Application core
│   │   ├── main.py            # FastAPI app + WebSocket
│   │   ├── models/            # Pydantic domain models
│   │   ├── routers/           # REST API endpoints
│   │   ├── realtime/          # WebSocket infrastructure
│   │   ├── integrations/      # External API clients
│   │   ├── security/          # Auth, rate limiting
│   │   └── openclaw/          # AI agent system
│   ├── ingest/                # Market data ingestion
│   │   ├── exchanges/         # Exchange adapters (Binance, Coinbase, etc.)
│   │   ├── alternative_data/  # On-chain, sentiment, funding
│   │   └── websocket_manager.py
│   ├── dataset/               # Feature engineering
│   │   ├── builder.py         # Dataset construction
│   │   ├── features.py        # Feature computation
│   │   └── indicators.py      # Technical indicators
│   ├── sim/                   # Backtesting engine
│   │   ├── engine.py          # Event-driven simulator
│   │   ├── vectorized_engine.py
│   │   ├── fill_model.py      # Realistic order fills
│   │   └── fees.py            # Exchange fee models
│   ├── strategies/            # Trading strategies
│   │   ├── base.py            # Strategy interface
│   │   ├── ai_strategy.py     # ML-based strategy
│   │   ├── momentum.py        # Momentum strategies
│   │   └── mean_reversion.py  # Mean reversion
│   ├── ml/                    # Machine learning
│   │   ├── trainer.py         # Model training
│   │   ├── inference.py       # Prediction service
│   │   ├── drift_detection.py # Model monitoring
│   │   └── explainability.py  # SHAP values
│   ├── risk/                  # Risk management
│   │   ├── manager.py         # Risk engine
│   │   ├── portfolio_risk.py  # Portfolio metrics
│   │   └── circuit_breakers.py
│   ├── execution/             # Order execution
│   │   ├── order_manager.py   # Order lifecycle
│   │   ├── router.py          # Smart order routing
│   │   └── tca.py             # Transaction cost analysis
│   ├── monitoring/            # Observability
│   │   ├── metrics.py         # Prometheus metrics
│   │   ├── dashboard.py       # Monitoring dashboard
│   │   └── alerts.py          # Alert manager
│   ├── paper_trading/         # Paper trading
│   │   ├── engine.py          # Paper trading engine
│   │   └── live_feed.py       # Live market feed
│   ├── features/              # Feature store
│   │   ├── computer.py        # Feature computation
│   │   ├── cache.py           # Feature caching
│   │   └── definitions/       # Feature definitions
│   ├── patterns/              # Pattern detection
│   │   ├── detector.py        # Pattern scanner
│   │   ├── candlestick.py     # Candlestick patterns
│   │   └── technical.py       # Technical patterns
│   ├── regime/                # Regime classification
│   │   ├── classifier.py      # Market regime detector
│   │   └── predictor.py       # Regime prediction
│   ├── portfolio/             # Portfolio management
│   │   ├── optimizer.py       # Portfolio optimization
│   │   ├── rebalancer.py      # Rebalancing logic
│   │   └── attribution.py     # Performance attribution
│   └── tests/                 # Test suite (200+ tests)
│
├── frontend/                   # Next.js 16 frontend
│   ├── src/
│   │   ├── app/               # Next.js app router
│   │   │   ├── page.tsx       # Dashboard
│   │   │   ├── markets/       # Market overview
│   │   │   ├── backtests/     # Backtest results
│   │   │   ├── paper/         # Paper trading
│   │   │   ├── models/        # ML models
│   │   │   └── risk/          # Risk dashboard
│   │   ├── components/        # React components
│   │   │   ├── Sidebar.tsx    # Navigation
│   │   │   ├── ConnectionStatus.tsx
│   │   │   ├── StrategyLab/   # Visual strategy builder
│   │   │   ├── RiskCockpit/   # Risk visualizations
│   │   │   └── ModelGovernance/
│   │   ├── hooks/             # React hooks
│   │   │   ├── useApi.ts      # API client
│   │   │   └── useWebSocket.ts # WebSocket hook
│   │   └── terminal/          # Terminal-style UI
│   ├── scripts/
│   │   └── start-with-backend.js  # Auto-start script
│   └── package.json
│
├── config/                     # Configuration files
│   ├── dev.yaml               # Development config
│   ├── staging.yaml           # Staging config
│   ├── prod.yaml              # Production config
│   ├── exchanges.yaml         # Exchange settings
│   ├── realtime_updates.json  # WebSocket config
│   └── openclaw.json          # AI agent config
│
├── data/                       # Data storage
│   ├── parquet/               # Market data (Parquet)
│   ├── live/                  # Live data cache
│   ├── metrics.db             # Metrics database
│   └── prediction_logs.sqlite # ML predictions
│
├── models/                     # Trained ML models
│   ├── model_5m.joblib        # 5-minute model
│   └── model_5m_metrics.json  # Model metrics
│
├── docs/                       # Documentation
│   ├── api-documentation.md   # API reference
│   ├── architecture.md        # System architecture
│   ├── developer-guide.md     # Development guide
│   ├── operations-guide.md    # Operations manual
│   └── openclaw/              # AI agent docs
│
├── k8s/                        # Kubernetes manifests
│   ├── backend-deployment.yaml
│   ├── monitoring/            # Prometheus, Grafana
│   └── logging/               # ELK stack
│
├── deploy/                     # Deployment scripts
│   ├── docker-compose.staging.yml
│   ├── migrations/            # Database migrations
│   └── openclaw/              # AI agent deployment
│
├── scripts/                    # Utility scripts
│   ├── check_duplicate_dataclasses.py
│   ├── coverage_targets.py
│   └── smoke_staging.py
│
├── start_backend.py            # Backend startup script
├── pyproject.toml             # Python project config
├── requirements.txt           # Python dependencies
├── requirements-dev.txt       # Dev dependencies
├── Dockerfile                 # Backend container
├── Dockerfile.worker          # Worker container
└── package.json               # Root npm scripts
```

---

## 📦 Installation

### Prerequisites

- **Python 3.11+** - [Download](https://www.python.org/downloads/)
- **Node.js 18+** - [Download](https://nodejs.org/)
- **pip** - Python package manager
- **npm** - Node package manager

### Backend Setup

```bash
# Install Python dependencies
pip install -r requirements-dev.txt

# Verify installation
python -c "import fastapi; print('FastAPI installed')"
```

### Frontend Setup

```bash
# Install Node dependencies
cd frontend
npm install

# Verify installation
npm run build
```

### Environment Variables

Create `.env` file in project root:

```bash
# Backend
BACKEND_PORT=8000
MARKETPY_ENV=dev

# Security (optional)
SECURITY_ENABLE_AUTH=false
SECURITY_JWT_SECRET=your-secret-key

# Discord notifications (optional)
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# Exchange API keys (optional)
BINANCE_API_KEY=your-api-key
BINANCE_API_SECRET=your-api-secret
```

Frontend `.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## ⚙️ Configuration

MarketPy uses YAML configuration files in `config/`:

### Environment Selection

```bash
# Development (default)
MARKETPY_ENV=dev python start_backend.py

# Staging
MARKETPY_ENV=staging python start_backend.py

# Production
MARKETPY_ENV=prod python start_backend.py
```

### Configuration Files

- **`config/dev.yaml`** - Development settings
- **`config/staging.yaml`** - Staging environment
- **`config/prod.yaml`** - Production settings
- **`config/exchanges.yaml`** - Exchange configurations
- **`config/realtime_updates.json`** - WebSocket settings
- **`config/openclaw.json`** - AI agent configuration

### Override with Environment Variables

Any setting can be overridden:

```bash
BACKEND_PORT=9000 python start_backend.py
```

See [docs/configuration.md](docs/configuration.md) for details.

---

## 📡 API Documentation

### REST Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/status` | GET | System mode and connected markets |
| `/api/portfolio` | GET | Portfolio summary (cash, positions, PnL) |
| `/api/market/{id}` | GET | Market data (bid/ask/mid/candles) |
| `/api/markets` | GET | List all tracked markets |
| `/api/signals/{id}` | GET | AI predictions and trading signals |
| `/api/trades` | GET | Recent trade history |
| `/api/backtest/run` | POST | Execute backtest |
| `/api/backtest/capabilities` | GET | Available strategies and modes |
| `/api/paper-trading/risk-status` | GET | Risk limit status |
| `/api/autonomous/start` | POST | Start autonomous AI trading |
| `/api/autonomous/stop` | POST | Stop autonomous trading |
| `/api/autonomous/status` | GET | Autonomous trading status |
| `/api/autonomous/stats` | GET | Autonomous trading statistics |
| `/api/autonomous/portfolio` | GET | Autonomous trading portfolio |
| `/api/models/{id}/feature_importance` | GET | Model feature importance |
| `/api/health/summary` | GET | System health snapshot |
| `/api/data/health` | GET | Data quality metrics |

### WebSocket

**Endpoint:** `ws://localhost:8000/ws/live`

**Message Types:**

```json
// Subscribe to channels
{
  "type": "subscribe_channels",
  "channels": ["predictions", "risk", "execution", "alerts"]
}

// Subscribe to market
{
  "type": "subscribe_market",
  "market_id": "BTCUSDT"
}

// Ping/pong
{
  "type": "ping"
}
```

**Server Messages:**

- `market_update` - Real-time price updates
- `paper_signal` - Trading signals
- `paper_trade` - Trade executions
- `status_update` - System status
- `predictions_update` - ML predictions
- `risk_update` - Risk metrics
- `execution_update` - Execution quality
- `alerts_update` - Active alerts

See [docs/api-documentation.md](docs/api-documentation.md) for complete API reference.

---

## 🤖 Autonomous AI Trading

MarketPy includes a fully autonomous trading system that uses ML models to trade automatically without human intervention.

### How It Works

1. **Continuous Monitoring** - Watches live market data 24/7
2. **ML Predictions** - Uses trained models to predict price movements
3. **Signal Generation** - Generates BUY/SELL signals based on edge detection
4. **Automated Execution** - Executes trades automatically when conditions are met
5. **Risk Management** - Enforces position limits, exposure limits, and stop-loss
6. **Performance Tracking** - Monitors PnL, win rate, and other metrics in real-time

### Quick Start

```bash
# Start autonomous trading via API
curl -X POST http://localhost:8000/api/autonomous/start \
  -H "Content-Type: application/json" \
  -d '{
    "initial_cash": 10000,
    "markets": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
    "edge_buffer": 0.001,
    "kelly_fraction": 0.25,
    "max_daily_loss": 500
  }'

# Check status
curl http://localhost:8000/api/autonomous/status

# View statistics
curl http://localhost:8000/api/autonomous/stats

# Stop trading
curl -X POST http://localhost:8000/api/autonomous/stop
```

### Python API

```python
from backend.app.autonomous import AutonomousTrader, AutonomousConfig

# Configure autonomous trader
config = AutonomousConfig(
    initial_cash=10000.0,
    markets=["BTCUSDT", "ETHUSDT"],
    edge_buffer=0.001,  # 0.1% minimum edge
    kelly_fraction=0.25,  # Quarter Kelly sizing
    max_position_per_market=5000.0,
    max_total_exposure=8000.0,
    max_daily_loss=500.0,
)

# Create and start trader
trader = AutonomousTrader(config)
await trader.start()

# Monitor performance
stats = trader.get_stats()
print(f"Total PnL: ${stats['total_pnl']:.2f}")
print(f"Win Rate: {stats['win_rate']:.1f}%")
print(f"Total Trades: {stats['total_trades']}")

# Stop trading
await trader.stop()
```

### Configuration Options

| Parameter | Description | Default |
|-----------|-------------|---------|
| `initial_cash` | Starting capital | $10,000 |
| `markets` | Markets to trade | ["BTCUSDT", "ETHUSDT", "SOLUSDT"] |
| `edge_buffer` | Minimum edge required (%) | 0.001 (0.1%) |
| `kelly_fraction` | Kelly criterion fraction | 0.25 (quarter Kelly) |
| `order_size` | Order size as fraction of portfolio | 0.1 (10%) |
| `max_position_per_market` | Max position per market | $5,000 |
| `max_total_exposure` | Max total exposure | $8,000 |
| `max_daily_loss` | Max daily loss before stopping | $500 |
| `fill_model` | Fill model (M1/M2/M3) | M2 (realistic) |
| `fee_rate` | Trading fee rate | 0.0002 (0.02%) |

### Risk Management

The autonomous trader includes multiple safety mechanisms:

- **Position Limits** - Maximum position size per market
- **Exposure Limits** - Maximum total portfolio exposure
- **Daily Loss Limit** - Stops trading if daily loss exceeds threshold
- **Edge Requirements** - Only trades when predicted edge exceeds buffer
- **Kelly Sizing** - Position sizing based on Kelly criterion
- **Cooldown Periods** - Adaptive cooldowns based on market volatility

### Monitoring

Real-time statistics available via API:

```json
{
  "total_pnl": 234.56,
  "total_pnl_pct": 2.35,
  "total_trades": 42,
  "win_rate": 58.5,
  "sharpe_ratio": 1.23,
  "max_drawdown": -3.2,
  "current_positions": 2,
  "runtime_hours": 12.5,
  "is_running": true
}
```

### Discord Notifications

Enable Discord alerts for:
- Trading started/stopped
- Large trades executed
- Risk limit violations
- Performance milestones
- Daily PnL updates

Set `DISCORD_WEBHOOK_URL` in your `.env` file.

---

## 📊 Data Pipeline

### 1. Data Ingestion

```bash
# Record live market data
python -m backend.ingest.recorder --duration 3600

# Record from specific exchange
python -m backend.ingest.recorder --exchange binance --symbols BTCUSDT,ETHUSDT
```

### 2. Dataset Building

```bash
# Build training dataset
python -m backend.dataset.builder

# Custom timeframe
python -m backend.dataset.builder --timeframe 5m --lookback 30
```

### 3. Model Training

```bash
# Train ML model
python -m backend.ml.trainer --data-path data/parquet/market_id=BTCUSDT/bars.parquet

# With hyperparameter tuning
python -m backend.ml.trainer --optimize --trials 100
```

### 4. Backtesting

```bash
# Run backtest via API
curl -X POST http://localhost:8000/api/backtest/run \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": "ai_strategy",
    "market_ids": ["BTCUSDT"],
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "initial_cash": 10000
  }'
```

---

## 🎯 Trading Strategies

### Built-in Strategies

1. **AI Strategy** (`ai_strategy`) - ML-based predictions with Kelly sizing
2. **Momentum** (`momentum`) - Trend-following strategies
3. **Mean Reversion** (`mean_reversion`) - Range-bound strategies
4. **Pattern Strategy** (`pattern_strategy`) - Technical pattern recognition
5. **Regime Strategy** (`regime_strategy`) - Adaptive to market conditions

### Custom Strategy

```python
from backend.strategies.base import BaseStrategy

class MyStrategy(BaseStrategy):
    def generate_signals(self, market_data):
        # Your logic here
        return signals
    
    def calculate_position_size(self, signal, portfolio):
        # Position sizing logic
        return size
```

Register in `backend/strategies/__init__.py`.

---

## 🤖 Machine Learning

### Supported Models

- **XGBoost** - Gradient boosting (default)
- **LightGBM** - Fast gradient boosting
- **CatBoost** - Categorical feature support

### Features

- **Technical Indicators** - 50+ indicators (RSI, MACD, Bollinger Bands, etc.)
- **Price Features** - Returns, volatility, momentum
- **Volume Features** - Volume profile, VWAP, OBV
- **Microstructure** - Bid-ask spread, order flow
- **On-chain Metrics** - Network activity, whale movements
- **Alternative Data** - Sentiment, funding rates, liquidations

### Model Monitoring

- **Drift Detection** - Kolmogorov-Smirnov test
- **Feature Importance** - SHAP values
- **Performance Tracking** - Prediction accuracy over time
- **Auto-retraining** - Triggered on drift detection

---

## 🚀 Deployment

### Docker

```bash
# Build images
docker build -f Dockerfile -t marketpy/backend:latest .
docker build -f Dockerfile.worker -t marketpy/worker:latest .

# Run with docker-compose
docker-compose -f deploy/docker-compose.staging.yml up
```

### Kubernetes

```bash
# Deploy to cluster
kubectl apply -f k8s/

# Check status
kubectl get pods -n marketpy
```

### Production Checklist

- [ ] Set `MARKETPY_ENV=prod`
- [ ] Enable HTTPS (`SECURITY_REQUIRE_HTTPS=true`)
- [ ] Configure authentication (`SECURITY_ENABLE_AUTH=true`)
- [ ] Set up monitoring (Prometheus + Grafana)
- [ ] Configure logging (ELK stack)
- [ ] Set up backups for data/ and models/
- [ ] Configure Discord alerts
- [ ] Review security settings

See [docs/operations-guide.md](docs/operations-guide.md) for details.

---

## 🛠️ Development

### Run Tests

```bash
# Backend tests
pytest backend/tests -v

# With coverage
pytest backend/tests --cov=backend --cov-report=html

# Frontend tests
cd frontend
npm run test

# With coverage
npm run test:coverage
```

### Code Quality

```bash
# Linting
ruff check backend
cd frontend && npm run lint

# Type checking
mypy backend --ignore-missing-imports

# Format code
ruff format backend
cd frontend && npm run lint:fix
```

### Development Mode

```bash
# Backend with auto-reload
uvicorn backend.app.main:app --reload --port 8000

# Frontend with hot reload
cd frontend
npm run dev:frontend-only
```

---

## 📚 Documentation

- **[START_HERE.md](START_HERE.md)** - Quick start guide
- **[docs/api-documentation.md](docs/api-documentation.md)** - Complete API reference
- **[docs/architecture.md](docs/architecture.md)** - System architecture
- **[docs/developer-guide.md](docs/developer-guide.md)** - Development guide
- **[docs/operations-guide.md](docs/operations-guide.md)** - Operations manual
- **[docs/configuration.md](docs/configuration.md)** - Configuration guide
- **[docs/openclaw/](docs/openclaw/)** - AI agent documentation
- **[frontend/README.md](frontend/README.md)** - Frontend documentation

---

## 🔑 Key Concepts

### Fee Calculation

```
fee = price × size × fee_rate
```

### Target Variable

```
y_h(t) = log(mid(t+h) / mid(t))
```

### Edge Rule

Trade only if:
```
pred_price > ask × (1 + buffer)  # Buy
pred_price < bid × (1 - buffer)  # Sell
```

### Kelly Sizing

```
f* = edge / vol² × kelly_fraction
```

---

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

---

## 📄 License

MIT License - see LICENSE file for details.

---

## 🙏 Acknowledgments

- **FastAPI** - Modern Python web framework
- **Next.js** - React framework
- **CCXT** - Cryptocurrency exchange library
- **VectorBT** - Backtesting library
- **XGBoost** - Gradient boosting library

---

## 📞 Support

- **Issues:** [GitHub Issues](https://github.com/EN-rain/MarketPy/issues)
- **Documentation:** [docs/](docs/)
- **Discord:** (Coming soon)

---

**Happy Trading! 📈**
