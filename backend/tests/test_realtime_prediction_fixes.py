from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import time

import joblib
import pytest
from fastapi.testclient import TestClient

from backend.app.main import AppConfig, create_app
from backend.app.models.market import OrderBookSnapshot
from backend.app.models.signal import EdgeDecision, Horizon, Prediction, Signal
from backend.app.routers import backtest, paper_trading
from backend.ml.inference import Inferencer
from backend.ml.prediction_tracker import PredictionTracker, get_prediction_tracker
from backend.paper_trading.engine import PaperTradingEngine


class _FakeBinanceClient:
    def __init__(self) -> None:
        self.is_running = True
        self.markets = {}
        self.event_count = 0
        self.handlers = []

    def add_handler(self, handler) -> None:
        self.handlers.append(handler)

    def remove_handler(self, handler) -> None:
        if handler in self.handlers:
            self.handlers.remove(handler)

    async def start(self, symbols=None) -> None:
        self.is_running = True

    def stop(self) -> None:
        self.is_running = False


class _FakeEngine:
    def stop(self) -> None:
        return None


@pytest.fixture(autouse=True)
def reset_paper_engine_state():
    paper_trading.set_paper_engine(None)
    paper_trading.set_binance_handler(None)
    backtest._recent_backtests.clear()
    get_prediction_tracker().reset()
    yield
    paper_trading.set_paper_engine(None)
    paper_trading.set_binance_handler(None)
    backtest._recent_backtests.clear()
    get_prediction_tracker().reset()


def test_inferencer_fails_fast_when_model_dir_is_empty(tmp_path):
    with pytest.raises(FileNotFoundError, match="No trained model artifacts found"):
        Inferencer(model_dir=tmp_path)


def test_backend_startup_fails_fast_when_models_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.app.main.settings.model_dir", str(tmp_path / "empty_models"))
    app = create_app(AppConfig(enable_prediction_autostart=True))

    with pytest.raises(RuntimeError, match="No trained model artifacts found in models/ directory"):
        with TestClient(app):
            pass


def test_backend_startup_autostarts_prediction_service(monkeypatch):
    autostart_calls: list[list[str]] = []
    fake_client = _FakeBinanceClient()

    async def fake_start_binance_stream(manager):
        return fake_client, None

    async def fake_auto_start_prediction_service(app, market_ids: list[str]) -> None:
        autostart_calls.append(market_ids)
        app.state.paper_engine = _FakeEngine()
        app.state.app_state.is_running = True
        app.state.app_state.connected_markets = market_ids

    monkeypatch.setattr("backend.app.main.start_binance_stream", fake_start_binance_stream)
    monkeypatch.setattr("backend.app.main.validate_model_artifacts", lambda model_dir=None: [Path("models/model_1h.joblib")])
    monkeypatch.setattr("backend.app.main.auto_start_prediction_service", fake_auto_start_prediction_service)

    app = create_app(AppConfig(enable_prediction_autostart=True))

    with TestClient(app):
        deadline = time.time() + 2
        while time.time() < deadline and not autostart_calls:
            time.sleep(0.01)
        assert autostart_calls == [["BTCUSDT", "ETHUSDT", "SOLUSDT"]]
        assert app.state.app_state.is_running is True
        assert app.state.app_state.connected_markets == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        assert len(app.state.model_artifacts) == 1
        assert app.state.model_artifacts[0].endswith("models\\model_1h.joblib") or app.state.model_artifacts[0].endswith("models/model_1h.joblib")


def test_manual_paper_start_stop_still_works(monkeypatch):
    fake_client = _FakeBinanceClient()
    monkeypatch.setattr("backend.app.routers.paper_trading.get_binance_client", lambda request: fake_client)

    app = create_app(AppConfig(enable_binance_stream=False, enable_prediction_autostart=False))

    with TestClient(app) as client:
        start = client.post(
            "/api/paper/start",
            json={
                "market_ids": ["BTCUSDT", "ETHUSDT"],
                "strategy": "momentum",
                "initial_cash": 10000.0,
                "fill_model": "M2",
                "fee_rate": 0.02,
            },
        )
        assert start.status_code == 200
        assert start.json()["status"] == "started"

        status = client.get("/api/paper/status")
        assert status.status_code == 200
        assert status.json()["is_running"] is True
        assert status.json()["markets_count"] == 2

        stop = client.post("/api/paper/stop")
        assert stop.status_code == 200
        assert stop.json()["status"] == "stopped"


