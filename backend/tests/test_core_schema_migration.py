from __future__ import annotations

from pathlib import Path


MIGRATION_PATH = Path("deploy/migrations/20260307_add_ml_trading_core_tables.sql")


def _migration_sql() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_core_schema_migration_creates_required_tables() -> None:
    sql = _migration_sql()

    for table_name in (
        "models",
        "features",
        "drift_reports",
        "patterns",
        "regime_history",
        "execution_analysis",
        "alternative_data",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table_name}" in sql


def test_core_schema_migration_includes_foreign_keys() -> None:
    sql = _migration_sql()

    assert "model_id BIGINT NOT NULL REFERENCES models(id) ON DELETE CASCADE" in sql
    assert "source_model_id BIGINT REFERENCES models(id) ON DELETE SET NULL" in sql


def test_core_schema_migration_includes_indexes() -> None:
    sql = _migration_sql()

    for index_name in (
        "idx_models_status",
        "idx_features_name_version",
        "idx_drift_reports_model_time",
        "idx_patterns_symbol_type",
        "idx_regime_history_symbol_detected",
        "idx_execution_analysis_symbol_time",
        "idx_alternative_data_symbol_time",
    ):
        assert f"CREATE INDEX IF NOT EXISTS {index_name}" in sql


def test_core_schema_migration_includes_constraints() -> None:
    sql = _migration_sql()

    assert "CONSTRAINT chk_patterns_confidence_range CHECK (confidence >= 0.0 AND confidence <= 1.0)" in sql
    assert "CONSTRAINT chk_regime_confidence_range CHECK (confidence >= 0.0 AND confidence <= 1.0)" in sql
    assert "CONSTRAINT chk_alternative_data_quality_score CHECK (quality_score >= 0.0 AND quality_score <= 1.0)" in sql
    assert "CONSTRAINT uq_execution_analysis_order UNIQUE (exchange, order_id)" in sql
