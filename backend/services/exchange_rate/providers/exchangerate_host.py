"""
Fawazahmed0 Currency API provider implementation (free, no API key required).
https://github.com/fawazahmed0/exchange-api
"""
import time
import requests
from datetime import date, datetime
from typing import Optional, Dict

from .base import ExchangeRateProvider
from ..types import ExchangeRateResult, CurrencyPair, RateSource, Confidence
from ..errors import NetworkError


class ExchangeRateHostProvider(ExchangeRateProvider):
    """
    Fallback provider using fawazahmed0/currency-api (free, no API key required).

    Note: Class name kept as ExchangeRateHostProvider for backward compatibility,
    but now uses the fawazahmed0 currency API which is free and actively maintained.
    """

    # Primary CDN URL
    PRIMARY_URL = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@{date}/v1/currencies/{currency}.json"
    # Fallback Cloudflare URL
    FALLBACK_URL = "https://{date}.currency-api.pages.dev/v1/currencies/{currency}.json"

    def __init__(self):
        super().__init__(name="fawazahmed0-currency-api", min_request_interval=0.5)
        self._last_request_time: Optional[float] = None

    def _rate_limit_wait(self):
        """Enforce minimum interval between requests"""
        if self._last_request_time:
            elapsed = time.time() - self._last_request_time
            if elapsed < self.min_request_interval:
                time.sleep(self.min_request_interval - elapsed)
        self._last_request_time = time.time()

    def _fetch_rates(self, base_currency: str, rate_date: date) -> Optional[Dict]:
        """Fetch all rates for a base currency, with fallback URL"""
        base_lower = base_currency.lower()
        date_str = rate_date.isoformat()

        # Try primary URL first
        primary_url = self.PRIMARY_URL.format(date=date_str, currency=base_lower)

        try:
            response = requests.get(primary_url, timeout=10)
            if response.status_code == 200:
                return response.json()
        except requests.exceptions.RequestException:
            pass  # Try fallback

        # Try fallback URL
        fallback_url = self.FALLBACK_URL.format(date=date_str, currency=base_lower)

        try:
            response = requests.get(fallback_url, timeout=10)
            if response.status_code == 200:
                return response.json()
        except requests.exceptions.RequestException as e:
            raise NetworkError(
                message=f"Both primary and fallback URLs failed for {base_currency}: {str(e)}",
                provider=self.name,
                original_error=e
            )

        return None

    def get_rate(
        self,
        pair: CurrencyPair,
        rate_date: date
    ) -> Optional[ExchangeRateResult]:
        """Fetch exchange rate from fawazahmed0 currency API"""
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
            data = self._fetch_rates(pair.base, rate_date)
            response_time_ms = (time.time() - start_time) * 1000

            if data is None:
                self._record_failure()
                self._logger.warning(f"No data returned for {pair} on {rate_date}")
                return None

            # The API returns data in format: {"date": "...", "usd": {"eur": 0.85, ...}}
            base_lower = pair.base.lower()
            target_lower = pair.target.lower()

            rates = data.get(base_lower, {})

            if target_lower not in rates:
                self._record_failure()
                self._logger.warning(f"Rate not found: {pair} on {rate_date}")
                return None

            rate = float(rates[target_lower])
            self._record_success(response_time_ms)

            return ExchangeRateResult(
                pair=pair,
                rate=rate,
                rate_date=rate_date,
                source=RateSource.EXCHANGERATE_HOST,  # Keep for backward compatibility
                confidence=Confidence.HIGH,
                fetched_at=datetime.utcnow()
            )

        except NetworkError:
            raise
        except Exception as e:
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
        """Fetch all rates for a base currency in one request"""
        self._rate_limit_wait()

        try:
            data = self._fetch_rates(base, rate_date)

            if data is None:
                return {}

            base_lower = base.lower()
            rates = data.get(base_lower, {})

            return {
                currency: float(rates.get(currency.lower(), 0))
                for currency in self.SUPPORTED_CURRENCIES
                if currency.lower() in rates
            }

        except Exception as e:
            self._logger.error(f"Failed to fetch all rates: {e}")
            return {}

    def health_check(self) -> bool:
        """Check if the API is responding"""
        try:
            url = self.PRIMARY_URL.format(date="latest", currency="usd")
            response = requests.get(url, timeout=5)
            return response.status_code == 200
        except Exception:
            # Try fallback
            try:
                url = self.FALLBACK_URL.format(date="latest", currency="usd")
                response = requests.get(url, timeout=5)
                return response.status_code == 200
            except Exception:
                return False
