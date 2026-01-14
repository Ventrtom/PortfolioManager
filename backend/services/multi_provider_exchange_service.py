"""
Multi-Provider Exchange Rate Service
Supports multiple exchange rate APIs with automatic fallback:
1. ExchangeRate-API - Primary (current provider)
2. Open Exchange Rates - Requires API key
3. CurrencyAPI - Requires API key
4. Exchange Rate Host - Free, no API key
"""

import requests
import time
import os
from datetime import date, datetime
from typing import Optional, Dict, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ExchangeRateProvider:
    """Base class for exchange rate providers"""

    def __init__(self, name: str, api_key: Optional[str] = None):
        self.name = name
        self.api_key = api_key
        self.last_request_time = None
        self.request_count = 0
        self.min_request_interval = 0.5  # 500ms between requests

    def can_make_request(self) -> bool:
        """Check if we can make a request based on rate limits"""
        if self.last_request_time:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.min_request_interval:
                time.sleep(self.min_request_interval - elapsed)
        return True

    def get_historical_rate(self, base: str, target: str, rate_date: date) -> Optional[Dict]:
        """
        Fetch historical exchange rate - to be implemented by subclasses

        Returns:
            {
                'rate': float,
                'source': str,
                'base': str,
                'target': str,
                'date': date
            } or None if unavailable
        """
        raise NotImplementedError


class ExchangeRateAPIProvider(ExchangeRateProvider):
    """ExchangeRate-API provider (current primary)"""

    def __init__(self, api_key: str):
        super().__init__("exchangerate-api.io", api_key)
        self.base_url = "https://v6.exchangerate-api.io/v6"

    def get_historical_rate(self, base: str, target: str, rate_date: date) -> Optional[Dict]:
        """Fetch historical rate from ExchangeRate-API"""
        try:
            self.can_make_request()
            self.last_request_time = time.time()

            url = f"{self.base_url}/{self.api_key}/history/{base}/{rate_date.year}/{rate_date.month:02d}/{rate_date.day:02d}"

            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get('result') != 'success':
                error_type = data.get('error-type', 'unknown')
                logger.warning(f"{self.name}: API error for {base}/{target}: {error_type}")
                return None

            conversion_rates = data.get('conversion_rates', {})
            if target not in conversion_rates:
                logger.warning(f"{self.name}: No rate for {base}/{target} on {rate_date}")
                return None

            rate = conversion_rates[target]
            logger.info(f"{self.name}: Successfully fetched {base}/{target} = {rate}")

            return {
                'rate': float(rate),
                'source': self.name,
                'base': base,
                'target': target,
                'date': rate_date
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"{self.name}: Error fetching {base}/{target}: {e}")
            return None
        except Exception as e:
            logger.error(f"{self.name}: Unexpected error for {base}/{target}: {e}")
            return None


