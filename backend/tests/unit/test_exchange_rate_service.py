"""
Unit tests for exchange rate service.
"""
import pytest
from datetime import date, datetime
from unittest.mock import Mock

from services.exchange_rate import (
    ExchangeRateService, ExchangeRateResult, CurrencyPair,
    RateSource, Confidence, InvalidCurrencyError, RateNotFoundError,
    ExchangeRateConfig
)
from services.exchange_rate.cache import ExchangeRateCache


class TestExchangeRateService:
    """Tests for ExchangeRateService"""

    def test_identity_rate_returns_1(self, service_with_mocks):
        """Same currency should return rate of 1.0"""
        service, _, _, db = service_with_mocks

        rate = service.get_rate("USD", "USD", date(2024, 1, 15), db)

        assert rate == 1.0

    def test_identity_rate_with_metadata(self, service_with_mocks):
        """Same currency should return identity source"""
        service, _, _, db = service_with_mocks

        result = service.get_rate_with_metadata(
            "USD", "USD", date(2024, 1, 15), db
        )

        assert result.rate == 1.0
        assert result.source == RateSource.IDENTITY
        assert result.confidence == Confidence.HIGH

    def test_invalid_currency_raises_error(self, service_with_mocks):
        """Invalid currency should raise InvalidCurrencyError"""
        service, _, _, db = service_with_mocks

        with pytest.raises(InvalidCurrencyError) as exc_info:
            service.get_rate("INVALID", "USD", date(2024, 1, 15), db)

        assert exc_info.value.currency == "INVALID"
        assert "USD" in exc_info.value.details["supported"]

    def test_cache_hit_returns_cached_rate(self, mock_config, populated_db):
        """Should return rate from cache when available"""
        service = ExchangeRateService(config=mock_config)

        result = service.get_rate_with_metadata(
            "USD", "EUR", date(2024, 1, 15), populated_db
        )

        assert result.rate == 0.85
        assert result.source == RateSource.DATABASE_CACHE

    def test_provider_called_when_cache_miss(self, service_with_mocks):
        """Should call provider when rate not in cache"""
        service, mock_provider, _, db = service_with_mocks

        mock_provider.get_rate.return_value = ExchangeRateResult(
            pair=CurrencyPair("USD", "EUR"),
            rate=0.86,
            rate_date=date(2024, 1, 20),
            source=RateSource.EXCHANGERATE_API,
            confidence=Confidence.HIGH,
            fetched_at=datetime.utcnow()
        )

        result = service.get_rate_with_metadata(
            "USD", "EUR", date(2024, 1, 20), db
        )

        assert result.rate == 0.86
        mock_provider.get_rate.assert_called()

    def test_fallback_provider_used_when_primary_fails(self, service_with_mocks):
        """Should try fallback provider when primary fails"""
        service, mock_provider, fallback_provider, db = service_with_mocks

        # Primary returns None, simulating failure
        mock_provider.get_rate.return_value = None
        fallback_provider.get_rate.return_value = ExchangeRateResult(
            pair=CurrencyPair("USD", "EUR"),
            rate=0.87,
            rate_date=date(2024, 1, 20),
            source=RateSource.EXCHANGERATE_HOST,
            confidence=Confidence.HIGH,
            fetched_at=datetime.utcnow()
        )

        result = service.get_rate_with_metadata(
            "USD", "EUR", date(2024, 1, 20), db
        )

        assert result.rate == 0.87
        mock_provider.get_rate.assert_called()
        fallback_provider.get_rate.assert_called()

    def test_historical_fallback_when_providers_fail(
        self, mock_config, populated_db
    ):
        """Should use historical fallback when all providers fail"""
        # Create service with mock providers that return None
        mock_primary = Mock()
        mock_primary.name = "mock-primary"
        mock_primary.get_rate.return_value = None

        mock_fallback = Mock()
        mock_fallback.name = "mock-fallback"
        mock_fallback.get_rate.return_value = None

        service = ExchangeRateService(
            config=mock_config,
            primary_provider=mock_primary,
            fallback_provider=mock_fallback,
            cache=ExchangeRateCache(memory_ttl_seconds=60)
        )

        # Request a future date (no direct rate available, will use fallback)
        result = service.get_rate_with_metadata(
            "USD", "EUR", date(2024, 1, 20), populated_db
        )

        assert result.rate == 0.85  # Historical rate from 2024-01-15
        assert result.source == RateSource.HISTORICAL_FALLBACK
        assert result.is_stale is True
        assert result.staleness_days == 5

    def test_rate_not_found_when_all_fail(self, service_with_mocks):
        """Should raise RateNotFoundError when all methods fail"""
        service, mock_provider, fallback_provider, db = service_with_mocks
        mock_provider.get_rate.return_value = None
        fallback_provider.get_rate.return_value = None

        with pytest.raises(RateNotFoundError) as exc_info:
            service.get_rate("USD", "EUR", date(2020, 1, 1), db)

        assert "USD" in str(exc_info.value)
        assert "EUR" in str(exc_info.value)

    def test_convert_amount(self, service_with_mocks):
        """Should correctly convert amounts"""
        service, mock_provider, _, db = service_with_mocks

        mock_provider.get_rate.return_value = ExchangeRateResult(
            pair=CurrencyPair("USD", "EUR"),
            rate=0.85,
            rate_date=date(2024, 1, 15),
            source=RateSource.EXCHANGERATE_API,
            confidence=Confidence.HIGH,
            fetched_at=datetime.utcnow()
        )

        result = service.convert_amount(
            100.0, "USD", "EUR", date(2024, 1, 15), db
        )

        assert result == 85.0

    def test_get_all_currency_amounts(self, service_with_mocks):
        """Should convert to all currencies"""
        service, mock_provider, _, db = service_with_mocks

        def mock_get_rate(pair, rate_date):
            rates = {
                ("USD", "EUR"): 0.85,
                ("USD", "CZK"): 22.5,
            }
            rate = rates.get((pair.base, pair.target))
            if rate:
                return ExchangeRateResult(
                    pair=pair,
                    rate=rate,
                    rate_date=rate_date,
                    source=RateSource.EXCHANGERATE_API,
                    confidence=Confidence.HIGH,
                    fetched_at=datetime.utcnow()
                )
            return None

        mock_provider.get_rate.side_effect = mock_get_rate

        result = service.get_all_currency_amounts(
            100.0, "USD", date(2024, 1, 15), db
        )

        assert result.usd == 100.0
        assert result.eur == 85.0
        assert result.czk == 2250.0
        assert result.is_complete is True

    def test_batch_get_rates(self, mock_config, populated_db):
        """Should efficiently fetch multiple rates"""
        service = ExchangeRateService(config=mock_config)

        pairs = [
            ("USD", "EUR", date(2024, 1, 15)),
            ("USD", "CZK", date(2024, 1, 15)),
            ("EUR", "CZK", date(2024, 1, 15)),
        ]

        results = service.batch_get_rates(pairs, populated_db)

        assert len(results) == 3
        assert "USD/EUR/2024-01-15" in results
        assert results["USD/EUR/2024-01-15"].rate == 0.85

    def test_health_check(self, service_with_mocks):
        """Should return health status of providers"""
        service, mock_provider, fallback_provider, _ = service_with_mocks

        health = service.health_check()

        assert mock_provider.name in health
        assert health[mock_provider.name] is True

    def test_provider_stats(self, service_with_mocks):
        """Should return provider statistics"""
        service, mock_provider, fallback_provider, _ = service_with_mocks

        stats = service.get_provider_stats()

        assert mock_provider.name in stats
        assert "requests_made" in stats[mock_provider.name]


