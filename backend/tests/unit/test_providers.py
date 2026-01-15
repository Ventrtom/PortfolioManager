"""
Unit tests for exchange rate providers.
"""
import pytest
from datetime import date, datetime
from unittest.mock import patch, Mock
import requests

from services.exchange_rate.providers.frankfurter import FrankfurterProvider
from services.exchange_rate.providers.exchangerate_api import (
    ExchangeRateAPIProvider
)
from services.exchange_rate.providers.exchangerate_host import (
    ExchangeRateHostProvider
)
from services.exchange_rate import (
    CurrencyPair, RateSource, NetworkError, RateLimitError
)


class TestFrankfurterProvider:
    """Tests for Frankfurter API provider (primary provider)"""

    def test_identity_rate(self):
        """Same currency should return 1.0"""
        provider = FrankfurterProvider()

        result = provider.get_rate(
            CurrencyPair("USD", "USD"),
            date(2019, 6, 15)
        )

        assert result.rate == 1.0
        assert result.source == RateSource.IDENTITY

    @patch('services.exchange_rate.providers.frankfurter.requests.get')
    def test_successful_api_call(self, mock_get):
        """Should parse API response correctly"""
        mock_response = Mock()
        mock_response.status_code = 200
        # Frankfurter API format: {"amount":1.0,"base":"USD","date":"2019-06-14","rates":{"EUR":0.88771}}
        mock_response.json.return_value = {
            "amount": 1.0,
            "base": "USD",
            "date": "2019-06-14",
            "rates": {"EUR": 0.88771, "CZK": 22.672}
        }
        mock_get.return_value = mock_response

        provider = FrankfurterProvider()
        result = provider.get_rate(
            CurrencyPair("USD", "EUR"),
            date(2019, 6, 15)
        )

        assert result.rate == 0.88771
        assert result.source == RateSource.FRANKFURTER
        assert result.confidence.value == "high"

    @patch('services.exchange_rate.providers.frankfurter.requests.get')
    def test_historical_date_2019(self, mock_get):
        """Should handle historical data from 2019"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "amount": 1.0,
            "base": "USD",
            "date": "2019-01-02",
            "rates": {"EUR": 0.87654, "CZK": 22.123}
        }
        mock_get.return_value = mock_response

        provider = FrankfurterProvider()
        result = provider.get_rate(
            CurrencyPair("USD", "EUR"),
            date(2019, 1, 2)
        )

        assert result.rate == 0.87654
        assert result.rate_date == date(2019, 1, 2)

    @patch('services.exchange_rate.providers.frankfurter.requests.get')
    def test_not_found_returns_none(self, mock_get):
        """Should return None for 404"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        provider = FrankfurterProvider()
        result = provider.get_rate(
            CurrencyPair("USD", "EUR"),
            date(1990, 1, 1)  # Before data availability
        )

        assert result is None

    @patch('services.exchange_rate.providers.frankfurter.requests.get')
    def test_rate_not_in_response(self, mock_get):
        """Should return None if target currency not in response"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "amount": 1.0,
            "base": "USD",
            "date": "2019-06-14",
            "rates": {"GBP": 0.75}  # No EUR
        }
        mock_get.return_value = mock_response

        provider = FrankfurterProvider()
        result = provider.get_rate(
            CurrencyPair("USD", "EUR"),
            date(2019, 6, 15)
        )

        assert result is None

    @patch('services.exchange_rate.providers.frankfurter.requests.get')
    def test_network_timeout_error(self, mock_get):
        """Should raise NetworkError on timeout"""
        mock_get.side_effect = requests.exceptions.Timeout()

        provider = FrankfurterProvider()

        with pytest.raises(NetworkError) as exc_info:
            provider.get_rate(CurrencyPair("USD", "EUR"), date(2019, 6, 15))

        assert exc_info.value.provider == "frankfurter"

    @patch('services.exchange_rate.providers.frankfurter.requests.get')
    def test_network_connection_error(self, mock_get):
        """Should raise NetworkError on connection failure"""
        mock_get.side_effect = requests.exceptions.ConnectionError()

        provider = FrankfurterProvider()

        with pytest.raises(NetworkError):
            provider.get_rate(CurrencyPair("USD", "EUR"), date(2019, 6, 15))

    @patch('services.exchange_rate.providers.frankfurter.requests.get')
    def test_stats_tracking_success(self, mock_get):
        """Should track request statistics on success"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "amount": 1.0,
            "base": "USD",
            "date": "2019-06-14",
            "rates": {"EUR": 0.88771}
        }
        mock_get.return_value = mock_response

        provider = FrankfurterProvider()
        provider.get_rate(CurrencyPair("USD", "EUR"), date(2019, 6, 15))

        assert provider.stats.requests_made == 1
        assert provider.stats.successful_requests == 1
        assert provider.stats.failed_requests == 0

    @patch('services.exchange_rate.providers.frankfurter.requests.get')
    def test_stats_tracking_failure(self, mock_get):
        """Should track request statistics on failure"""
        mock_get.side_effect = requests.exceptions.Timeout()

        provider = FrankfurterProvider()

        try:
            provider.get_rate(CurrencyPair("USD", "EUR"), date(2019, 6, 15))
        except NetworkError:
            pass

        assert provider.stats.requests_made == 1
        assert provider.stats.successful_requests == 0
        assert provider.stats.failed_requests == 1

    @patch('services.exchange_rate.providers.frankfurter.requests.get')
    def test_get_all_rates_for_base(self, mock_get):
        """Should fetch all rates for a base currency"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "amount": 1.0,
            "base": "USD",
            "date": "2019-06-14",
            "rates": {
                "EUR": 0.88771,
                "CZK": 22.672,
                "GBP": 0.78,
                "JPY": 108.5
            }
        }
        mock_get.return_value = mock_response

        provider = FrankfurterProvider()
        result = provider.get_all_rates_for_base("USD", date(2019, 6, 15))

        assert "EUR" in result
        assert "CZK" in result
        assert "GBP" in result  # Frankfurter supports more currencies

    @patch('services.exchange_rate.providers.frankfurter.requests.get')
    def test_health_check_success(self, mock_get):
        """Should return True when API is responding"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        provider = FrankfurterProvider()
        assert provider.health_check() is True

    @patch('services.exchange_rate.providers.frankfurter.requests.get')
    def test_health_check_failure(self, mock_get):
        """Should return False when API is not responding"""
        mock_get.side_effect = requests.exceptions.Timeout()

        provider = FrankfurterProvider()
        assert provider.health_check() is False