class OpenExchangeRatesProvider(ExchangeRateProvider):
    """Open Exchange Rates provider"""

    def __init__(self, api_key: str):
        super().__init__("openexchangerates.org", api_key)
        self.base_url = "https://openexchangerates.org/api"

    def get_historical_rate(self, base: str, target: str, rate_date: date) -> Optional[Dict]:
        """Fetch historical rate from Open Exchange Rates"""
        try:
            self.can_make_request()
            self.last_request_time = time.time()

            # Open Exchange Rates uses USD as base by default
            # For historical data: /api/historical/YYYY-MM-DD.json
            url = f"{self.base_url}/historical/{rate_date.isoformat()}.json"
            params = {
                'app_id': self.api_key,
                'base': base,
                'symbols': target
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            rates = data.get('rates', {})
            if target not in rates:
                logger.warning(f"{self.name}: No rate for {base}/{target} on {rate_date}")
                return None

            rate = rates[target]
            logger.info(f"{self.name}: Successfully fetched {base}/{target} = {rate}")

            return {
                'rate': float(rate),
                'source': self.name,
                'base': base,
                'target': target,
                'date': rate_date
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"{self.name}: Error fetching {base}/{target}: {e}")
            return None
        except Exception as e:
            logger.error(f"{self.name}: Unexpected error for {base}/{target}: {e}")
            return None


class CurrencyAPIProvider(ExchangeRateProvider):
    """CurrencyAPI provider"""

    def __init__(self, api_key: str):
        super().__init__("currencyapi.com", api_key)
        self.base_url = "https://api.currencyapi.com/v3"

    def get_historical_rate(self, base: str, target: str, rate_date: date) -> Optional[Dict]:
        """Fetch historical rate from CurrencyAPI"""
        try:
            self.can_make_request()
            self.last_request_time = time.time()

            # CurrencyAPI historical endpoint
            url = f"{self.base_url}/historical"
            params = {
                'apikey': self.api_key,
                'date': rate_date.isoformat(),
                'base_currency': base,
                'currencies': target
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            rates = data.get('data', {})
            if target not in rates:
                logger.warning(f"{self.name}: No rate for {base}/{target} on {rate_date}")
                return None

            rate = rates[target].get('value')
            if rate is None:
                logger.warning(f"{self.name}: Invalid rate data for {base}/{target}")
                return None

            logger.info(f"{self.name}: Successfully fetched {base}/{target} = {rate}")

            return {
                'rate': float(rate),
                'source': self.name,
                'base': base,
                'target': target,
                'date': rate_date
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"{self.name}: Error fetching {base}/{target}: {e}")
            return None
        except Exception as e:
            logger.error(f"{self.name}: Unexpected error for {base}/{target}: {e}")
            return None


class ExchangeRateHostProvider(ExchangeRateProvider):
    """Exchange Rate Host provider (free, no API key)"""

    def __init__(self):
        super().__init__("exchangerate.host", None)
        self.base_url = "https://api.exchangerate.host"

    def get_historical_rate(self, base: str, target: str, rate_date: date) -> Optional[Dict]:
        """Fetch historical rate from Exchange Rate Host"""
        try:
            self.can_make_request()
            self.last_request_time = time.time()

            # Exchange Rate Host historical endpoint: /{date}
            url = f"{self.base_url}/{rate_date.isoformat()}"
            params = {
                'base': base,
                'symbols': target
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if not data.get('success'):
                logger.warning(f"{self.name}: API error for {base}/{target}")
                return None

            rates = data.get('rates', {})
            if target not in rates:
                logger.warning(f"{self.name}: No rate for {base}/{target} on {rate_date}")
                return None

            rate = rates[target]
            logger.info(f"{self.name}: Successfully fetched {base}/{target} = {rate}")

            return {
                'rate': float(rate),
                'source': self.name,
                'base': base,
                'target': target,
                'date': rate_date
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"{self.name}: Error fetching {base}/{target}: {e}")
            return None
        except Exception as e:
            logger.error(f"{self.name}: Unexpected error for {base}/{target}: {e}")
            return None


class MultiProviderExchangeService:
    """
    Multi-provider exchange rate service with automatic fallback.
    Tries providers in sequence until one succeeds.
    """

    def __init__(self):
        self.providers: List[ExchangeRateProvider] = []
        self._initialize_providers()

        if not self.providers:
            logger.warning("No exchange rate providers available!")

    def _initialize_providers(self):
        """Initialize all available providers based on API keys"""

        # Provider 1: ExchangeRate-API (current primary)
        api_key = os.getenv('EXCHANGE_RATE_API_KEY')
        if api_key:
            self.providers.append(ExchangeRateAPIProvider(api_key))
            logger.info("Initialized ExchangeRate-API provider")
        else:
            logger.warning("EXCHANGE_RATE_API_KEY not found - skipping exchangerate-api.io")

        # Provider 2: Open Exchange Rates
        api_key = os.getenv('OPEN_EXCHANGE_RATES_API_KEY')
        if api_key:
            self.providers.append(OpenExchangeRatesProvider(api_key))
            logger.info("Initialized Open Exchange Rates provider")
        else:
            logger.info("OPEN_EXCHANGE_RATES_API_KEY not found - skipping openexchangerates.org")

        # Provider 3: CurrencyAPI
        api_key = os.getenv('CURRENCY_API_KEY')
        if api_key:
            self.providers.append(CurrencyAPIProvider(api_key))
            logger.info("Initialized CurrencyAPI provider")
        else:
            logger.info("CURRENCY_API_KEY not found - skipping currencyapi.com")

        # Provider 4: Exchange Rate Host (no API key needed)
        self.providers.append(ExchangeRateHostProvider())
        logger.info("Initialized Exchange Rate Host provider")

        logger.info(f"Initialized MultiProviderExchangeService with {len(self.providers)} active providers: {[p.name for p in self.providers]}")

    def get_exchange_rate(
        self,
        base_currency: str,
        target_currency: str,
        rate_date: date
    ) -> Optional[Dict]:
        """
        Get exchange rate from first available provider.

        Args:
            base_currency: Source currency (USD, EUR, CZK)
            target_currency: Target currency (USD, EUR, CZK)
            rate_date: Date for exchange rate

        Returns:
            {
                'rate': float,
                'source': str,  # Provider name
                'base': str,
                'target': str,
                'date': date,
                'confidence': str  # 'high' for API providers
            } or None if all providers fail
        """
        # Same currency check
        if base_currency == target_currency:
            return {
                'rate': 1.0,
                'source': 'identity',
                'base': base_currency,
                'target': target_currency,
                'date': rate_date,
                'confidence': 'high'
            }

        # Try each provider in sequence
        for provider in self.providers:
            logger.info(f"Trying {provider.name} for {base_currency}/{target_currency} on {rate_date}")

            result = provider.get_historical_rate(base_currency, target_currency, rate_date)

            if result:
                result['confidence'] = 'high'  # API providers are high confidence
                logger.info(f"✓ Successfully fetched {base_currency}/{target_currency} from {provider.name}")
                return result

        logger.warning(f"All providers failed for {base_currency}/{target_currency} on {rate_date}")
        return None

    def get_all_rates_for_date(
        self,
        base_currencies: List[str],
        target_currencies: List[str],
        rate_date: date
    ) -> Dict[str, Dict[str, Optional[Dict]]]:
        """
        Fetch all currency pair combinations for a specific date.

        Args:
            base_currencies: List of base currencies
            target_currencies: List of target currencies
            rate_date: Date to fetch rates for

        Returns:
            Nested dict: {base: {target: rate_info}}
        """
        all_rates = {}

        for base in base_currencies:
            all_rates[base] = {}
            for target in target_currencies:
                rate_info = self.get_exchange_rate(base, target, rate_date)
                all_rates[base][target] = rate_info

        return all_rates

    def test_providers(self) -> Dict[str, bool]:
        """
        Test all providers with a simple USD/EUR query.
        Useful for health checks.

        Returns:
            Dict of provider_name: success_status
        """
        test_date = date(2024, 1, 1)  # Use a known historical date
        results = {}

        for provider in self.providers:
            try:
                result = provider.get_historical_rate('USD', 'EUR', test_date)
                results[provider.name] = result is not None
            except Exception as e:
                logger.error(f"Provider test failed for {provider.name}: {e}")
                results[provider.name] = False

        return results
