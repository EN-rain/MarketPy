"""External API integrations package."""

from .base_client import ExternalAPIClient, RateLimit
from .bpi_service import BPIService
from .coincap_client import CoinCapClient
from .coindesk_client import CoinDeskClient
from .coingecko_client import CoinGeckoClient, CoinGeckoRateLimitExceededError
from .coinpaprika_client import CoinPaprikaClient
from .discord_client import DiscordMessage, DiscordWebhookClient, RetryPolicy
from .discord_notifier import DiscordNotifier, DiscordNotifierConfig, NotificationCategory
from .feed_failover import FeedFailoverManager
from .gateway import APIGateway, TTLCache
from .github_client import GitHubClient, GitHubRateLimitExceededError
from .hackernews_client import HackerNewsClient
from .market_metrics_service import MarketMetricsService
from .mempool_client import MempoolClient
from .onchain_monitor import OnChainAlert, OnChainMonitor

__all__ = [
    "APIGateway",
    "BPIService",
    "CoinCapClient",
    "CoinDeskClient",
    "CoinGeckoClient",
    "CoinGeckoRateLimitExceededError",
    "CoinPaprikaClient",
    "DiscordMessage",
    "DiscordNotifier",
    "DiscordNotifierConfig",
    "DiscordWebhookClient",
    "ExternalAPIClient",
    "FeedFailoverManager",
    "GitHubClient",
    "GitHubRateLimitExceededError",
    "HackerNewsClient",
    "MarketMetricsService",
    "MempoolClient",
    "OnChainAlert",
    "OnChainMonitor",
    "NotificationCategory",
    "RateLimit",
    "RetryPolicy",
    "TTLCache",
]
