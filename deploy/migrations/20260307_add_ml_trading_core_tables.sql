-- Core schema for ML trading enhancements (PostgreSQL)

BEGIN;

CREATE TABLE IF NOT EXISTS models (
    id BIGSERIAL PRIMARY KEY,
    model_key TEXT NOT NULL UNIQUE,
    model_name TEXT NOT NULL,
    version TEXT NOT NULL,
    algorithm TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'registered',
    artifact_uri TEXT,
    checksum TEXT,
    hyperparameters JSONB NOT NULL DEFAULT '{}'::jsonb,
    feature_list JSONB NOT NULL DEFAULT '[]'::jsonb,
    performance_metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_models_status ON models (status);
CREATE INDEX IF NOT EXISTS idx_models_created_at ON models (created_at DESC);

CREATE TABLE IF NOT EXISTS features (
    id BIGSERIAL PRIMARY KEY,
    feature_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    definition JSONB NOT NULL DEFAULT '{}'::jsonb,
    dependencies JSONB NOT NULL DEFAULT '[]'::jsonb,
    data_sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    computation_logic TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_features_name_version ON features (name, version);

CREATE TABLE IF NOT EXISTS drift_reports (
    id BIGSERIAL PRIMARY KEY,
    model_id BIGINT NOT NULL REFERENCES models(id) ON DELETE CASCADE,
    report_time TIMESTAMPTZ NOT NULL,
    drift_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    baseline_window_start TIMESTAMPTZ,
    baseline_window_end TIMESTAMPTZ,
    comparison_window_start TIMESTAMPTZ,
    comparison_window_end TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_drift_reports_model_time ON drift_reports (model_id, report_time DESC);
CREATE INDEX IF NOT EXISTS idx_drift_reports_severity ON drift_reports (severity, report_time DESC);

CREATE TABLE IF NOT EXISTS patterns (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    pattern_type TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    formation_time TIMESTAMPTZ NOT NULL,
    completion_time TIMESTAMPTZ,
    key_price_levels JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_patterns_confidence_range CHECK (confidence >= 0.0 AND confidence <= 1.0)
);

CREATE INDEX IF NOT EXISTS idx_patterns_symbol_type ON patterns (symbol, pattern_type);
CREATE INDEX IF NOT EXISTS idx_patterns_completion_time ON patterns (completion_time DESC);

CREATE TABLE IF NOT EXISTS regime_history (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    regime TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL,
    features JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_model_id BIGINT REFERENCES models(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_regime_confidence_range CHECK (confidence >= 0.0 AND confidence <= 1.0)
);

CREATE INDEX IF NOT EXISTS idx_regime_history_symbol_detected ON regime_history (symbol, detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_regime_history_regime ON regime_history (regime, detected_at DESC);

CREATE TABLE IF NOT EXISTS execution_analysis (
    id BIGSERIAL PRIMARY KEY,
    exchange TEXT NOT NULL,
    symbol TEXT NOT NULL,
    order_id TEXT NOT NULL,
    side TEXT NOT NULL,
    predicted_price DOUBLE PRECISION,
    order_price DOUBLE PRECISION NOT NULL,
    fill_price DOUBLE PRECISION,
    slippage_bps DOUBLE PRECISION,
    fees DOUBLE PRECISION NOT NULL DEFAULT 0,
    market_regime TEXT,
    analysis_time TIMESTAMPTZ NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_execution_analysis_order UNIQUE (exchange, order_id)
);

CREATE INDEX IF NOT EXISTS idx_execution_analysis_symbol_time ON execution_analysis (symbol, analysis_time DESC);
CREATE INDEX IF NOT EXISTS idx_execution_analysis_exchange_time ON execution_analysis (exchange, analysis_time DESC);

CREATE TABLE IF NOT EXISTS alternative_data (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    source TEXT NOT NULL,
    data_type TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    value JSONB NOT NULL DEFAULT '{}'::jsonb,
    quality_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    is_stale BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_alternative_data_quality_score CHECK (quality_score >= 0.0 AND quality_score <= 1.0)
);

CREATE INDEX IF NOT EXISTS idx_alternative_data_symbol_time ON alternative_data (symbol, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_alternative_data_source_type ON alternative_data (source, data_type, observed_at DESC);

COMMIT;
