"""
Unit tests for exchange rate cache.
"""
import pytest
from datetime import date, datetime, timedelta
from unittest.mock import patch

from services.exchange_rate.cache import (
    InMemoryCache, DatabaseCache, ExchangeRateCache
)
from services.exchange_rate import (
    ExchangeRateResult, CurrencyPair, RateSource, Confidence
)


class TestInMemoryCache:
    """Tests for in-memory cache"""

    def test_set_and_get(self, sample_rate_result):
        """Should store and retrieve rate"""
        cache = InMemoryCache(ttl_seconds=60)

        cache.set(sample_rate_result)
        result = cache.get(
            sample_rate_result.pair,
            sample_rate_result.rate_date
        )

        assert result is not None
        assert result.rate == sample_rate_result.rate
        assert result.source == RateSource.MEMORY_CACHE

    def test_cache_miss(self):
        """Should return None for missing entry"""
        cache = InMemoryCache(ttl_seconds=60)

        result = cache.get(CurrencyPair("USD", "EUR"), date(2024, 1, 15))

        assert result is None

    def test_cache_size(self, sample_rate_result):
        """Should track cache size"""
        cache = InMemoryCache(ttl_seconds=60)

        assert cache.size == 0

        cache.set(sample_rate_result)

        assert cache.size == 1

    def test_invalidate(self, sample_rate_result):
        """Should remove specific entry"""
        cache = InMemoryCache(ttl_seconds=60)
        cache.set(sample_rate_result)

        cache.invalidate(
            sample_rate_result.pair,
            sample_rate_result.rate_date
        )
        result = cache.get(
            sample_rate_result.pair,
            sample_rate_result.rate_date
        )

        assert result is None
        assert cache.size == 0

    def test_invalidate_nonexistent(self):
        """Should not error when invalidating nonexistent entry"""
        cache = InMemoryCache(ttl_seconds=60)

        # Should not raise
        cache.invalidate(CurrencyPair("USD", "EUR"), date(2024, 1, 15))

    def test_clear(self, sample_rate_result):
        """Should clear all entries"""
        cache = InMemoryCache(ttl_seconds=60)
        cache.set(sample_rate_result)

        cache.clear()

        assert cache.size == 0

    def test_multiple_entries(self):
        """Should handle multiple distinct entries"""
        cache = InMemoryCache(ttl_seconds=60)

        result1 = ExchangeRateResult(
            pair=CurrencyPair("USD", "EUR"),
            rate=0.85,
            rate_date=date(2024, 1, 15),
            source=RateSource.EXCHANGERATE_API,
            confidence=Confidence.HIGH,
            fetched_at=datetime.utcnow()
        )

        result2 = ExchangeRateResult(
            pair=CurrencyPair("USD", "CZK"),
            rate=22.5,
            rate_date=date(2024, 1, 15),
            source=RateSource.EXCHANGERATE_API,
            confidence=Confidence.HIGH,
            fetched_at=datetime.utcnow()
        )

        cache.set(result1)
        cache.set(result2)

        assert cache.size == 2

        retrieved1 = cache.get(result1.pair, result1.rate_date)
        retrieved2 = cache.get(result2.pair, result2.rate_date)

        assert retrieved1.rate == 0.85
        assert retrieved2.rate == 22.5