def test_trained_models_still_load_when_present(tmp_path):
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    artifact = {
        "models": {"xgb": _ConstantModel()},
        "weights": {"xgb": 1.0},
        "thresholds": {"buy_threshold": 0.0, "sell_threshold": 0.0},
    }
    joblib.dump(artifact, model_dir / "model_1h.joblib")

    inferencer = Inferencer(model_dir=model_dir)

    assert inferencer.available_horizons == ["model_1h"]


def test_inferencer_loads_5m_model_when_present(tmp_path):
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    artifact = {
        "models": {"xgb": _ConstantModel()},
        "weights": {"xgb": 1.0},
        "thresholds": {"buy_threshold": 0.0, "sell_threshold": 0.0},
    }
    joblib.dump(artifact, model_dir / "model_5m.joblib")

    inferencer = Inferencer(model_dir=model_dir)

    assert inferencer.available_horizons == ["model_5m", "model_1h", "model_6h", "model_1d"]
    thresholds = inferencer.get_threshold(Horizon.H1)
    assert "buy_threshold" in thresholds


def test_model_registry_derives_additional_models_from_5m_artifact(tmp_path, monkeypatch):
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    artifact = {
        "models": {"xgb": _ConstantModel()},
        "weights": {"xgb": 1.0},
        "thresholds": {"buy_threshold": 0.0, "sell_threshold": 0.0},
    }
    joblib.dump(artifact, model_dir / "model_5m.joblib")
    (model_dir / "model_5m_metrics.json").write_text(
        '{"accuracy": 0.812, "model_type": "xgb", "dataset": "btc_parquet", "params_count": 128}',
        encoding="utf-8",
    )
    monkeypatch.setattr("backend.app.routers.models_analytics.settings.model_dir", str(model_dir))

    app = create_app(AppConfig(enable_binance_stream=False, enable_prediction_autostart=False))

    with TestClient(app) as client:
        response = client.get("/api/models/registry")

    assert response.status_code == 200
    payload = response.json()
    ids = {item["id"] for item in payload["items"]}
    assert {"model_5m", "model_1h", "model_6h", "model_1d"}.issubset(ids)