class TestExchangeRateAPIProvider:
    """Tests for ExchangeRate-API provider"""

    @patch.dict('os.environ', {'EXCHANGE_RATE_API_KEY': ''}, clear=False)
    def test_unconfigured_provider_returns_none(self):
        """Provider without API key should return None"""
        # Clear the env var to simulate unconfigured state
        import os
        old_val = os.environ.pop('EXCHANGE_RATE_API_KEY', None)
        try:
            provider = ExchangeRateAPIProvider(api_key=None)

            result = provider.get_rate(
                CurrencyPair("USD", "EUR"),
                date(2024, 1, 15)
            )

            assert result is None
        finally:
            if old_val:
                os.environ['EXCHANGE_RATE_API_KEY'] = old_val

    def test_is_configured_with_key(self):
        """Provider with API key should be configured"""
        provider = ExchangeRateAPIProvider(api_key="test-key")
        assert provider.is_configured is True

    def test_is_not_configured_without_key(self):
        """Provider without API key should not be configured"""
        import os
        old_val = os.environ.pop('EXCHANGE_RATE_API_KEY', None)
        try:
            provider = ExchangeRateAPIProvider(api_key=None)
            assert provider.is_configured is False
        finally:
            if old_val:
                os.environ['EXCHANGE_RATE_API_KEY'] = old_val

    def test_identity_rate(self):
        """Same currency should return 1.0"""
        provider = ExchangeRateAPIProvider(api_key="test-key")

        result = provider.get_rate(
            CurrencyPair("USD", "USD"),
            date(2024, 1, 15)
        )

        assert result.rate == 1.0
        assert result.source == RateSource.IDENTITY

    @patch('services.exchange_rate.providers.exchangerate_api.requests.get')
    def test_successful_api_call(self, mock_get):
        """Should parse API response correctly"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": "success",
            "conversion_rates": {"EUR": 0.85, "CZK": 22.5}
        }
        mock_get.return_value = mock_response

        provider = ExchangeRateAPIProvider(api_key="test-key")
        result = provider.get_rate(
            CurrencyPair("USD", "EUR"),
            date(2024, 1, 15)
        )

        assert result.rate == 0.85
        assert result.source == RateSource.EXCHANGERATE_API
        assert result.confidence.value == "high"

    @patch('services.exchange_rate.providers.exchangerate_api.requests.get')
    def test_rate_limit_error(self, mock_get):
        """Should raise RateLimitError on 429"""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_get.return_value = mock_response

        provider = ExchangeRateAPIProvider(api_key="test-key")

        with pytest.raises(RateLimitError) as exc_info:
            provider.get_rate(CurrencyPair("USD", "EUR"), date(2024, 1, 15))

        assert exc_info.value.provider == "exchangerate-api.io"

    @patch('services.exchange_rate.providers.exchangerate_api.requests.get')
    def test_network_timeout_error(self, mock_get):
        """Should raise NetworkError on timeout"""
        mock_get.side_effect = requests.exceptions.Timeout()

        provider = ExchangeRateAPIProvider(api_key="test-key")

        with pytest.raises(NetworkError) as exc_info:
            provider.get_rate(CurrencyPair("USD", "EUR"), date(2024, 1, 15))

        assert exc_info.value.provider == "exchangerate-api.io"

    @patch('services.exchange_rate.providers.exchangerate_api.requests.get')
    def test_network_connection_error(self, mock_get):
        """Should raise NetworkError on connection failure"""
        mock_get.side_effect = requests.exceptions.ConnectionError()

        provider = ExchangeRateAPIProvider(api_key="test-key")

        with pytest.raises(NetworkError):
            provider.get_rate(CurrencyPair("USD", "EUR"), date(2024, 1, 15))

    @patch('services.exchange_rate.providers.exchangerate_api.requests.get')
    def test_stats_tracking_success(self, mock_get):
        """Should track request statistics on success"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": "success",
            "conversion_rates": {"EUR": 0.85}
        }
        mock_get.return_value = mock_response

        provider = ExchangeRateAPIProvider(api_key="test-key")
        provider.get_rate(CurrencyPair("USD", "EUR"), date(2024, 1, 15))

        assert provider.stats.requests_made == 1
        assert provider.stats.successful_requests == 1
        assert provider.stats.failed_requests == 0

    @patch('services.exchange_rate.providers.exchangerate_api.requests.get')
    def test_stats_tracking_failure(self, mock_get):
        """Should track request statistics on failure"""
        mock_get.side_effect = requests.exceptions.Timeout()

        provider = ExchangeRateAPIProvider(api_key="test-key")

        try:
            provider.get_rate(CurrencyPair("USD", "EUR"), date(2024, 1, 15))
        except NetworkError:
            pass

        assert provider.stats.requests_made == 1
        assert provider.stats.successful_requests == 0
        assert provider.stats.failed_requests == 1

    @patch('services.exchange_rate.providers.exchangerate_api.requests.get')
    def test_rate_not_in_response(self, mock_get):
        """Should return None if target currency not in response"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": "success",
            "conversion_rates": {"GBP": 0.75}  # No EUR
        }
        mock_get.return_value = mock_response

        provider = ExchangeRateAPIProvider(api_key="test-key")
        result = provider.get_rate(
            CurrencyPair("USD", "EUR"),
            date(2024, 1, 15)
        )

        assert result is None

    @patch('services.exchange_rate.providers.exchangerate_api.requests.get')
    def test_health_check_success(self, mock_get):
        """Should return True when API is responding"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        provider = ExchangeRateAPIProvider(api_key="test-key")
        assert provider.health_check() is True

    @patch('services.exchange_rate.providers.exchangerate_api.requests.get')
    def test_health_check_failure(self, mock_get):
        """Should return False when API is not responding"""
        mock_get.side_effect = requests.exceptions.Timeout()

        provider = ExchangeRateAPIProvider(api_key="test-key")
        assert provider.health_check() is False