class TestDatabaseCache:
    """Tests for database cache"""

    def test_get_from_populated_db(self, populated_db):
        """Should retrieve rate from database"""
        cache = DatabaseCache()

        result = cache.get(
            CurrencyPair("USD", "EUR"),
            date(2024, 1, 15),
            populated_db
        )

        assert result is not None
        assert result.rate == 0.85
        assert result.source == RateSource.DATABASE_CACHE

    def test_get_cache_miss(self, test_db):
        """Should return None for missing entry"""
        cache = DatabaseCache()

        result = cache.get(
            CurrencyPair("USD", "EUR"),
            date(2020, 1, 1),
            test_db
        )

        assert result is None

    def test_set_new_rate(self, test_db, sample_rate_result):
        """Should store new rate in database"""
        cache = DatabaseCache()

        cache.set(sample_rate_result, test_db)
        test_db.commit()

        result = cache.get(
            sample_rate_result.pair,
            sample_rate_result.rate_date,
            test_db
        )

        assert result is not None
        assert result.rate == sample_rate_result.rate

    def test_set_updates_existing(self, populated_db):
        """Should update existing rate in database"""
        cache = DatabaseCache()

        # Update existing rate
        updated_result = ExchangeRateResult(
            pair=CurrencyPair("USD", "EUR"),
            rate=0.90,  # Different rate
            rate_date=date(2024, 1, 15),
            source=RateSource.EXCHANGERATE_API,
            confidence=Confidence.HIGH,
            fetched_at=datetime.utcnow()
        )

        cache.set(updated_result, populated_db)
        populated_db.commit()

        result = cache.get(
            CurrencyPair("USD", "EUR"),
            date(2024, 1, 15),
            populated_db
        )

        assert result.rate == 0.90

    def test_get_last_known_rate(self, populated_db):
        """Should find historical fallback rate"""
        cache = DatabaseCache()

        result = cache.get_last_known_rate(
            CurrencyPair("USD", "EUR"),
            date(2024, 1, 20),  # After the cached date
            populated_db
        )

        assert result is not None
        assert result.rate == 0.85
        assert result.source == RateSource.HISTORICAL_FALLBACK
        assert result.is_stale is True
        assert result.staleness_days == 5

    def test_get_last_known_rate_not_found(self, test_db):
        """Should return None when no historical rate exists"""
        cache = DatabaseCache()

        result = cache.get_last_known_rate(
            CurrencyPair("USD", "EUR"),
            date(2020, 1, 1),
            test_db
        )

        assert result is None

    def test_staleness_confidence_medium(self, populated_db):
        """Should return medium confidence for rates <= 30 days old"""
        cache = DatabaseCache()

        result = cache.get_last_known_rate(
            CurrencyPair("USD", "EUR"),
            date(2024, 1, 25),  # 10 days after cached rate
            populated_db
        )

        assert result.confidence == Confidence.MEDIUM
        assert result.needs_review is False

    def test_staleness_confidence_low(self, populated_db):
        """Should return low confidence for rates > 30 days old"""
        cache = DatabaseCache()

        result = cache.get_last_known_rate(
            CurrencyPair("USD", "EUR"),
            date(2024, 3, 15),  # 60 days after cached rate
            populated_db
        )

        assert result.confidence == Confidence.LOW

    def test_staleness_needs_review(self, populated_db):
        """Should flag rates > 90 days old for review"""
        cache = DatabaseCache()

        result = cache.get_last_known_rate(
            CurrencyPair("USD", "EUR"),
            date(2024, 5, 15),  # ~120 days after cached rate
            populated_db
        )

        assert result.needs_review is True
        assert "days old" in result.review_reason


class TestExchangeRateCache:
    """Tests for unified cache"""

    def test_memory_cache_hit(self, test_db, sample_rate_result):
        """Should return from memory cache first"""
        cache = ExchangeRateCache(memory_ttl_seconds=60)

        # Manually populate memory cache
        cache._memory_cache.set(sample_rate_result)

        result = cache.get(
            sample_rate_result.pair,
            sample_rate_result.rate_date,
            test_db
        )

        assert result is not None
        assert result.source == RateSource.MEMORY_CACHE

    def test_database_cache_populates_memory(self, populated_db):
        """Should populate memory cache from database hit"""
        cache = ExchangeRateCache(memory_ttl_seconds=60)

        # First call should hit database
        result1 = cache.get(
            CurrencyPair("USD", "EUR"),
            date(2024, 1, 15),
            populated_db
        )

        assert result1.source == RateSource.DATABASE_CACHE

        # Second call should hit memory cache
        result2 = cache.get(
            CurrencyPair("USD", "EUR"),
            date(2024, 1, 15),
            populated_db
        )

        assert result2.source == RateSource.MEMORY_CACHE

    def test_set_populates_both_caches(self, test_db, sample_rate_result):
        """Should store in both memory and database"""
        cache = ExchangeRateCache(memory_ttl_seconds=60)

        cache.set(sample_rate_result, test_db)
        test_db.commit()

        # Check memory cache
        memory_result = cache._memory_cache.get(
            sample_rate_result.pair,
            sample_rate_result.rate_date
        )
        assert memory_result is not None

        # Check database cache
        db_result = cache._db_cache.get(
            sample_rate_result.pair,
            sample_rate_result.rate_date,
            test_db
        )
        assert db_result is not None

    def test_invalidate_clears_memory_only(self, test_db, sample_rate_result):
        """Invalidate should only clear memory cache"""
        cache = ExchangeRateCache(memory_ttl_seconds=60)

        cache.set(sample_rate_result, test_db)
        test_db.commit()

        cache.invalidate(
            sample_rate_result.pair,
            sample_rate_result.rate_date
        )

        # Memory cache should be empty
        assert cache._memory_cache.size == 0

        # Database should still have the rate
        db_result = cache._db_cache.get(
            sample_rate_result.pair,
            sample_rate_result.rate_date,
            test_db
        )
        assert db_result is not None

    def test_clear_memory_cache(self, test_db, sample_rate_result):
        """Should clear only memory cache"""
        cache = ExchangeRateCache(memory_ttl_seconds=60)

        cache.set(sample_rate_result, test_db)
        test_db.commit()

        cache.clear_memory_cache()

        assert cache._memory_cache.size == 0

    def test_historical_fallback(self, populated_db):
        """Should return historical fallback"""
        cache = ExchangeRateCache(memory_ttl_seconds=60)

        result = cache.get_historical_fallback(
            CurrencyPair("USD", "EUR"),
            date(2024, 1, 20),
            populated_db
        )

        assert result is not None
        assert result.source == RateSource.HISTORICAL_FALLBACK