def test_manual_paper_order_endpoint_executes_fill(monkeypatch):
    app = create_app(AppConfig(enable_binance_stream=False, enable_prediction_autostart=False))
    engine = PaperTradingEngine(initial_cash=10_000.0, fill_model="M2")
    engine.register_market("BTCUSDT", {"question": "BTC"})
    engine.markets["BTCUSDT"].orderbook = OrderBookSnapshot(
        token_id="BTCUSDT",
        timestamp=datetime.now(UTC),
        best_bid=100.0,
        best_ask=101.0,
        mid=100.5,
        spread=1.0,
    )
    engine.start()
    paper_trading.set_paper_engine(engine)

    with TestClient(app) as client:
        response = client.post(
            "/api/paper/order",
            json={
                "market_id": "BTCUSDT",
                "side": "buy",
                "size": 1.0,
                "order_type": "market",
                "limit_price": None,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "filled"
    assert payload["market_id"] == "BTCUSDT"
    assert payload["side"] == "BUY"
    assert payload["price"] == pytest.approx(101.0)


def test_manual_sell_order_reports_missing_position_reason():
    app = create_app(AppConfig(enable_binance_stream=False, enable_prediction_autostart=False))
    engine = PaperTradingEngine(initial_cash=10_000.0, fill_model="M2")
    engine.register_market("BTCUSDT", {"question": "BTC"})
    engine.markets["BTCUSDT"].orderbook = OrderBookSnapshot(
        token_id="BTCUSDT",
        timestamp=datetime.now(UTC),
        best_bid=100.0,
        best_ask=101.0,
        mid=100.5,
        spread=1.0,
    )
    engine.start()
    paper_trading.set_paper_engine(engine)

    with TestClient(app) as client:
      response = client.post(
          "/api/paper/order",
          json={
              "market_id": "BTCUSDT",
              "side": "sell",
              "size": 1.0,
              "order_type": "market",
              "limit_price": None,
          },
      )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "rejected"
    assert payload["reason"] == "Sell order rejected because there is no open paper position to close."


def test_manual_limit_order_reports_non_crossing_reason():
    app = create_app(AppConfig(enable_binance_stream=False, enable_prediction_autostart=False))
    engine = PaperTradingEngine(initial_cash=10_000.0, fill_model="M2")
    engine.register_market("BTCUSDT", {"question": "BTC"})
    engine.markets["BTCUSDT"].orderbook = OrderBookSnapshot(
        token_id="BTCUSDT",
        timestamp=datetime.now(UTC),
        best_bid=100.0,
        best_ask=101.0,
        mid=100.5,
        spread=1.0,
    )
    engine.start()
    paper_trading.set_paper_engine(engine)

    with TestClient(app) as client:
      response = client.post(
          "/api/paper/order",
          json={
              "market_id": "BTCUSDT",
              "side": "buy",
              "size": 1.0,
              "order_type": "limit",
              "limit_price": 99.0,
          },
      )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "rejected"
    assert payload["reason"] == "Limit order did not cross the current live bid/ask spread."


def test_backtest_recent_endpoint_returns_live_run(monkeypatch):
    class _FakeTrade:
        def __init__(self) -> None:
            self.timestamp = datetime.now(UTC)
            self.symbol = "BTCUSDT"
            self.side = "BUY"
            self.price = 101.0
            self.size = 1.0

    class _FakeInstantResult:
        total_return = 0.128
        trades = [_FakeTrade()]
        win_rate = 61.4
        max_drawdown = -7.2
        sharpe_ratio = 1.42
        equity_curve = [{"timestamp": datetime.now(UTC).isoformat(), "total_equity": 11280.0}]
        execution_ms = 840

    class _FakeInstantEngine:
        def __init__(self, data_dir=None) -> None:
            self.data_dir = data_dir

        def run_backtest(self, **kwargs):
            return _FakeInstantResult()

    monkeypatch.setattr("backend.app.routers.backtest.InstantBacktestEngine", _FakeInstantEngine)

    app = create_app(AppConfig(enable_binance_stream=False, enable_prediction_autostart=False))

    with TestClient(app) as client:
        response = client.post(
            "/api/backtest/run",
            json={
                "market_ids": ["BTCUSDT"],
                "strategy": "momentum",
                "start_date": "2024-01-01T00:00:00Z",
                "end_date": "2024-06-30T23:59:59Z",
            },
        )
        assert response.status_code == 200

        recent = client.get("/api/backtest/recent")

    assert recent.status_code == 200
    items = recent.json()["items"]
    assert len(items) == 1
    assert items[0]["strategy"] == "momentum"
    assert items[0]["pair"] == "BTCUSDT"
    assert items[0]["engine"] == "instant"
    assert items[0]["total_return"] == pytest.approx(12.8)


def test_model_registry_endpoint_lists_artifacts(tmp_path, monkeypatch):
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    artifact = {
        "models": {"xgb": _ConstantModel()},
        "weights": {"xgb": 1.0},
        "thresholds": {"buy_threshold": 0.0, "sell_threshold": 0.0},
    }
    joblib.dump(artifact, model_dir / "model_1h.joblib")
    (model_dir / "model_1h_metrics.json").write_text(
        '{"accuracy": 0.812, "model_type": "xgb", "dataset": "btc_parquet", "params_count": 128}',
        encoding="utf-8",
    )
    monkeypatch.setattr("backend.app.routers.models_analytics.settings.model_dir", str(model_dir))

    app = create_app(AppConfig(enable_binance_stream=False, enable_prediction_autostart=False))

    with TestClient(app) as client:
        response = client.get("/api/models/registry")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 1
    assert payload["items"][0]["id"] == "model_1h"
    assert payload["items"][0]["accuracy"] == pytest.approx(81.2)
    assert payload["items"][0]["dataset"] == "btc_parquet"


def test_prediction_tracker_persists_and_restores_history(tmp_path):
    storage_path = tmp_path / "prediction_tracking.json"
    tracker = PredictionTracker(storage_path=storage_path, snapshot_interval_seconds=0)
    signal = Signal(
        market_id="BTCUSDT",
        timestamp=datetime(2026, 3, 7, 8, 0, tzinfo=UTC),
        current_mid=100.0,
        current_bid=99.5,
        current_ask=100.5,
        predictions=[
            Prediction(horizon=Horizon.M5, predicted_return=0.01, predicted_price=101.0, confidence=0.8),
        ],
        edge=0.5,
        decision=EdgeDecision.BUY,
        strategy="ai",
        reason="test",
    )

    tracker.record_signal(signal)
    tracker.record_market_price("BTCUSDT", datetime(2026, 3, 7, 8, 5, tzinfo=UTC), 102.0)

    restarted = PredictionTracker(storage_path=storage_path, snapshot_interval_seconds=0)
    summary = restarted.get_summary()
    recent = restarted.get_recent(limit=5)

    assert summary["resolved_predictions"] == 1
    assert summary["by_horizon"]["5m"]["win_rate"] == pytest.approx(1.0)
    assert recent[0]["horizon"] == "5m"
    assert recent[0]["actual_price"] == pytest.approx(102.0)


class _ConstantModel:
    def predict(self, values):
        return [0.0]
