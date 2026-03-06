"""Configuration models for enhanced realtime updates system."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PrioritizerConfig:
    """Configuration for UpdatePrioritizer component."""
    price_change_threshold: float = 0.02  # 2% price change triggers critical
    volume_spike_multiplier: float = 3.0  # 3x volume increase triggers critical
    critical_event_types: list[str] = field(default_factory=lambda: ["order_fill", "trade_execution"])


@dataclass
class BatcherConfig:
    """Configuration for MessageBatcher component."""
    batch_window_ms: int = 100  # Time window for batching in milliseconds
    max_batch_size: int = 50  # Maximum updates per batch before forced flush
    enable_batching: bool = True  # Global toggle for batching feature


@dataclass
class RateLimiterConfig:
    """Configuration for RateLimiter component."""
    max_messages_per_second: int = 10  # Maximum broadcast rate per client
    burst_size: int = 20  # Token bucket burst capacity
    critical_bypass: bool = True  # Whether critical messages bypass rate limits


@dataclass
class RetentionPolicy:
    """Retention policy for candle history."""
    max_candles: int
    retention_seconds: int


@dataclass
class MemoryConfig:
    """Configuration for MemoryManager component."""
    max_candles_per_market: int = 1000  # Maximum candle count per market
    retention_seconds: int = 86400  # Time-based retention (24 hours)
    tier_policies: dict[str, RetentionPolicy] = field(default_factory=dict)


@dataclass
class BackpressureConfig:
    """Configuration for BackpressureHandler component."""
    send_buffer_threshold: int = 65536  # Buffer size threshold for marking client as slow (bytes)
    slow_client_timeout: int = 30  # Duration before disconnecting slow client (seconds)
    drop_non_critical_for_slow: bool = True  # Whether to drop non-critical updates for slow clients


@dataclass
class SystemConfig:
    """Complete system configuration aggregating all component configs."""

    # Component configurations
    prioritizer: PrioritizerConfig = field(default_factory=PrioritizerConfig)
    batcher: BatcherConfig = field(default_factory=BatcherConfig)
    rate_limiter: RateLimiterConfig = field(default_factory=RateLimiterConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    backpressure: BackpressureConfig = field(default_factory=BackpressureConfig)

    # Batching (for backward compatibility and direct access)
    batch_window_ms: int = 100
    max_batch_size: int = 50
    enable_batching: bool = True

    # Rate Limiting
    max_messages_per_second: int = 10
    burst_size: int = 20
    critical_bypass: bool = True

    # Prioritization
    price_change_threshold: float = 0.02
    volume_spike_multiplier: float = 3.0
    critical_event_types: list[str] = field(default_factory=lambda: ["order_fill"])

    # Memory Management
    max_candles_per_market: int = 1000
    retention_seconds: int = 86400

    # Backpressure
    send_buffer_threshold: int = 65536
    slow_client_timeout: int = 30
    drop_non_critical_for_slow: bool = True

    # Concurrency
    worker_pool_size: int = 10
    max_concurrent_markets: int = 100

    # Signal Cooldown
    min_signal_cooldown_seconds: float = 1.0
    max_signal_cooldown_seconds: float = 30.0
    volatility_window_seconds: int = 300
    volatility_threshold_low: float = 0.005
    volatility_threshold_high: float = 0.03

    # Frontend Polling
    ws_connected_poll_interval_ms: int = 10000
    ws_disconnected_poll_interval_ms: int = 2000
    rest_backoff_multiplier: float = 1.5
    rest_max_backoff_ms: int = 30000

    def __post_init__(self):
        """Sync component configs with top-level fields for backward compatibility."""
        # Sync batcher config
        self.batcher.batch_window_ms = self.batch_window_ms
        self.batcher.max_batch_size = self.max_batch_size
        self.batcher.enable_batching = self.enable_batching

        # Sync rate limiter config
        self.rate_limiter.max_messages_per_second = self.max_messages_per_second
        self.rate_limiter.burst_size = self.burst_size
        self.rate_limiter.critical_bypass = self.critical_bypass

        # Sync prioritizer config
        self.prioritizer.price_change_threshold = self.price_change_threshold
        self.prioritizer.volume_spike_multiplier = self.volume_spike_multiplier
        self.prioritizer.critical_event_types = self.critical_event_types

        # Sync memory config
        self.memory.max_candles_per_market = self.max_candles_per_market
        self.memory.retention_seconds = self.retention_seconds

        # Sync backpressure config
        self.backpressure.send_buffer_threshold = self.send_buffer_threshold
        self.backpressure.slow_client_timeout = self.slow_client_timeout
        self.backpressure.drop_non_critical_for_slow = self.drop_non_critical_for_slow
