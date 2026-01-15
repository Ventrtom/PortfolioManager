"""
ExchangeRate-API.io provider implementation.
"""
import os
import time
import requests
from datetime import date, datetime
from typing import Optional, Dict

from .base import ExchangeRateProvider
from ..types import ExchangeRateResult, CurrencyPair, RateSource, Confidence
from ..errors import NetworkError, RateLimitError, ProviderError


class ExchangeRateAPIProvider(ExchangeRateProvider):
    """Primary provider: exchangerate-api.io"""

    BASE_URL = "https://v6.exchangerate-api.io/v6"

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(name="exchangerate-api.io", min_request_interval=0.5)
        self._api_key = api_key or os.getenv('EXCHANGE_RATE_API_KEY')
        self._last_request_time: Optional[float] = None

        if not self._api_key:
            self._logger.warning(
                "No API key provided - provider will not function"
            )
            self._stats.is_available = False

    @property
    def is_configured(self) -> bool:
        """Check if provider is properly configured"""
        return bool(self._api_key)

    def _rate_limit_wait(self):
        """Enforce minimum interval between requests"""
        if self._last_request_time:
            elapsed = time.time() - self._last_request_time
            if elapsed < self.min_request_interval:
                time.sleep(self.min_request_interval - elapsed)
        self._last_request_time = time.time()

    def get_rate(
        self,
        pair: CurrencyPair,
        rate_date: date
    ) -> Optional[ExchangeRateResult]:
        """Fetch exchange rate from ExchangeRate-API"""
        if not self.is_configured:
            return None

        if pair.is_identity:
            return ExchangeRateResult(
                pair=pair,
                rate=1.0,
                rate_date=rate_date,
                source=RateSource.IDENTITY,
                confidence=Confidence.HIGH,
                fetched_at=datetime.utcnow()
            )

        self._rate_limit_wait()
        start_time = time.time()

        try:
            url = (
                f"{self.BASE_URL}/{self._api_key}/history/"
                f"{pair.base}/{rate_date.year}/"
                f"{rate_date.month:02d}/{rate_date.day:02d}"
            )

            response = requests.get(url, timeout=10)
            response_time_ms = (time.time() - start_time) * 1000

            if response.status_code == 429:
                self._record_failure(is_rate_limit=True)
                raise RateLimitError(provider=self.name)

            response.raise_for_status()
            data = response.json()

            if data.get('result') != 'success':
                error_type = data.get('error-type', 'unknown')
                self._record_failure()
                raise ProviderError(
                    provider=self.name,
                    message=f"API returned error: {error_type}",
                    api_error=error_type
                )

            conversion_rates = data.get('conversion_rates', {})

            if pair.target not in conversion_rates:
                self._logger.warning(f"Rate not found: {pair} on {rate_date}")
                return None

            rate = float(conversion_rates[pair.target])
            self._record_success(response_time_ms)

            return ExchangeRateResult(
                pair=pair,
                rate=rate,
                rate_date=rate_date,
                source=RateSource.EXCHANGERATE_API,
                confidence=Confidence.HIGH,
                fetched_at=datetime.utcnow()
            )

        except requests.exceptions.Timeout:
            self._record_failure()
            raise NetworkError(
                message=f"Request timed out for {pair}",
                provider=self.name
            )
        except requests.exceptions.RequestException as e:
            self._record_failure()
            raise NetworkError(
                message=f"Request failed for {pair}: {str(e)}",
                provider=self.name,
                original_error=e
            )

    def get_all_rates_for_base(
        self,
        base: str,
        rate_date: date
    ) -> Dict[str, float]:
        """Fetch all rates for a base currency"""
        if not self.is_configured:
            return {}

        self._rate_limit_wait()

        try:
            url = (
                f"{self.BASE_URL}/{self._api_key}/history/"
                f"{base}/{rate_date.year}/"
                f"{rate_date.month:02d}/{rate_date.day:02d}"
            )

            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get('result') != 'success':
                return {}

            conversion_rates = data.get('conversion_rates', {})

            return {
                currency: float(rate)
                for currency, rate in conversion_rates.items()
                if currency in self.SUPPORTED_CURRENCIES
            }

        except Exception as e:
            self._logger.error(f"Failed to fetch all rates: {e}")
            return {}

    def health_check(self) -> bool:
        """Check if ExchangeRate-API is responding"""
        if not self.is_configured:
            return False

        try:
            url = f"{self.BASE_URL}/{self._api_key}/latest/USD"
            response = requests.get(url, timeout=5)
            return response.status_code == 200
        except Exception:
            return False
