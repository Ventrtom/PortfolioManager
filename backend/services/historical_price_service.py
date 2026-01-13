import yfinance as yf
from sqlalchemy.orm import Session
from models.database import StockPrice
from datetime import date, timedelta
from typing import List, Optional, Tuple, Dict, Set
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress yfinance's verbose error logging for delisted stocks
logging.getLogger('yfinance').setLevel(logging.CRITICAL)


class HistoricalPriceService:
    """Service for managing historical stock prices"""

    # Class-level cache for delisted/failed tickers to avoid repeated API calls
    _failed_tickers: Set[str] = set()

    @staticmethod
    def get_price_for_date(ticker: str, target_date: date, db: Session) -> Optional[float]:
        """
        Get price for specific date with fallback strategy:
        1. Check StockPrice table (cached)
        2. Fetch from yfinance if missing
        3. Use last known price within 7 days (for weekends/holidays)
        4. Return None if no data available

        Args:
            ticker: Stock ticker symbol
            target_date: Date for price lookup
            db: Database session

        Returns:
            Price as float, or None if unavailable
        """
        # Check cache first
        cached_price = db.query(StockPrice).filter(
            StockPrice.ticker == ticker,
            StockPrice.price_date == target_date
        ).first()

        if cached_price:
            return cached_price.price

        # Skip known delisted/failed tickers to avoid repeated API calls
        if ticker in HistoricalPriceService._failed_tickers:
            # Silently use last known price for delisted stocks
            last_price = HistoricalPriceService.get_last_known_price(ticker, target_date, db, max_days_back=365)
            if last_price:
                return last_price[1]  # Return price only
            return None

        # Try to fetch from yfinance
        try:
            price = HistoricalPriceService._fetch_single_price(ticker, target_date, db)
            if price:
                return price
        except Exception as e:
            # Mark as failed ticker to avoid future retries
            HistoricalPriceService._failed_tickers.add(ticker)
            logger.debug(f"Failed to fetch price for {ticker} on {target_date}: {e}")

        # Fallback: use last known price within 7 days
        last_price = HistoricalPriceService.get_last_known_price(ticker, target_date, db, max_days_back=7)
        if last_price:
            price_date, price = last_price
            days_diff = (target_date - price_date).days
            logger.debug(f"Using price from {price_date} for {ticker} on {target_date} ({days_diff} days ago)")
            return price

        # Only log warning once per ticker
        if ticker not in HistoricalPriceService._failed_tickers:
            logger.warning(f"No price available for {ticker} on {target_date} (possibly delisted)")
            HistoricalPriceService._failed_tickers.add(ticker)

        return None

    @staticmethod
    def _fetch_single_price(ticker: str, target_date: date, db: Session) -> Optional[float]:
        """
        Fetch single price from yfinance and cache it

        Args:
            ticker: Stock ticker
            target_date: Target date
            db: Database session

        Returns:
            Price or None
        """
        try:
            # Fetch a few days around target date to handle weekends
            start_date = target_date - timedelta(days=5)
            end_date = target_date + timedelta(days=2)

            stock = yf.Ticker(ticker)
            hist = stock.history(start=start_date, end=end_date)

            if hist.empty:
                return None

            # Cache all fetched prices
            for hist_date, row in hist.iterrows():
                price_date = hist_date.date()
                close_price = float(row['Close'])

                # Check if already cached
                existing = db.query(StockPrice).filter(
                    StockPrice.ticker == ticker,
                    StockPrice.price_date == price_date
                ).first()

                if not existing:
                    new_price = StockPrice(
                        ticker=ticker,
                        price=close_price,
                        price_date=price_date
                    )
                    db.add(new_price)

            db.commit()

            # Return price for target date if available
            for hist_date, row in hist.iterrows():
                if hist_date.date() == target_date:
                    return float(row['Close'])

            return None

        except Exception as e:
            logger.error(f"Error fetching price for {ticker} on {target_date}: {e}")
            return None

    @staticmethod
    def populate_historical_prices(
        ticker: str,
        start_date: date,
        end_date: date,
        db: Session
    ) -> int:
        """
        Batch populate StockPrice table for date range

        Args:
            ticker: Stock ticker
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            db: Database session

        Returns:
            Count of prices added
        """
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(start=start_date, end=end_date + timedelta(days=1))

            if hist.empty:
                logger.warning(f"No historical data found for {ticker} from {start_date} to {end_date}")
                return 0

            count = 0
            for hist_date, row in hist.iterrows():
                price_date = hist_date.date()
                close_price = float(row['Close'])

                # Check if already exists
                existing = db.query(StockPrice).filter(
                    StockPrice.ticker == ticker,
                    StockPrice.price_date == price_date
                ).first()

                if not existing:
                    new_price = StockPrice(
                        ticker=ticker,
                        price=close_price,
                        price_date=price_date
                    )
                    db.add(new_price)
                    count += 1

            db.commit()
            logger.info(f"Populated {count} historical prices for {ticker} from {start_date} to {end_date}")
            return count

        except Exception as e:
            logger.error(f"Error populating historical prices for {ticker}: {e}")
            db.rollback()
            return 0

    @staticmethod
    def ensure_prices_for_period(
        tickers: List[str],
        start_date: date,
        end_date: date,
        db: Session
    ) -> Dict[str, int]:
        """
        Ensure all tickers have prices for the entire period.
        Populates missing prices on-demand.

        Args:
            tickers: List of stock tickers
            start_date: Start date
            end_date: End date
            db: Database session

        Returns:
            Dict of {ticker: count_added}
        """
        results = {}

        for ticker in tickers:
            # Check if we have any prices for this ticker in the range
            existing_count = db.query(StockPrice).filter(
                StockPrice.ticker == ticker,
                StockPrice.price_date >= start_date,
                StockPrice.price_date <= end_date
            ).count()

            # If we have very few prices, repopulate
            expected_days = (end_date - start_date).days
            if existing_count < expected_days * 0.5:  # If less than 50% coverage
                logger.info(f"Populating historical prices for {ticker} (only {existing_count} cached)")
                added = HistoricalPriceService.populate_historical_prices(
                    ticker,
                    start_date,
                    end_date,
                    db
                )
                results[ticker] = added
            else:
                logger.debug(f"Sufficient cached prices for {ticker}: {existing_count}")
                results[ticker] = 0

        return results

    @staticmethod
    def get_last_known_price(
        ticker: str,
        before_date: date,
        db: Session,
        max_days_back: int = 7
    ) -> Optional[Tuple[date, float]]:
        """
        Get most recent price before target date.
        Used as fallback for weekends/holidays.

        Args:
            ticker: Stock ticker
            before_date: Find price before this date
            db: Database session
            max_days_back: Maximum days to look back

        Returns:
            Tuple of (price_date, price) or None
        """
        cutoff_date = before_date - timedelta(days=max_days_back)

        last_price = db.query(StockPrice).filter(
            StockPrice.ticker == ticker,
            StockPrice.price_date < before_date,
            StockPrice.price_date >= cutoff_date
        ).order_by(StockPrice.price_date.desc()).first()

        if last_price:
            return (last_price.price_date, last_price.price)

        return None

    @staticmethod
    def get_price_series(
        ticker: str,
        start_date: date,
        end_date: date,
        db: Session
    ) -> List[Tuple[date, float]]:
        """
        Get series of prices for a ticker

        Args:
            ticker: Stock ticker
            start_date: Start date
            end_date: End date
            db: Database session

        Returns:
            List of (date, price) tuples
        """
        prices = db.query(StockPrice).filter(
            StockPrice.ticker == ticker,
            StockPrice.price_date >= start_date,
            StockPrice.price_date <= end_date
        ).order_by(StockPrice.price_date.asc()).all()

        return [(p.price_date, p.price) for p in prices]
