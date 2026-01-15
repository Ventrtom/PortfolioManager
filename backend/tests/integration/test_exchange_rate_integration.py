"""
Integration tests for exchange rate service.
These tests make real API calls and should be run sparingly.

The primary provider (Frankfurter) is free and doesn't require an API key.
Historical data is available from January 4, 1999.
"""
import pytest
import os
from datetime import date, timedelta

from services.exchange_rate import ExchangeRateService, ExchangeRateConfig, RateSource


# Test dates - Frankfurter (ECB data) has data from January 4, 1999
# Using weekdays to ensure data availability
TEST_DATE_2019 = date(2019, 6, 14)  # Friday
TEST_DATE_2020 = date(2020, 3, 13)  # Friday (around COVID start)
TEST_DATE_2024 = date(2024, 6, 14)  # Friday
TEST_DATE_1999 = date(1999, 1, 4)   # First available date


class TestExchangeRateIntegration:
    """Integration tests with real API (use sparingly)"""

    @pytest.fixture
    def service(self, test_db):
        """Create service with real providers"""
        config = ExchangeRateConfig.from_environment()
        return ExchangeRateService(config=config)

    def test_historical_rate_2019(self, service, test_db):
        """Should fetch historical rate from 2019"""
        result = service.get_rate_with_metadata(
            "USD", "EUR",
            TEST_DATE_2019,
            test_db
        )

        assert result is not None
        assert result.source == RateSource.FRANKFURTER
        # USD/EUR in June 2019 was around 0.88-0.89
        assert 0.85 < result.rate < 0.95

    def test_historical_rate_2020(self, service, test_db):
        """Should fetch historical rate from 2020"""
        result = service.get_rate_with_metadata(
            "USD", "CZK",
            TEST_DATE_2020,
            test_db
        )

        assert result is not None
        # USD/CZK in March 2020 was around 23-25
        assert 20 < result.rate < 30

    def test_historical_rate_earliest(self, service, test_db):
        """Should fetch rate from earliest available date (1999)"""
        result = service.get_rate_with_metadata(
            "USD", "EUR",
            TEST_DATE_1999,
            test_db
        )

        assert result is not None
        # USD/EUR in early 1999 was around 0.85
        assert 0.75 < result.rate < 0.95

    def test_real_api_czk_rate(self, service, test_db):
        """Should fetch USD/CZK rate"""
        result = service.get_rate_with_metadata(
            "USD", "CZK",
            TEST_DATE_2024,
            test_db
        )

        assert result is not None
        # USD/CZK should be in reasonable range (typically 20-25)
        assert 15 < result.rate < 30

    def test_health_check(self, service):
        """Should report provider health"""
        health = service.health_check()

        # At least one provider should be healthy
        assert any(health.values())
        # Frankfurter should be healthy (primary provider)
        assert health.get("frankfurter", False) is True

    def test_provider_stats_after_request(self, service, test_db):
        """Should track provider statistics"""
        # Make a request
        try:
            service.get_rate("USD", "EUR", TEST_DATE_2019, test_db)
        except Exception:
            pass  # Stats should be tracked even on failure

        stats = service.get_provider_stats()

        # Should have some requests recorded
        total_requests = sum(
            s["requests_made"] for s in stats.values()
        )
        assert total_requests >= 1

    def test_caching_works(self, service, test_db):
        """Should cache rates and not hit API twice"""
        # First request
        result1 = service.get_rate_with_metadata(
            "USD", "EUR",
            TEST_DATE_2019,
            test_db
        )

        # Second request should come from cache
        result2 = service.get_rate_with_metadata(
            "USD", "EUR",
            TEST_DATE_2019,
            test_db
        )

        # Rates should be the same
        assert result1.rate == result2.rate

        # Second result should come from cache
        # (either memory or database)
        assert result2.source.value in [
            "memory_cache", "database_cache"
        ]

    def test_batch_get_rates(self, service, test_db):
        """Should fetch multiple rates"""
        pairs = [
            ("USD", "EUR", TEST_DATE_2019),
            ("USD", "CZK", TEST_DATE_2019),
            ("EUR", "CZK", TEST_DATE_2019),
        ]

        results = service.batch_get_rates(pairs, test_db)

        assert len(results) == 3
        for key, result in results.items():
            assert result.rate > 0

    def test_conversion_across_years(self, service, test_db):
        """Should correctly convert amounts using historical rates"""
        # Convert 1000 USD to EUR in 2019
        amount = service.convert_amount(
            1000.0, "USD", "EUR", TEST_DATE_2019, test_db
        )

        # In June 2019, 1000 USD was about 880-890 EUR
        assert 850 < amount < 950

    def test_get_all_currency_amounts(self, service, test_db):
        """Should convert to all supported currencies"""
        result = service.get_all_currency_amounts(
            1000.0, "USD", TEST_DATE_2019, test_db
        )

        assert result.usd == 1000.0
        assert result.eur is not None and 800 < result.eur < 1000
        assert result.czk is not None and 20000 < result.czk < 30000
        assert result.is_complete