class TestExchangeRateHostProvider:
    """Tests for fawazahmed0 currency API provider (ExchangeRateHostProvider)"""

    def test_identity_rate(self):
        """Same currency should return 1.0"""
        provider = ExchangeRateHostProvider()

        result = provider.get_rate(
            CurrencyPair("USD", "USD"),
            date(2024, 1, 15)
        )

        assert result.rate == 1.0
        assert result.source == RateSource.IDENTITY

    @patch('services.exchange_rate.providers.exchangerate_host.requests.get')
    def test_successful_api_call(self, mock_get):
        """Should parse API response correctly"""
        mock_response = Mock()
        mock_response.status_code = 200
        # fawazahmed0 API format: {"date": "...", "usd": {"eur": 0.85, ...}}
        mock_response.json.return_value = {
            "date": "2024-01-15",
            "usd": {"eur": 0.85, "czk": 22.5}
        }
        mock_get.return_value = mock_response

        provider = ExchangeRateHostProvider()
        result = provider.get_rate(
            CurrencyPair("USD", "EUR"),
            date(2024, 1, 15)
        )

        assert result.rate == 0.85
        assert result.source == RateSource.EXCHANGERATE_HOST

    @patch('services.exchange_rate.providers.exchangerate_host.requests.get')
    def test_unsuccessful_response(self, mock_get):
        """Should return None when data is missing"""
        mock_response = Mock()
        mock_response.status_code = 200
        # Response with no rates data
        mock_response.json.return_value = {"date": "2024-01-15"}
        mock_get.return_value = mock_response

        provider = ExchangeRateHostProvider()
        result = provider.get_rate(
            CurrencyPair("USD", "EUR"),
            date(2024, 1, 15)
        )

        assert result is None

    @patch('services.exchange_rate.providers.exchangerate_host.requests.get')
    def test_network_error(self, mock_get):
        """Should raise NetworkError on connection failure"""
        mock_get.side_effect = requests.exceptions.ConnectionError()

        provider = ExchangeRateHostProvider()

        with pytest.raises(NetworkError) as exc_info:
            provider.get_rate(CurrencyPair("USD", "EUR"), date(2024, 1, 15))

        assert exc_info.value.provider == "fawazahmed0-currency-api"

    @patch('services.exchange_rate.providers.exchangerate_host.requests.get')
    def test_get_all_rates_for_base(self, mock_get):
        """Should fetch all rates for a base currency"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "date": "2024-01-15",
            "usd": {
                "usd": 1.0,
                "eur": 0.85,
                "czk": 22.5,
                "gbp": 0.75  # Should be filtered out
            }
        }
        mock_get.return_value = mock_response

        provider = ExchangeRateHostProvider()
        result = provider.get_all_rates_for_base("USD", date(2024, 1, 15))

        assert "USD" in result
        assert "EUR" in result
        assert "CZK" in result
        assert "GBP" not in result  # Not in SUPPORTED_CURRENCIES

    @patch('services.exchange_rate.providers.exchangerate_host.requests.get')
    def test_health_check_success(self, mock_get):
        """Should return True when API is responding"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        provider = ExchangeRateHostProvider()
        assert provider.health_check() is True

    @patch('services.exchange_rate.providers.exchangerate_host.requests.get')
    def test_health_check_failure(self, mock_get):
        """Should return False when API is not responding"""
        mock_get.side_effect = requests.exceptions.Timeout()

        provider = ExchangeRateHostProvider()
        assert provider.health_check() is False
