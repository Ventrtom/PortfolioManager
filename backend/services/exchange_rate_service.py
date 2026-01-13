import os
import requests
import time
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from models.database import ExchangeRate, Transaction
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ExchangeRateService:
    """Service for managing exchange rates and currency conversions"""

    # API configuration
    API_BASE_URL = "https://v6.exchangerate-api.io/v6"
    SUPPORTED_CURRENCIES = ['USD', 'EUR', 'CZK']

    # Failed API call cache (to avoid repeated failures)
    _failed_date_cache: Dict[str, float] = {}  # date_string -> timestamp
    _FAILED_CACHE_TIMEOUT = 300  # 5 minutes

    @staticmethod
    def _get_api_key() -> str:
        """Get API key from environment variable"""
        api_key = os.getenv('EXCHANGE_RATE_API_KEY')
        if not api_key:
            raise ValueError(
                "EXCHANGE_RATE_API_KEY not found in environment variables. "
                "Please add it to your .env file. "
                "Get your API key from: https://app.exchangerate-api.com/sign-up"
            )
        return api_key

    @staticmethod
    def _check_failed_cache(rate_date: date) -> bool:
        """Check if this date recently failed to fetch"""
        date_str = rate_date.isoformat()
        if date_str in ExchangeRateService._failed_date_cache:
            failed_time = ExchangeRateService._failed_date_cache[date_str]
            if time.time() - failed_time < ExchangeRateService._FAILED_CACHE_TIMEOUT:
                return True
            else:
                # Cache expired, remove it
                del ExchangeRateService._failed_date_cache[date_str]
        return False

    @staticmethod
    def _add_to_failed_cache(rate_date: date):
        """Mark this date as failed"""
        date_str = rate_date.isoformat()
        ExchangeRateService._failed_date_cache[date_str] = time.time()

    @staticmethod
    def get_exchange_rate(
        base_currency: str,
        target_currency: str,
        rate_date: date,
        db: Session
    ) -> Optional[float]:
        """
        Get exchange rate for a specific date
        Returns rate or None if unavailable

        Args:
            base_currency: Source currency (USD, EUR, CZK)
            target_currency: Target currency (USD, EUR, CZK)
            rate_date: Date for exchange rate
            db: Database session

        Returns:
            Exchange rate as float, or None if unavailable
        """
        # Same currency = 1.0
        if base_currency == target_currency:
            return 1.0

        # Check cache first
        cached_rate = db.query(ExchangeRate).filter(
            ExchangeRate.base_currency == base_currency,
            ExchangeRate.target_currency == target_currency,
            ExchangeRate.rate_date == rate_date
        ).first()

        if cached_rate:
            return cached_rate.rate

        # Check if we recently failed to fetch this date
        if ExchangeRateService._check_failed_cache(rate_date):
            return None

        # Try to fetch from API
        try:
            rates = ExchangeRateService.fetch_rates_for_date(rate_date, db)
            if base_currency in rates and target_currency in rates[base_currency]:
                return rates[base_currency][target_currency]
        except Exception as e:
            print(f"Failed to fetch exchange rate for {base_currency}/{target_currency} on {rate_date}: {e}")
            ExchangeRateService._add_to_failed_cache(rate_date)

        return None

    @staticmethod
    def fetch_rates_for_date(rate_date: date, db: Session) -> Dict[str, Dict[str, float]]:
        """
        Fetch all currency pairs for a specific date from API
        Caches all combinations in database

        Args:
            rate_date: Date to fetch rates for
            db: Database session

        Returns:
            Nested dict: {base: {target: rate}}
            Example: {'USD': {'EUR': 0.85, 'CZK': 22.5}, 'EUR': {'USD': 1.18, 'CZK': 26.5}, ...}
        """
        api_key = ExchangeRateService._get_api_key()
        all_rates = {}

        # Fetch rates for each base currency
        for base_currency in ExchangeRateService.SUPPORTED_CURRENCIES:
            # Check if we already have all rates for this base currency
            cached_rates = db.query(ExchangeRate).filter(
                ExchangeRate.base_currency == base_currency,
                ExchangeRate.rate_date == rate_date
            ).all()

            if len(cached_rates) >= len(ExchangeRateService.SUPPORTED_CURRENCIES):
                # Already cached
                all_rates[base_currency] = {
                    rate.target_currency: rate.rate
                    for rate in cached_rates
                }
                continue

            # Fetch from API with retry logic
            url = f"{ExchangeRateService.API_BASE_URL}/{api_key}/history/{base_currency}/{rate_date.year}/{rate_date.month:02d}/{rate_date.day:02d}"

            max_retries = 3
            retry_delays = [5, 15, 30]  # Exponential backoff

            for attempt in range(max_retries):
                try:
                    response = requests.get(url, timeout=10)
                    response.raise_for_status()
                    data = response.json()

                    if data.get('result') != 'success':
                        error_type = data.get('error-type', 'unknown')
                        raise Exception(f"API error: {error_type}")

                    conversion_rates = data.get('conversion_rates', {})

                    # Store rates for this base currency
                    base_rates = {}
                    for target_currency in ExchangeRateService.SUPPORTED_CURRENCIES:
                        if target_currency in conversion_rates:
                            rate_value = conversion_rates[target_currency]
                            base_rates[target_currency] = rate_value

                            # Cache in database
                            existing = db.query(ExchangeRate).filter(
                                ExchangeRate.base_currency == base_currency,
                                ExchangeRate.target_currency == target_currency,
                                ExchangeRate.rate_date == rate_date
                            ).first()

                            if not existing:
                                new_rate = ExchangeRate(
                                    base_currency=base_currency,
                                    target_currency=target_currency,
                                    rate_date=rate_date,
                                    rate=rate_value,
                                    source="exchangerate-api.io",
                                    fetched_at=datetime.utcnow()
                                )
                                db.add(new_rate)

                    db.commit()
                    all_rates[base_currency] = base_rates
                    break  # Success, exit retry loop

                except requests.exceptions.RequestException as e:
                    if attempt < max_retries - 1:
                        print(f"Attempt {attempt + 1} failed for {base_currency} on {rate_date}: {e}")
                        print(f"Retrying in {retry_delays[attempt]} seconds...")
                        time.sleep(retry_delays[attempt])
                    else:
                        print(f"All attempts failed for {base_currency} on {rate_date}: {e}")
                        ExchangeRateService._add_to_failed_cache(rate_date)
                        raise

        return all_rates

    @staticmethod
    def convert_amount(
        amount: float,
        from_currency: str,
        to_currency: str,
        rate_date: date,
        db: Session
    ) -> Optional[float]:
        """
        Convert amount from one currency to another

        Args:
            amount: Amount to convert
            from_currency: Source currency
            to_currency: Target currency
            rate_date: Date for exchange rate
            db: Database session

        Returns:
            Converted amount or None if rate unavailable
        """
        if from_currency == to_currency:
            return amount

        rate = ExchangeRateService.get_exchange_rate(from_currency, to_currency, rate_date, db)
        if rate is None:
            return None

        return round(amount * rate, 2)

    @staticmethod
    def get_all_currency_amounts(
        amount: float,
        transaction_currency: str,
        rate_date: date,
        db: Session
    ) -> Dict[str, float]:
        """
        Convert a transaction amount to all three currencies

        Args:
            amount: Transaction amount in transaction_currency
            transaction_currency: Currency of the transaction (USD, EUR, or CZK)
            rate_date: Date of transaction
            db: Database session

        Returns:
            Dict with keys 'usd', 'eur', 'czk' containing converted amounts

        Raises:
            Exception if critical rates are unavailable
        """
        transaction_currency = transaction_currency.upper()
        if transaction_currency not in ExchangeRateService.SUPPORTED_CURRENCIES:
            raise ValueError(f"Unsupported currency: {transaction_currency}")

        # Initialize result with None values
        result = {'usd': None, 'eur': None, 'czk': None}

        # Set the transaction currency amount directly
        result[transaction_currency.lower()] = round(amount, 2)

        # Convert to other currencies
        for target_currency in ExchangeRateService.SUPPORTED_CURRENCIES:
            if target_currency == transaction_currency:
                continue  # Already set

            converted = ExchangeRateService.convert_amount(
                amount,
                transaction_currency,
                target_currency,
                rate_date,
                db
            )

            if converted is None:
                # Try fallback: use last known rate
                last_rate = ExchangeRateService.get_last_known_rate(
                    transaction_currency,
                    target_currency,
                    rate_date,
                    db
                )
                if last_rate:
                    last_date, rate = last_rate
                    converted = round(amount * rate, 2)
                    print(f"Warning: Using last known rate from {last_date} for {transaction_currency}/{target_currency}")

            if converted is None:
                raise Exception(
                    f"Unable to fetch exchange rate for {transaction_currency}/{target_currency} on {rate_date}. "
                    f"Please check your EXCHANGE_RATE_API_KEY and try again."
                )

            result[target_currency.lower()] = converted

        return result

    @staticmethod
    def get_last_known_rate(
        base_currency: str,
        target_currency: str,
        before_date: date,
        db: Session
    ) -> Optional[Tuple[date, float]]:
        """
        Get the most recent exchange rate before a given date
        Used as fallback when exact date unavailable

        Args:
            base_currency: Source currency
            target_currency: Target currency
            before_date: Find rate before this date
            db: Database session

        Returns:
            Tuple of (rate_date, rate) or None if no rate found
        """
        if base_currency == target_currency:
            return (before_date, 1.0)

        last_rate = db.query(ExchangeRate).filter(
            ExchangeRate.base_currency == base_currency,
            ExchangeRate.target_currency == target_currency,
            ExchangeRate.rate_date < before_date
        ).order_by(ExchangeRate.rate_date.desc()).first()

        if last_rate:
            return (last_rate.rate_date, last_rate.rate)

        return None

    @staticmethod
    def batch_fetch_rates(unique_dates: List[date], db: Session) -> int:
        """
        Fetch exchange rates for multiple dates
        Used by migration and refresh operations

        Args:
            unique_dates: List of dates to fetch rates for
            db: Database session

        Returns:
            Count of dates successfully fetched
        """
        success_count = 0

        for i, rate_date in enumerate(unique_dates, 1):
            print(f"Fetching rates for {rate_date} ({i}/{len(unique_dates)})...")

            try:
                # Check if rates already exist for all currency pairs
                existing_count = db.query(ExchangeRate).filter(
                    ExchangeRate.rate_date == rate_date
                ).count()

                # We need 9 rates total: 3 base currencies × 3 target currencies
                if existing_count >= 9:
                    print(f"  Rates already cached for {rate_date}")
                    success_count += 1
                    continue

                # Fetch rates
                rates = ExchangeRateService.fetch_rates_for_date(rate_date, db)

                if rates:
                    print(f"  Successfully fetched rates for {rate_date}")
                    success_count += 1
                else:
                    print(f"  Failed to fetch rates for {rate_date}")

                # Rate limiting: small delay between requests
                if i < len(unique_dates):
                    time.sleep(1)  # 1 second between requests

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
            from_currency: Source currency (USD, EUR, CZK)
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

        # Get exchange rate
        rate = ExchangeRateService.get_exchange_rate(
            from_currency,
            CurrencyNormalizer.BASE_CURRENCY,
            amount_date,
            db
        )

        if rate:
            return amount * rate

        # Fallback: try last known rate
        last_rate = ExchangeRateService.get_last_known_rate(
            from_currency,
            CurrencyNormalizer.BASE_CURRENCY,
            amount_date,
            db
        )

        if last_rate:
            rate_date, rate_value = last_rate
            days_stale = (amount_date - rate_date).days
            logger.warning(
                f"Using stale exchange rate ({days_stale} days old) for "
                f"{from_currency}/{CurrencyNormalizer.BASE_CURRENCY} on {amount_date}"
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
            {
                'amount_czk': float,
                'exchange_rate_date': date,
                'exchange_rate_staleness_days': int (0 if exact, >0 if fallback),
                'conversion_warning': Optional[str]
            }
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
        rate = ExchangeRateService.get_exchange_rate(txn_currency, 'CZK', txn_date, db)

        if rate:
            return {
                'amount_czk': txn_amount * rate,
                'exchange_rate_date': txn_date,
                'exchange_rate_staleness_days': 0,
                'conversion_warning': None
            }

        # Fallback to last known
        last_rate = ExchangeRateService.get_last_known_rate(txn_currency, 'CZK', txn_date, db)

        if last_rate:
            rate_date, rate_value = last_rate
            staleness = (txn_date - rate_date).days

            return {
                'amount_czk': txn_amount * rate_value,
                'exchange_rate_date': rate_date,
                'exchange_rate_staleness_days': staleness,
                'conversion_warning': f"Used exchange rate from {rate_date} ({staleness} days before transaction)"
            }

        raise ValueError(
            f"Cannot normalize transaction {transaction.id}: "
            f"No exchange rate available for {txn_currency}/CZK on or before {txn_date}"
        )
