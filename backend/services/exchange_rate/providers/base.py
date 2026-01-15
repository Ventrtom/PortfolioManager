"""
Abstract base class for exchange rate providers.
"""
from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Optional, Dict
import logging

from ..types import ExchangeRateResult, CurrencyPair, ProviderStats


class ExchangeRateProvider(ABC):
    """Abstract base class for exchange rate providers"""

    SUPPORTED_CURRENCIES = ['USD', 'EUR', 'CZK']

    def __init__(self, name: str, min_request_interval: float = 0.5):
        self.name = name
        self.min_request_interval = min_request_interval
        self._stats = ProviderStats(name=name)
        self._logger = logging.getLogger(f"exchange_rate.provider.{name}")

    @abstractmethod
    def get_rate(
        self,
        pair: CurrencyPair,
        rate_date: date
    ) -> Optional[ExchangeRateResult]:
        """
        Fetch exchange rate for a currency pair on a specific date.

        Args:
            pair: Currency pair to fetch
            rate_date: Date for historical rate

        Returns:
            ExchangeRateResult if successful, None if rate unavailable

        Raises:
            NetworkError: If network request fails
            RateLimitError: If rate limit exceeded
            ProviderError: If provider returns an error
        """
        pass

    @abstractmethod
    def get_all_rates_for_base(
        self,
        base: str,
        rate_date: date
    ) -> Dict[str, float]:
        """
        Fetch all rates for a base currency on a specific date.

        Args:
            base: Base currency
            rate_date: Date for historical rates

        Returns:
            Dict mapping target currency to rate
        """
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """
        Check if the provider is operational.

        Returns:
            True if provider is available and responding
        """
        pass

    @property
    def stats(self) -> ProviderStats:
        """Get provider statistics"""
        return self._stats

    def supports_currency(self, currency: str) -> bool:
        """Check if provider supports a currency"""
        return currency.upper() in self.SUPPORTED_CURRENCIES

    def _record_success(self, response_time_ms: float):
        """Record a successful request"""
        self._stats.requests_made += 1
        self._stats.successful_requests += 1
        self._stats.last_request_time = datetime.utcnow()
        # Rolling average
        n = self._stats.successful_requests
        self._stats.avg_response_time_ms = (
            (self._stats.avg_response_time_ms * (n - 1) + response_time_ms) / n
        )

    def _record_failure(self, is_rate_limit: bool = False):
        """Record a failed request"""
        self._stats.requests_made += 1
        self._stats.failed_requests += 1
        self._stats.last_request_time = datetime.utcnow()
        if is_rate_limit:
            self._stats.rate_limit_hits += 1
