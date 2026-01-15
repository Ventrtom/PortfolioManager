"""
Main exchange rate service.
"""
import logging
from datetime import date, datetime
from typing import List, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from .providers.base import ExchangeRateProvider
from .providers.frankfurter import FrankfurterProvider
from .providers.exchangerate_host import ExchangeRateHostProvider
from .cache import ExchangeRateCache
from .config import ExchangeRateConfig
from .types import (
    ExchangeRateResult, CurrencyPair, RateSource, Confidence,
    MultiCurrencyResult, ConversionResult
)
from .errors import (
    InvalidCurrencyError, RateNotFoundError, NetworkError, RateLimitError
)


class ExchangeRateService:
    """
    Exchange rate service with simple 2-tier provider fallback and caching.

    Resolution order:
    1. In-memory cache
    2. Database cache
    3. Primary provider (Frankfurter - ECB data, free, historical from 1999)
    4. Fallback provider (fawazahmed0 - free, data from 2025+)
    5. Historical fallback (last known rate)
    """

    def __init__(
        self,
        config: Optional[ExchangeRateConfig] = None,
        primary_provider: Optional[ExchangeRateProvider] = None,
        fallback_provider: Optional[ExchangeRateProvider] = None,
        cache: Optional[ExchangeRateCache] = None
    ):
        """
        Initialize service with optional dependency injection.

        Args:
            config: Service configuration (defaults to environment)
            primary_provider: Primary rate provider (defaults to Frankfurter)
            fallback_provider: Fallback provider (defaults to fawazahmed0)
            cache: Cache layer (defaults to memory + database cache)
        """
        self._config = config or ExchangeRateConfig.from_environment()
        self._cache = cache or ExchangeRateCache(
            memory_ttl_seconds=self._config.memory_cache_ttl_seconds
        )

        # Initialize providers
        # Primary: Frankfurter (ECB data, free, no API key, historical from 1999)
        # Fallback: fawazahmed0 (free, no API key, data from 2025+)
        self._primary_provider = primary_provider or FrankfurterProvider()
        self._fallback_provider = fallback_provider or ExchangeRateHostProvider()

        self._logger = logging.getLogger("exchange_rate.service")

    def _validate_currency(self, currency: str) -> str:
        """Validate and normalize currency code"""
        currency = currency.upper()
        if currency not in self._config.supported_currencies:
            raise InvalidCurrencyError(
                currency=currency,
                supported=list(self._config.supported_currencies)
            )
        return currency

    def get_rate(
        self,
        base: str,
        target: str,
        rate_date: date,
        db: Session
    ) -> float:
        """
        Get exchange rate for a currency pair on a specific date.

        Args:
            base: Base currency (USD, EUR, CZK)
            target: Target currency (USD, EUR, CZK)
            rate_date: Date for exchange rate
            db: Database session

        Returns:
            Exchange rate as float

        Raises:
            InvalidCurrencyError: If currency not supported
            RateNotFoundError: If rate cannot be found
        """
        result = self.get_rate_with_metadata(base, target, rate_date, db)
        return result.rate

    def get_rate_with_metadata(
        self,
        base: str,
        target: str,
        rate_date: date,
        db: Session
    ) -> ExchangeRateResult:
        """
        Get exchange rate with full metadata.

        Args:
            base: Base currency (USD, EUR, CZK)
            target: Target currency (USD, EUR, CZK)
            rate_date: Date for exchange rate
            db: Database session

        Returns:
            ExchangeRateResult with rate and metadata

        Raises:
            InvalidCurrencyError: If currency not supported
            RateNotFoundError: If rate cannot be found
        """
        # Validate currencies
        base = self._validate_currency(base)
        target = self._validate_currency(target)

        pair = CurrencyPair(base, target)

        # Handle identity case
        if pair.is_identity:
            return ExchangeRateResult(
                pair=pair,
                rate=1.0,
                rate_date=rate_date,
                source=RateSource.IDENTITY,
                confidence=Confidence.HIGH,
                fetched_at=datetime.utcnow()
            )

        # Try cache first
        cached = self._cache.get(pair, rate_date, db)
        if cached:
            self._logger.debug(f"Cache hit for {pair} on {rate_date}")
            return cached

        # Try providers
        result = self._fetch_from_providers(pair, rate_date)

        if result:
            # Store in cache
            self._cache.set(result, db)
            db.commit()
            return result

        # Try historical fallback
        result = self._cache.get_historical_fallback(pair, rate_date, db)

        if result:
            self._logger.warning(
                f"Using historical fallback for {pair} on {rate_date}: "
                f"rate from {result.rate_date} ({result.staleness_days} days old)"
            )
            return result

        # All methods failed
        raise RateNotFoundError(
            base=pair.base,
            target=pair.target,
            rate_date=rate_date.isoformat()
        )

    def _fetch_from_providers(
        self,
        pair: CurrencyPair,
        rate_date: date
    ) -> Optional[ExchangeRateResult]:
        """Try to fetch rate from providers"""
        providers = [self._primary_provider, self._fallback_provider]

        for provider in providers:
            try:
                self._logger.debug(
                    f"Trying {provider.name} for {pair} on {rate_date}"
                )
                result = provider.get_rate(pair, rate_date)

                if result:
                    self._logger.info(
                        f"Successfully fetched {pair} on {rate_date} "
                        f"from {provider.name}: {result.rate}"
                    )
                    return result

            except RateLimitError as e:
                self._logger.warning(f"Rate limit hit for {provider.name}")
                continue
            except NetworkError as e:
                self._logger.warning(
                    f"Network error for {provider.name}: {e.message}"
                )
                continue
            except Exception as e:
                self._logger.error(
                    f"Unexpected error for {provider.name}: {e}"
                )
                continue

        self._logger.warning(f"All providers failed for {pair} on {rate_date}")
        return None

    def convert_amount(
        self,
        amount: float,
        from_currency: str,
        to_currency: str,
        rate_date: date,
        db: Session
    ) -> float:
        """
        Convert amount from one currency to another.

        Args:
            amount: Amount to convert
            from_currency: Source currency
            to_currency: Target currency
            rate_date: Date for exchange rate
            db: Database session

        Returns:
            Converted amount
        """
        rate = self.get_rate(from_currency, to_currency, rate_date, db)
        return round(amount * rate, 2)

    def convert_amount_with_metadata(
        self,
        amount: float,
        from_currency: str,
        to_currency: str,
        rate_date: date,
        db: Session
    ) -> ConversionResult:
        """
        Convert amount with full conversion details.

        Args:
            amount: Amount to convert
            from_currency: Source currency
            to_currency: Target currency
            rate_date: Date for exchange rate
            db: Database session

        Returns:
            ConversionResult with amount and metadata
        """
        rate_result = self.get_rate_with_metadata(
            from_currency, to_currency, rate_date, db
        )
        converted = round(amount * rate_result.rate, 2)

        return ConversionResult(
            original_amount=amount,
            original_currency=from_currency.upper(),
            converted_amount=converted,
            target_currency=to_currency.upper(),
            rate_used=rate_result
        )

    def get_all_currency_amounts(
        self,
        amount: float,
        source_currency: str,
        rate_date: date,
        db: Session
    ) -> MultiCurrencyResult:
        """
        Convert amount to all supported currencies.

        Args:
            amount: Amount in source currency
            source_currency: Source currency
            rate_date: Date for exchange rates
            db: Database session

        Returns:
            MultiCurrencyResult with all currency amounts
        """
        source_currency = self._validate_currency(source_currency)

        result = MultiCurrencyResult(
            usd=None,
            eur=None,
            czk=None,
            source_currency=source_currency,
            source_amount=amount
        )

        # Set source currency amount
        setattr(result, source_currency.lower(), round(amount, 2))

        # Convert to other currencies
        for target in self._config.supported_currencies:
            if target == source_currency:
                continue

            try:
                rate_result = self.get_rate_with_metadata(
                    source_currency, target, rate_date, db
                )
                converted = round(amount * rate_result.rate, 2)
                setattr(result, target.lower(), converted)
                result.rates_used[target] = rate_result

                if rate_result.is_stale:
                    result.warnings.append(
                        f"{source_currency}/{target} rate is "
                        f"{rate_result.staleness_days} days old"
                    )

            except RateNotFoundError:
                result.failed_conversions.append(f"{source_currency}/{target}")
                result.warnings.append(
                    f"Could not get rate for {source_currency}/{target} "
                    f"on {rate_date}"
                )
            except Exception as e:
                result.failed_conversions.append(f"{source_currency}/{target}")
                result.warnings.append(f"Error converting to {target}: {str(e)}")

        return result

    def batch_get_rates(
        self,
        pairs: List[Tuple[str, str, date]],
        db: Session
    ) -> Dict[str, ExchangeRateResult]:
        """
        Get rates for multiple currency pairs efficiently.

        Args:
            pairs: List of (base, target, date) tuples
            db: Database session

        Returns:
            Dict mapping "BASE/TARGET/DATE" to ExchangeRateResult
        """
        results = {}

        for base, target, rate_date in pairs:
            key = f"{base.upper()}/{target.upper()}/{rate_date.isoformat()}"

            try:
                result = self.get_rate_with_metadata(base, target, rate_date, db)
                results[key] = result
            except Exception as e:
                self._logger.warning(f"Failed to get rate for {key}: {e}")
                # Continue with other pairs

        return results

    def refresh_cache(
        self,
        pairs: List[Tuple[str, str, date]],
        db: Session
    ) -> Dict[str, bool]:
        """
        Force refresh rates from providers (bypass cache).

        Args:
            pairs: List of (base, target, date) tuples
            db: Database session

        Returns:
            Dict mapping pair key to success status
        """
        results = {}

        for base, target, rate_date in pairs:
            base = base.upper()
            target = target.upper()
            pair = CurrencyPair(base, target)
            key = f"{base}/{target}/{rate_date.isoformat()}"

            # Invalidate cache
            self._cache.invalidate(pair, rate_date)

            # Fetch fresh from providers
            result = self._fetch_from_providers(pair, rate_date)

            if result:
                self._cache.set(result, db)
                results[key] = True
            else:
                results[key] = False

        db.commit()
        return results

    def health_check(self) -> Dict[str, bool]:
        """
        Check health of all providers.

        Returns:
            Dict mapping provider name to health status
        """
        return {
            self._primary_provider.name: self._primary_provider.health_check(),
            self._fallback_provider.name: self._fallback_provider.health_check(),
        }

    def get_provider_stats(self) -> Dict[str, dict]:
        """
        Get statistics for all providers.

        Returns:
            Dict mapping provider name to stats dict
        """
        return {
            self._primary_provider.name: {
                "requests_made": self._primary_provider.stats.requests_made,
                "successful_requests": (
                    self._primary_provider.stats.successful_requests
                ),
                "failed_requests": self._primary_provider.stats.failed_requests,
                "rate_limit_hits": self._primary_provider.stats.rate_limit_hits,
                "avg_response_time_ms": (
                    self._primary_provider.stats.avg_response_time_ms
                ),
                "is_available": self._primary_provider.stats.is_available,
            },
            self._fallback_provider.name: {
                "requests_made": self._fallback_provider.stats.requests_made,
                "successful_requests": (
                    self._fallback_provider.stats.successful_requests
                ),
                "failed_requests": self._fallback_provider.stats.failed_requests,
                "rate_limit_hits": self._fallback_provider.stats.rate_limit_hits,
                "avg_response_time_ms": (
                    self._fallback_provider.stats.avg_response_time_ms
                ),
                "is_available": self._fallback_provider.stats.is_available,
            },
        }
