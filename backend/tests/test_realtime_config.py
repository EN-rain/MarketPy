"""Tests for realtime configuration models."""


from backend.app.models.realtime_config import (
    BackpressureConfig,
    BatcherConfig,
    MemoryConfig,
    PrioritizerConfig,
    RateLimiterConfig,
    RetentionPolicy,
    SystemConfig,
)


def test_prioritizer_config_defaults():
    """Test PrioritizerConfig has correct default values."""
    config = PrioritizerConfig()
    assert config.price_change_threshold == 0.02
    assert config.volume_spike_multiplier == 3.0
    assert config.critical_event_types == ["order_fill", "trade_execution"]


def test_batcher_config_defaults():
    """Test BatcherConfig has correct default values."""
    config = BatcherConfig()
    assert config.batch_window_ms == 100
    assert config.max_batch_size == 50
    assert config.enable_batching is True


def test_rate_limiter_config_defaults():
    """Test RateLimiterConfig has correct default values."""
    config = RateLimiterConfig()
    assert config.max_messages_per_second == 10
    assert config.burst_size == 20
    assert config.critical_bypass is True


def test_memory_config_defaults():
    """Test MemoryConfig has correct default values."""
    config = MemoryConfig()
    assert config.max_candles_per_market == 1000
    assert config.retention_seconds == 86400
    assert config.tier_policies == {}


def test_backpressure_config_defaults():
    """Test BackpressureConfig has correct default values."""
    config = BackpressureConfig()
    assert config.send_buffer_threshold == 65536
    assert config.slow_client_timeout == 30
    assert config.drop_non_critical_for_slow is True


def test_system_config_defaults():
    """Test SystemConfig has correct default values."""
    config = SystemConfig()

    # Batching
    assert config.batch_window_ms == 100
    assert config.max_batch_size == 50
    assert config.enable_batching is True

    # Rate Limiting
    assert config.max_messages_per_second == 10
    assert config.burst_size == 20
    assert config.critical_bypass is True

    # Prioritization
    assert config.price_change_threshold == 0.02
    assert config.volume_spike_multiplier == 3.0
    assert config.critical_event_types == ["order_fill"]

    # Memory Management
    assert config.max_candles_per_market == 1000
    assert config.retention_seconds == 86400

    # Backpressure
    assert config.send_buffer_threshold == 65536
    assert config.slow_client_timeout == 30
    assert config.drop_non_critical_for_slow is True

    # Concurrency
    assert config.worker_pool_size == 10
    assert config.max_concurrent_markets == 100

    # Signal Cooldown
    assert config.min_signal_cooldown_seconds == 1.0
    assert config.max_signal_cooldown_seconds == 30.0
    assert config.volatility_window_seconds == 300
    assert config.volatility_threshold_low == 0.005
    assert config.volatility_threshold_high == 0.03

    # Frontend Polling
    assert config.ws_connected_poll_interval_ms == 10000
    assert config.ws_disconnected_poll_interval_ms == 2000
    assert config.rest_backoff_multiplier == 1.5
    assert config.rest_max_backoff_ms == 30000


def test_system_config_component_sync():
    """Test SystemConfig syncs top-level fields to component configs."""
    config = SystemConfig(
        batch_window_ms=200,
        max_batch_size=100,
        max_messages_per_second=20,
        price_change_threshold=0.05,
    )

    # Verify component configs are synced
    assert config.batcher.batch_window_ms == 200
    assert config.batcher.max_batch_size == 100
    assert config.rate_limiter.max_messages_per_second == 20
    assert config.prioritizer.price_change_threshold == 0.05


def test_system_config_custom_values():
    """Test SystemConfig accepts custom values."""
    config = SystemConfig(
        batch_window_ms=50,
        max_batch_size=25,
        max_messages_per_second=5,
        burst_size=10,
        price_change_threshold=0.01,
        volume_spike_multiplier=2.0,
        max_candles_per_market=500,
        retention_seconds=43200,
        send_buffer_threshold=32768,
        slow_client_timeout=15,
        worker_pool_size=5,
        min_signal_cooldown_seconds=0.5,
        max_signal_cooldown_seconds=60.0,
    )

    assert config.batch_window_ms == 50
    assert config.max_batch_size == 25
    assert config.max_messages_per_second == 5
    assert config.burst_size == 10
    assert config.price_change_threshold == 0.01
    assert config.volume_spike_multiplier == 2.0
    assert config.max_candles_per_market == 500
    assert config.retention_seconds == 43200
    assert config.send_buffer_threshold == 32768
    assert config.slow_client_timeout == 15
    assert config.worker_pool_size == 5
    assert config.min_signal_cooldown_seconds == 0.5
    assert config.max_signal_cooldown_seconds == 60.0


def test_retention_policy():
    """Test RetentionPolicy dataclass."""
    policy = RetentionPolicy(max_candles=500, retention_seconds=3600)
    assert policy.max_candles == 500
    assert policy.retention_seconds == 3600


def test_memory_config_with_tier_policies():
    """Test MemoryConfig with tier-specific retention policies."""
    tier_policies = {
        "high_volume": RetentionPolicy(max_candles=2000, retention_seconds=172800),
        "low_volume": RetentionPolicy(max_candles=500, retention_seconds=43200),
    }
    config = MemoryConfig(tier_policies=tier_policies)

    assert len(config.tier_policies) == 2
    assert config.tier_policies["high_volume"].max_candles == 2000
    assert config.tier_policies["low_volume"].max_candles == 500
