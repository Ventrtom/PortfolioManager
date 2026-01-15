"""
Exchange Rate Service - Compatibility Facade

This module provides backward compatibility with the old API while
delegating to the new exchange_rate package implementation.

For new code, use:
    from services.exchange_rate import ExchangeRateService

This facade maintains the old static method interface for existing code.
"""
import logging
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from models.database import ExchangeRate, Transaction
from services.exchange_rate import (
    ExchangeRateService as NewExchangeRateService,
    ExchangeRateConfig,
    RateNotFoundError,
    InvalidCurrencyError,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ExchangeRateService:
    """
    Exchange rate service with backward-compatible static method API.
    Delegates to the new services.exchange_rate.ExchangeRateService.
    """

    SUPPORTED_CURRENCIES = ['USD', 'EUR', 'CZK']

    # Singleton instance of new service
    _instance: Optional[NewExchangeRateService] = None

    @classmethod
    def _get_service(cls) -> NewExchangeRateService:
        """Get or create the singleton service instance"""
        if cls._instance is None:
            config = ExchangeRateConfig.from_environment()
            cls._instance = NewExchangeRateService(config=config)
        return cls._instance

    @staticmethod
    def get_exchange_rate(
        base_currency: str,
        target_currency: str,
        rate_date: date,
        db: Session
    ) -> Optional[float]:
        """
        Get exchange rate for a specific date.

        Args:
            base_currency: Source currency (USD, EUR, CZK)
            target_currency: Target currency (USD, EUR, CZK)
            rate_date: Date for exchange rate
            db: Database session

        Returns:
            Exchange rate as float, or None if unavailable
        """
        try:
            service = ExchangeRateService._get_service()
            return service.get_rate(base_currency, target_currency, rate_date, db)
        except (RateNotFoundError, InvalidCurrencyError):
            return None
        except Exception as e:
            logger.error(f"Error getting exchange rate: {e}")
            return None

    @staticmethod
    def get_exchange_rate_intelligent(
        base_currency: str,
        target_currency: str,
        rate_date: date,
        db: Session
    ) -> Optional[Dict]:
        """
        Get exchange rate with full metadata.
        Uses simplified 2-tier provider fallback (no AI tier).

        Args:
            base_currency: Source currency (USD, EUR, CZK)
            target_currency: Target currency (USD, EUR, CZK)
            rate_date: Date for exchange rate
            db: Database session

        Returns:
            Dict with rate info or None:
            {
                'rate': float,
                'source': str,
                'confidence': str,
                'ai_used': bool,
                'needs_manual_review': bool,
                'ai_sources': List[str],
                'tier': int
            }
        """
        try:
            service = ExchangeRateService._get_service()
            result = service.get_rate_with_metadata(
                base_currency, target_currency, rate_date, db
            )

            # Map source to tier for backward compatibility
            source_to_tier = {
                'identity': 0,
                'memory_cache': 1,
                'database_cache': 1,
                'exchangerate-api.io': 2,
                'exchangerate.host': 2,
                'historical': 4,
            }

            return {
                'rate': result.rate,
                'source': result.source.value,
                'confidence': result.confidence.value,
                'ai_used': False,  # New service doesn't use AI
                'needs_manual_review': result.needs_review,
                'ai_sources': [],
                'tier': source_to_tier.get(result.source.value, 2)
            }

        except (RateNotFoundError, InvalidCurrencyError):
            return None
        except Exception as e:
            logger.error(f"Error in intelligent rate resolution: {e}")
            return None

    @staticmethod
    def convert_amount(
        amount: float,
        from_currency: str,
        to_currency: str,
        rate_date: date,
        db: Session
    ) -> Optional[float]:
        """
        Convert amount from one currency to another.

        Args:
            amount: Amount to convert
            from_currency: Source currency
            to_currency: Target currency
            rate_date: Date for exchange rate
            db: Database session

        Returns:
            Converted amount or None if rate unavailable
        """
        try:
            service = ExchangeRateService._get_service()
            return service.convert_amount(
                amount, from_currency, to_currency, rate_date, db
            )
        except (RateNotFoundError, InvalidCurrencyError):
            return None
        except Exception as e:
            logger.error(f"Error converting amount: {e}")
            return None

    @staticmethod
    def get_all_currency_amounts(
        amount: float,
        transaction_currency: str,
        rate_date: date,
        db: Session
    ) -> Dict[str, float]:
        """
        Convert a transaction amount to all three currencies.

        Args:
            amount: Transaction amount in transaction_currency
            transaction_currency: Currency of the transaction
            rate_date: Date of transaction
            db: Database session

        Returns:
            Dict with keys 'usd', 'eur', 'czk'

        Raises:
            Exception if critical rates are unavailable
        """
        service = ExchangeRateService._get_service()
        result = service.get_all_currency_amounts(
            amount, transaction_currency, rate_date, db
        )

        # Check for failed conversions
        if result.failed_conversions:
            raise Exception(
                f"Unable to fetch exchange rates for: "
                f"{', '.join(result.failed_conversions)}"
            )

        return {
            'usd': result.usd,
            'eur': result.eur,
            'czk': result.czk,
        }

    @staticmethod
    def get_all_currency_amounts_intelligent(
        amount: float,
        transaction_currency: str,
        rate_date: date,
        db: Session
    ) -> Dict:
        """
        Convert amount to all currencies with metadata.

        Args:
            amount: Transaction amount
            transaction_currency: Source currency
            rate_date: Date for rates
            db: Database session

        Returns:
            Dict with amounts and metadata
        """
        service = ExchangeRateService._get_service()
        result = service.get_all_currency_amounts(
            amount, transaction_currency, rate_date, db
        )

        # Convert to legacy format
        sources = {}
        for currency, rate_result in result.rates_used.items():
            sources[currency.lower()] = rate_result.source.value
        sources[transaction_currency.lower()] = 'identity'

        return {
            'usd': result.usd,
            'eur': result.eur,
            'czk': result.czk,
            'metadata': {
                'sources': sources,
                'ai_used': False,  # New service doesn't use AI
                'needs_manual_review': result.needs_review,
                'warnings': result.warnings,
                'failed_conversions': [
                    {'base': transaction_currency, 'target': fc.split('/')[1]}
                    for fc in result.failed_conversions
                ] if result.failed_conversions else []
            }
        }

    @staticmethod
    def get_last_known_rate(
        base_currency: str,
        target_currency: str,
        before_date: date,
        db: Session
    ) -> Optional[Tuple[date, float]]:
        """
        Get the most recent exchange rate before a given date.

        Args:
            base_currency: Source currency
            target_currency: Target currency
            before_date: Find rate before this date
            db: Database session

        Returns:
            Tuple of (rate_date, rate) or None
        """
        if base_currency == target_currency:
            return (before_date, 1.0)

        last_rate = db.query(ExchangeRate).filter(
            ExchangeRate.base_currency == base_currency.upper(),
            ExchangeRate.target_currency == target_currency.upper(),
            ExchangeRate.rate_date < before_date
        ).order_by(ExchangeRate.rate_date.desc()).first()

        if last_rate:
            return (last_rate.rate_date, last_rate.rate)

        return None

    @staticmethod
    def batch_fetch_rates(unique_dates: List[date], db: Session) -> int:
        """
        Fetch exchange rates for multiple dates.

        Args:
            unique_dates: List of dates to fetch rates for
            db: Database session

        Returns:
            Count of dates successfully fetched
        """
        import time

        service = ExchangeRateService._get_service()
        success_count = 0

        for i, rate_date in enumerate(unique_dates, 1):
            print(f"Fetching rates for {rate_date} ({i}/{len(unique_dates)})...")

            try:
                # Check if rates already exist
                existing_count = db.query(ExchangeRate).filter(
                    ExchangeRate.rate_date == rate_date
                ).count()

                if existing_count >= 9:
                    print(f"  Rates already cached for {rate_date}")
                    success_count += 1
                    continue

                # Build pairs to refresh
                pairs = []
                for base in ['USD', 'EUR', 'CZK']:
                    for target in ['USD', 'EUR', 'CZK']:
                        if base != target:
                            pairs.append((base, target, rate_date))

                # Fetch rates
                results = service.batch_get_rates(pairs, db)

                if results:
                    print(f"  Successfully fetched rates for {rate_date}")
                    success_count += 1
                else:
                    print(f"  Failed to fetch rates for {rate_date}")

                # Rate limiting
                if i < len(unique_dates):
                    time.sleep(1)

            except Exception as e:
                print(f"  Error fetching rates for {rate_date}: {e}")
                continue

        return success_count


class CurrencyNormalizer:
    """Normalize all portfolio calculations to CZK base currency"""

    BASE_CURRENCY = 'CZK'

    @staticmethod
    def to_base_currency(
        amount: float,
        from_currency: str,
        amount_date: date,
        db: Session
    ) -> Optional[float]:
        """
        Convert amount to base currency (CZK).

        Args:
            amount: Amount to convert
            from_currency: Source currency
            amount_date: Date for exchange rate lookup
            db: Database session

        Returns:
            Amount in CZK, or None if conversion fails
        """
        if not amount or amount == 0:
            return 0.0

        from_currency = from_currency.upper()

        if from_currency == CurrencyNormalizer.BASE_CURRENCY:
            return amount

        try:
            service = ExchangeRateService._get_service()
            return service.convert_amount(
                amount, from_currency, 'CZK', amount_date, db
            )
        except Exception as e:
            logger.warning(f"Failed to convert {amount} {from_currency} to CZK: {e}")

            # Try fallback
            last_rate = ExchangeRateService.get_last_known_rate(
                from_currency, 'CZK', amount_date, db
            )

            if last_rate:
                rate_date, rate_value = last_rate
                days_stale = (amount_date - rate_date).days
                logger.warning(
                    f"Using stale exchange rate ({days_stale} days old) for "
                    f"{from_currency}/CZK on {amount_date}"
                )
                return amount * rate_value

            logger.error(
                f"Failed to convert {amount} {from_currency} to CZK on {amount_date}"
            )
            return None

    @staticmethod
    def normalize_transaction(transaction: Transaction, db: Session) -> Dict:
        """
        Normalize transaction amounts to base currency (CZK).

        Args:
            transaction: Transaction object
            db: Database session

        Returns:
            Dict with normalized amount and metadata
        """
        txn_currency = (transaction.transaction_currency or 'CZK').upper()
        txn_amount = transaction.total_amount
        txn_date = transaction.transaction_date

        if txn_currency == 'CZK':
            return {
                'amount_czk': txn_amount,
                'exchange_rate_date': txn_date,
                'exchange_rate_staleness_days': 0,
                'conversion_warning': None
            }

        # Try exact date
        rate = ExchangeRateService.get_exchange_rate(
            txn_currency, 'CZK', txn_date, db
        )

        if rate:
            return {
                'amount_czk': txn_amount * rate,
                'exchange_rate_date': txn_date,
                'exchange_rate_staleness_days': 0,
                'conversion_warning': None
            }

        # Fallback to last known
        last_rate = ExchangeRateService.get_last_known_rate(
            txn_currency, 'CZK', txn_date, db
        )

        if last_rate:
            rate_date, rate_value = last_rate
            staleness = (txn_date - rate_date).days

            return {
                'amount_czk': txn_amount * rate_value,
                'exchange_rate_date': rate_date,
                'exchange_rate_staleness_days': staleness,
                'conversion_warning': (
                    f"Used exchange rate from {rate_date} "
                    f"({staleness} days before transaction)"
                )
            }

        raise ValueError(
            f"Cannot normalize transaction {transaction.id}: "
            f"No exchange rate available for {txn_currency}/CZK "
            f"on or before {txn_date}"
        )
