"""
Frankfurter API provider implementation.
Free, no API key required, historical data back to 1999.
https://www.frankfurter.app/docs/
"""
import time
import requests
from datetime import date, datetime
from typing import Optional, Dict

from .base import ExchangeRateProvider
from ..types import ExchangeRateResult, CurrencyPair, RateSource, Confidence
from ..errors import NetworkError


class FrankfurterProvider(ExchangeRateProvider):
    """
    Primary provider using Frankfurter API (free, no API key required).

    Based on European Central Bank (ECB) data - very reliable.
    Historical data available from January 4, 1999.
    Supports 30 major currencies.
    """

    BASE_URL = "https://api.frankfurter.app"

    # Frankfurter supports these currencies (ECB reference rates)
    SUPPORTED_CURRENCIES = [
        'USD', 'EUR', 'CZK', 'GBP', 'JPY', 'CHF', 'AUD', 'CAD',
        'CNY', 'HKD', 'NZD', 'SEK', 'KRW', 'SGD', 'NOK', 'MXN',
        'INR', 'BRL', 'ZAR', 'DKK', 'PLN', 'THB', 'IDR', 'HUF',
        'ILS', 'PHP', 'TRY', 'RON', 'ISK', 'MYR'
    ]

    def __init__(self):
        super().__init__(name="frankfurter", min_request_interval=0.1)
        self._last_request_time: Optional[float] = None

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
        """Fetch exchange rate from Frankfurter API"""
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
            # Frankfurter API format: /YYYY-MM-DD?from=USD&to=EUR,CZK
            url = f"{self.BASE_URL}/{rate_date.isoformat()}"
            params = {
                "from": pair.base,
                "to": pair.target
            }

            response = requests.get(url, params=params, timeout=10)
            response_time_ms = (time.time() - start_time) * 1000

            if response.status_code == 404:
                self._logger.warning(f"Date not available: {rate_date}")
                return None

            response.raise_for_status()
            data = response.json()

            # Response format: {"amount":1.0,"base":"USD","date":"2019-06-14","rates":{"EUR":0.88771}}
            rates = data.get('rates', {})
            actual_date = data.get('date')

            if pair.target not in rates:
                self._logger.warning(f"Rate not found: {pair} on {rate_date}")
                return None

            rate = float(rates[pair.target])
            self._record_success(response_time_ms)

            # Parse the actual date returned (might differ if weekend/holiday)
            if actual_date:
                actual_date = date.fromisoformat(actual_date)
            else:
                actual_date = rate_date

            return ExchangeRateResult(
                pair=pair,
                rate=rate,
                rate_date=actual_date,
                source=RateSource.FRANKFURTER,
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
        """Fetch all rates for a base currency in one request"""
        self._rate_limit_wait()

        try:
            url = f"{self.BASE_URL}/{rate_date.isoformat()}"
            params = {"from": base}

            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 404:
                return {}

            response.raise_for_status()
            data = response.json()

            rates = data.get('rates', {})

            # Filter to only supported currencies
            return {
                currency: float(rate)
                for currency, rate in rates.items()
                if currency in self.SUPPORTED_CURRENCIES
            }

        except Exception as e:
            self._logger.error(f"Failed to fetch all rates: {e}")
            return {}

    def health_check(self) -> bool:
        """Check if Frankfurter API is responding"""
        try:
            url = f"{self.BASE_URL}/latest"
            response = requests.get(url, timeout=5)
            return response.status_code == 200
        except Exception:
            return False
