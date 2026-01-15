"""
Caching layer for exchange rates.
"""
from datetime import date, datetime, timedelta
from typing import Optional, Dict, Tuple
from threading import RLock
import logging

from sqlalchemy.orm import Session

from models.database import ExchangeRate
from .types import ExchangeRateResult, CurrencyPair, RateSource, Confidence


class InMemoryCache:
    """Thread-safe in-memory cache for exchange rates"""

    def __init__(self, ttl_seconds: int = 3600):
        self._cache: Dict[str, Tuple[ExchangeRateResult, datetime]] = {}
        self._ttl = timedelta(seconds=ttl_seconds)
        self._lock = RLock()
        self._logger = logging.getLogger("exchange_rate.cache.memory")

    def _make_key(self, pair: CurrencyPair, rate_date: date) -> str:
        return f"{pair.base}:{pair.target}:{rate_date.isoformat()}"

    def get(
        self,
        pair: CurrencyPair,
        rate_date: date
    ) -> Optional[ExchangeRateResult]:
        """Get rate from cache if not expired"""
        key = self._make_key(pair, rate_date)

        with self._lock:
            if key not in self._cache:
                return None

            result, cached_at = self._cache[key]

            if datetime.utcnow() - cached_at > self._ttl:
                del self._cache[key]
                return None

            # Return with updated source to indicate memory cache
            return ExchangeRateResult(
                pair=result.pair,
                rate=result.rate,
                rate_date=result.rate_date,
                source=RateSource.MEMORY_CACHE,
                confidence=result.confidence,
                fetched_at=result.fetched_at,
                is_stale=result.is_stale,
                staleness_days=result.staleness_days,
                needs_review=result.needs_review,
                review_reason=result.review_reason
            )

    def set(self, result: ExchangeRateResult):
        """Store rate in cache"""
        key = self._make_key(result.pair, result.rate_date)

        with self._lock:
            self._cache[key] = (result, datetime.utcnow())

    def invalidate(self, pair: CurrencyPair, rate_date: date):
        """Remove specific entry from cache"""
        key = self._make_key(pair, rate_date)

        with self._lock:
            self._cache.pop(key, None)

    def clear(self):
        """Clear entire cache"""
        with self._lock:
            self._cache.clear()

    @property
    def size(self) -> int:
        """Get number of cached entries"""
        with self._lock:
            return len(self._cache)


class DatabaseCache:
    """Database cache layer for exchange rates"""

    def __init__(self):
        self._logger = logging.getLogger("exchange_rate.cache.database")

    def get(
        self,
        pair: CurrencyPair,
        rate_date: date,
        db: Session
    ) -> Optional[ExchangeRateResult]:
        """Get rate from database cache"""
        cached = db.query(ExchangeRate).filter(
            ExchangeRate.base_currency == pair.base,
            ExchangeRate.target_currency == pair.target,
            ExchangeRate.rate_date == rate_date
        ).first()

        if not cached:
            return None

        # Parse confidence from stored string
        try:
            confidence = Confidence(cached.confidence) if cached.confidence else Confidence.HIGH
        except ValueError:
            confidence = Confidence.HIGH

        return ExchangeRateResult(
            pair=pair,
            rate=cached.rate,
            rate_date=cached.rate_date,
            source=RateSource.DATABASE_CACHE,
            confidence=confidence,
            fetched_at=cached.fetched_at,
            needs_review=cached.needs_manual_review or False,
            review_reason=cached.manual_review_reason
        )

    def set(
        self,
        result: ExchangeRateResult,
        db: Session
    ):
        """Store rate in database cache"""
        # Check if exists
        existing = db.query(ExchangeRate).filter(
            ExchangeRate.base_currency == result.pair.base,
            ExchangeRate.target_currency == result.pair.target,
            ExchangeRate.rate_date == result.rate_date
        ).first()

        if existing:
            # Update existing
            existing.rate = result.rate
            existing.source = result.source.value
            existing.confidence = result.confidence.value
            existing.fetched_at = result.fetched_at
            existing.needs_manual_review = result.needs_review
            existing.manual_review_reason = result.review_reason
            existing.ai_used = False
        else:
            # Create new
            new_rate = ExchangeRate(
                base_currency=result.pair.base,
                target_currency=result.pair.target,
                rate_date=result.rate_date,
                rate=result.rate,
                source=result.source.value,
                confidence=result.confidence.value,
                fetched_at=result.fetched_at,
                needs_manual_review=result.needs_review,
                manual_review_reason=result.review_reason,
                ai_used=False
            )
            db.add(new_rate)

        db.flush()

    def get_last_known_rate(
        self,
        pair: CurrencyPair,
        before_date: date,
        db: Session
    ) -> Optional[ExchangeRateResult]:
        """Get most recent rate before a given date (for historical fallback)"""
        cached = db.query(ExchangeRate).filter(
            ExchangeRate.base_currency == pair.base,
            ExchangeRate.target_currency == pair.target,
            ExchangeRate.rate_date < before_date
        ).order_by(ExchangeRate.rate_date.desc()).first()

        if not cached:
            return None

        staleness_days = (before_date - cached.rate_date).days

        # Determine confidence based on staleness
        if staleness_days <= 30:
            confidence = Confidence.MEDIUM
        else:
            confidence = Confidence.LOW

        return ExchangeRateResult(
            pair=pair,
            rate=cached.rate,
            rate_date=cached.rate_date,
            source=RateSource.HISTORICAL_FALLBACK,
            confidence=confidence,
            fetched_at=cached.fetched_at,
            is_stale=True,
            staleness_days=staleness_days,
            needs_review=staleness_days > 90,
            review_reason=(
                f"Rate is {staleness_days} days old"
                if staleness_days > 90 else None
            )
        )


class ExchangeRateCache:
    """Unified cache combining in-memory and database layers"""

    def __init__(self, memory_ttl_seconds: int = 3600):
        self._memory_cache = InMemoryCache(ttl_seconds=memory_ttl_seconds)
        self._db_cache = DatabaseCache()
        self._logger = logging.getLogger("exchange_rate.cache")

    def get(
        self,
        pair: CurrencyPair,
        rate_date: date,
        db: Session
    ) -> Optional[ExchangeRateResult]:
        """Get rate from cache (memory first, then database)"""
        # Try memory cache first
        result = self._memory_cache.get(pair, rate_date)
        if result:
            self._logger.debug(f"Memory cache hit: {pair} on {rate_date}")
            return result

        # Try database cache
        result = self._db_cache.get(pair, rate_date, db)
        if result:
            self._logger.debug(f"Database cache hit: {pair} on {rate_date}")
            # Populate memory cache
            self._memory_cache.set(result)
            return result

        return None

    def set(
        self,
        result: ExchangeRateResult,
        db: Session
    ):
        """Store rate in both caches"""
        self._memory_cache.set(result)
        self._db_cache.set(result, db)

    def get_historical_fallback(
        self,
        pair: CurrencyPair,
        before_date: date,
        db: Session
    ) -> Optional[ExchangeRateResult]:
        """Get historical fallback rate"""
        return self._db_cache.get_last_known_rate(pair, before_date, db)

    def invalidate(self, pair: CurrencyPair, rate_date: date):
        """Invalidate memory cache entry"""
        self._memory_cache.invalidate(pair, rate_date)

    def clear_memory_cache(self):
        """Clear in-memory cache"""
        self._memory_cache.clear()