class TestCurrencyPair:
    """Tests for CurrencyPair dataclass"""

    def test_uppercase_normalization(self):
        """Currency codes should be uppercased"""
        pair = CurrencyPair("usd", "eur")
        assert pair.base == "USD"
        assert pair.target == "EUR"

    def test_identity_detection(self):
        """Same currency pair should be detected as identity"""
        pair = CurrencyPair("USD", "USD")
        assert pair.is_identity is True

    def test_non_identity(self):
        """Different currencies should not be identity"""
        pair = CurrencyPair("USD", "EUR")
        assert pair.is_identity is False

    def test_string_representation(self):
        """String representation should be BASE/TARGET"""
        pair = CurrencyPair("USD", "EUR")
        assert str(pair) == "USD/EUR"

    def test_immutable(self):
        """CurrencyPair should be immutable (frozen)"""
        pair = CurrencyPair("USD", "EUR")
        with pytest.raises(AttributeError):
            pair.base = "GBP"

    def test_hashable(self):
        """CurrencyPair should be hashable for use in dicts/sets"""
        pair1 = CurrencyPair("USD", "EUR")
        pair2 = CurrencyPair("USD", "EUR")

        # Should be usable as dict key
        d = {pair1: "test"}
        assert d[pair2] == "test"

        # Should work in sets
        s = {pair1, pair2}
        assert len(s) == 1


class TestExchangeRateResult:
    """Tests for ExchangeRateResult"""

    def test_to_dict(self, sample_rate_result):
        """Should serialize to dictionary correctly"""
        d = sample_rate_result.to_dict()

        assert d["base"] == "USD"
        assert d["target"] == "EUR"
        assert d["rate"] == 0.85
        assert d["source"] == "exchangerate-api.io"
        assert d["confidence"] == "high"

    def test_stale_defaults_to_false(self, sample_rate_result):
        """is_stale should default to False"""
        assert sample_rate_result.is_stale is False
        assert sample_rate_result.staleness_days == 0
