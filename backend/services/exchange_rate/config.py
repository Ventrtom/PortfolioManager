"""
Configuration management for exchange rate service.
"""
import os
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class ExchangeRateConfig:
    """Configuration for exchange rate service"""

    # API Keys
    exchangerate_api_key: Optional[str] = None

    # Cache settings
    memory_cache_ttl_seconds: int = 3600  # 1 hour

    # Provider settings
    primary_provider_timeout: int = 10  # seconds
    fallback_provider_timeout: int = 15  # seconds
    min_request_interval: float = 0.5  # seconds between requests

    # Retry settings
    max_retries: int = 2
    retry_delay_seconds: float = 1.0

    # Historical fallback settings
    max_staleness_days: int = 365  # Don't use rates older than this
    stale_warning_threshold_days: int = 30  # Warn if rate is older than this
    review_threshold_days: int = 90  # Flag for review if older than this

    # Supported currencies
    supported_currencies: Tuple[str, ...] = ('USD', 'EUR', 'CZK')

    @classmethod
    def from_environment(cls) -> 'ExchangeRateConfig':
        """Create configuration from environment variables"""
        return cls(
            exchangerate_api_key=os.getenv('EXCHANGE_RATE_API_KEY'),
            memory_cache_ttl_seconds=int(
                os.getenv('EXCHANGE_RATE_CACHE_TTL', '3600')
            ),
            max_retries=int(os.getenv('EXCHANGE_RATE_MAX_RETRIES', '2')),
        )
