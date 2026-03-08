-- Phase 4 tables

CREATE TABLE IF NOT EXISTS model_versions (
    model_id TEXT NOT NULL,
    version TEXT NOT NULL,
    artifact_path TEXT NOT NULL,
    hyperparameters TEXT NOT NULL,
    training_data_ref TEXT NOT NULL,
    performance_metrics TEXT NOT NULL,
    status TEXT NOT NULL,
    PRIMARY KEY (model_id, version)
);

CREATE TABLE IF NOT EXISTS drift_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    accuracy_drift REAL NOT NULL,
    feature_drift REAL NOT NULL,
    prediction_drift REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS feature_importance_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id TEXT NOT NULL,
    version TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    method TEXT NOT NULL,
    feature_scores TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS arbitrage_opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    buy_exchange TEXT NOT NULL,
    sell_exchange TEXT NOT NULL,
    buy_price REAL NOT NULL,
    sell_price REAL NOT NULL,
    gross_profit_pct REAL NOT NULL,
    net_profit_pct REAL NOT NULL,
    detected_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS marketplace_strategies (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    author TEXT NOT NULL,
    description TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    methodology TEXT NOT NULL,
    total_return REAL NOT NULL,
    sharpe_ratio REAL NOT NULL,
    max_drawdown REAL NOT NULL,
    out_of_sample_period_days INTEGER NOT NULL
);
