import yfinance as yf
from sqlalchemy.orm import Session
from models.database import Stock, StockPrice
from datetime import datetime, date, timedelta
from typing import Optional, Dict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MarketDataService:
    """Service for fetching and caching stock market data"""

    @staticmethod
    def get_stock_info(ticker: str, db: Session) -> Optional[Dict]:
        """
        Fetch stock information from yfinance and cache in database
        Returns dict with company info or None if not found
        """
        try:
            # Check if we have cached data (less than 7 days old)
            stock = db.query(Stock).filter(Stock.ticker == ticker).first()
            if stock and stock.last_updated:
                days_old = (datetime.utcnow() - stock.last_updated).days
                if days_old < 7:
                    logger.info(f"Using cached data for {ticker}")
                    return {
                        "ticker": stock.ticker,
                        "company_name": stock.company_name,
                        "sector": stock.sector,
                        "industry": stock.industry,
                        "currency": stock.currency
                    }

            # Fetch fresh data from yfinance
            logger.info(f"Fetching fresh data for {ticker}")
            stock_obj = yf.Ticker(ticker)
            info = stock_obj.info

            # Extract relevant information
            company_name = info.get("longName") or info.get("shortName")
            sector = info.get("sector")
            industry = info.get("industry")
            currency = info.get("currency", "USD")

            # Update or create stock record
            if stock:
                stock.company_name = company_name
                stock.sector = sector
                stock.industry = industry
                stock.currency = currency
                stock.last_updated = datetime.utcnow()
            else:
                stock = Stock(
                    ticker=ticker,
                    company_name=company_name,
                    sector=sector,
                    industry=industry,
                    currency=currency,
                    last_updated=datetime.utcnow()
                )
                db.add(stock)

            db.commit()

            return {
                "ticker": ticker,
                "company_name": company_name,
                "sector": sector,
                "industry": industry,
                "currency": currency
            }

        except Exception as e:
            logger.error(f"Error fetching stock info for {ticker}: {e}")
            # Return minimal data if fetch fails
            return {
                "ticker": ticker,
                "company_name": ticker,
                "sector": "Unknown",
                "industry": "Unknown",
                "currency": "USD"
            }

    @staticmethod
    def get_current_price(ticker: str, db: Session) -> Optional[float]:
        """
        Get current stock price from yfinance and cache in database
        Returns current price or None if not available
        """
        try:
            today = date.today()

            # Check if we have today's price cached
            price_record = db.query(StockPrice).filter(
                StockPrice.ticker == ticker,
                StockPrice.price_date == today
            ).first()

            if price_record:
                logger.info(f"Using cached price for {ticker}: ${price_record.price}")
                return price_record.price

            # Fetch current price from yfinance
            logger.info(f"Fetching current price for {ticker}")
            stock_obj = yf.Ticker(ticker)

            # Try to get the latest price
            history = stock_obj.history(period="1d")
            if not history.empty:
                current_price = float(history['Close'].iloc[-1])

                # Cache the price
                price_record = StockPrice(
                    ticker=ticker,
                    price=current_price,
                    price_date=today
                )
                db.add(price_record)
                db.commit()

                logger.info(f"Fetched price for {ticker}: ${current_price}")
                return current_price
            else:
                # Try info as fallback
                info = stock_obj.info
                current_price = info.get("currentPrice") or info.get("regularMarketPrice")
                if current_price:
                    price_record = StockPrice(
                        ticker=ticker,
                        price=current_price,
                        price_date=today
                    )
                    db.add(price_record)
                    db.commit()
                    return float(current_price)

            return None

        except Exception as e:
            logger.error(f"Error fetching price for {ticker}: {e}")
            return None

    @staticmethod
    def get_historical_prices(ticker: str, days: int = 365) -> Dict[date, float]:
        """
        Get historical prices for volatility calculations
        Returns dict of {date: price}
        """
        try:
            stock_obj = yf.Ticker(ticker)
            history = stock_obj.history(period=f"{days}d")

            if history.empty:
                return {}

            # Convert to dict of date: price
            prices = {}
            for index, row in history.iterrows():
                price_date = index.date()
                prices[price_date] = float(row['Close'])

            return prices

        except Exception as e:
            logger.error(f"Error fetching historical prices for {ticker}: {e}")
            return {}

    @staticmethod
    def refresh_all_prices(tickers: list, db: Session) -> Dict[str, float]:
        """
        Refresh prices for multiple tickers
        Returns dict of {ticker: price}
        """
        prices = {}
        for ticker in tickers:
            price = MarketDataService.get_current_price(ticker, db)
            if price:
                prices[ticker] = price

        return prices

    @staticmethod
    def get_dividend_history(ticker: str):
        """
        Get dividend history for a stock
        Returns DataFrame with dividend dates and amounts
        """
        try:
            stock_obj = yf.Ticker(ticker)
            dividends = stock_obj.dividends

            if dividends.empty:
                return None

            return dividends

        except Exception as e:
            logger.error(f"Error fetching dividends for {ticker}: {e}")
            return None
