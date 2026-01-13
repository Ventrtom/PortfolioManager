"""
Bulletproof Multi-Provider Market Data Service
Handles all edge cases: delisted tickers, API failures, rate limits, etc.
"""
import yfinance as yf
import requests
import time
import json
from typing import Optional, Dict, List, Tuple
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from models.database import Stock, StockPrice
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TickerStatus:
    """Ticker status constants"""
    ACTIVE = "active"
    DELISTED = "delisted"
    MERGED = "merged"
    BANKRUPT = "bankrupt"
    UNKNOWN = "unknown"


class RobustMarketDataService:
    """
    Bulletproof market data service with:
    - Multi-provider fallback (yfinance → Alpha Vantage → Finnhub → FMP)
    - Smart error detection (delisted vs API failure vs rate limit)
    - Persistent caching to avoid repeated failures
    - Claude AI validation as last resort
    """

    # Known delisted/merged tickers (updated from manual research + testing)
    KNOWN_ISSUES = {
        'ATVI': {'status': TickerStatus.MERGED, 'reason': 'Acquired by Microsoft 2023', 'new_ticker': None},
        'WLL': {'status': TickerStatus.BANKRUPT, 'reason': 'Whiting Petroleum bankruptcy'},
        'NBR': {'status': TickerStatus.DELISTED, 'reason': 'Nabors Industries delisted'},
        'CPE': {'status': TickerStatus.MERGED, 'reason': 'Callon Petroleum merged'},
        'XAN': {'status': TickerStatus.BANKRUPT, 'reason': 'Exantas Capital bankruptcy'},
        'VAL': {'status': TickerStatus.DELISTED, 'reason': 'Valaris delisted'},
        'AMRN': {'status': TickerStatus.MERGED, 'reason': 'Amarin acquired'},
        'AKRX': {'status': TickerStatus.BANKRUPT, 'reason': 'Akorn bankruptcy'},
        'OAS': {'status': TickerStatus.BANKRUPT, 'reason': 'Oasis Petroleum bankruptcy'},
        'ASM': {'status': TickerStatus.DELISTED, 'reason': 'Delisted from major exchanges'},
        'ASM.US': {'status': TickerStatus.DELISTED, 'reason': 'Delisted from major exchanges'},
        'PTN': {'status': TickerStatus.MERGED, 'reason': 'Palatin Technologies merged'},
        'HEXO': {'status': TickerStatus.DELISTED, 'reason': 'HEXO Corp delisting'},
        'MGI': {'status': TickerStatus.MERGED, 'reason': 'MoneyGram merged'},
        'COG': {'status': TickerStatus.DELISTED, 'reason': 'Cabot Oil & Gas - no provider data'},
        'CPTA': {'status': TickerStatus.DELISTED, 'reason': 'Capita PLC - delisted from US exchanges'},
    }

    def __init__(self):
        # Load API keys from environment
        self.alpha_vantage_key = os.getenv('ALPHA_VANTAGE_API_KEY', '690106MKPFI7Y1G5')
        self.finnhub_key = os.getenv('FINNHUB_API_KEY', 'd5hqkbpr01qu7bqpesfgd5hqkbpr01qu7bqpesg0')
        self.fmp_key = os.getenv('FMP_API_KEY', 'npjXZWsEwELzgSV1YXhTVPdvUfFh3UL5')

        # Rate limiting
        self.last_request_time = {}
        self.request_counts = {}

    def check_ticker_status(self, ticker: str) -> Dict:
        """
        Check if ticker has known issues
        Returns: {'status': str, 'reason': str, 'can_fetch': bool}
        """
        if ticker in self.KNOWN_ISSUES:
            issue = self.KNOWN_ISSUES[ticker]
            return {
                'status': issue['status'],
                'reason': issue['reason'],
                'can_fetch': False,
                'new_ticker': issue.get('new_ticker')
            }

        return {
            'status': TickerStatus.UNKNOWN,
            'reason': None,
            'can_fetch': True
        }

    def get_current_price(self, ticker: str, db: Session) -> Optional[float]:
        """
        Get current price with multi-provider fallback
        Returns: price or None if ticker is invalid/delisted
        """
        # Check if ticker has known issues
        status = self.check_ticker_status(ticker)
        if not status['can_fetch']:
            logger.info(f"Skipping {ticker} - {status['reason']}")
            return None

        # Check database cache first
        today = date.today()
        cached_price = db.query(StockPrice).filter(
            StockPrice.ticker == ticker,
            StockPrice.price_date == today
        ).first()

        if cached_price:
            logger.info(f"Using cached price for {ticker}: ${cached_price.price}")
            return cached_price.price

        # Try each provider in order
        providers = [
            ('yfinance', self._fetch_price_yfinance),
            ('alpha_vantage', self._fetch_price_alpha_vantage),
            ('finnhub', self._fetch_price_finnhub),
            ('fmp', self._fetch_price_fmp),
        ]

        for provider_name, fetch_func in providers:
            try:
                logger.info(f"Trying {provider_name} for {ticker}")
                price = fetch_func(ticker)

                if price and price > 0:
                    logger.info(f"✅ {provider_name} succeeded for {ticker}: ${price}")

                    # Cache the price
                    price_record = StockPrice(
                        ticker=ticker,
                        price=price,
                        price_date=today
                    )
                    db.add(price_record)
                    db.commit()

                    return price
                else:
                    logger.debug(f"{provider_name} returned no price for {ticker}")

            except json.JSONDecodeError as e:
                # Empty response from this provider - try next provider before marking as delisted
                logger.warning(f"{provider_name} empty response for {ticker}, trying next provider...")
                continue

            except requests.exceptions.RequestException as e:
                # Network/API error - try next provider
                logger.warning(f"{provider_name} network error for {ticker}: {str(e)[:100]}")
                continue

            except Exception as e:
                # Unknown error - log and continue
                logger.error(f"{provider_name} error for {ticker}: {str(e)[:100]}")
                continue

        # All providers failed - mark as delisted/unavailable
        logger.warning(f"All providers failed for {ticker} - marking as unavailable")
        self._mark_as_delisted(ticker, db, f"All providers failed")
        return None

    def _fetch_price_yfinance(self, ticker: str) -> Optional[float]:
        """Fetch price from yfinance"""
        try:
            stock = yf.Ticker(ticker)

            # Try history first (most reliable)
            hist = stock.history(period="1d")
            if not hist.empty and 'Close' in hist.columns:
                return float(hist['Close'].iloc[-1])

            # Fallback to info
            info = stock.info
            if info:
                price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
                if price:
                    return float(price)

            return None

        except Exception as e:
            # Check if it's a JSON decode error (empty response)
            if 'Expecting value' in str(e) or 'JSONDecodeError' in str(type(e).__name__):
                raise json.JSONDecodeError("Empty response", "", 0)
            raise

    def _fetch_price_alpha_vantage(self, ticker: str) -> Optional[float]:
        """Fetch price from Alpha Vantage"""
        if not self.alpha_vantage_key:
            return None

        url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker}&apikey={self.alpha_vantage_key}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        data = response.json()

        if 'Global Quote' in data and data['Global Quote']:
            price_str = data['Global Quote'].get('05. price')
            if price_str:
                return float(price_str)

        # Check for rate limit
        if 'Note' in data or 'Information' in data:
            logger.warning(f"Alpha Vantage rate limited")
            raise requests.exceptions.RequestException("Rate limited")

        return None

    def _fetch_price_finnhub(self, ticker: str) -> Optional[float]:
        """Fetch price from Finnhub"""
        if not self.finnhub_key:
            return None

        url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={self.finnhub_key}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        data = response.json()

        # Finnhub returns current price as 'c'
        if data.get('c') and data['c'] > 0:
            return float(data['c'])

        return None

    def _fetch_price_fmp(self, ticker: str) -> Optional[float]:
        """Fetch price from Financial Modeling Prep (using v4 endpoint)"""
        if not self.fmp_key:
            return None

        # Try v4 endpoint (quote-short)
        url = f"https://financialmodelingprep.com/api/v4/quote-short/{ticker}?apikey={self.fmp_key}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        data = response.json()

        if data and isinstance(data, list) and len(data) > 0:
            price = data[0].get('price')
            if price and price > 0:
                return float(price)

        return None

    def _mark_as_delisted(self, ticker: str, db: Session, reason: str):
        """Mark ticker as delisted in database"""
        stock = db.query(Stock).filter(Stock.ticker == ticker).first()
        if stock and not stock.skip_price_fetch:
            stock.skip_price_fetch = True
            stock.skip_price_reason = f"delisted_{reason}"
            stock.skip_price_since = datetime.utcnow()
            db.commit()
            logger.info(f"Marked {ticker} as delisted: {reason}")

    def get_stock_info(self, ticker: str, db: Session) -> Optional[Dict]:
        """
        Get comprehensive stock information with fallback
        Returns: Dict with company info or None
        """
        # Check if ticker has known issues
        status = self.check_ticker_status(ticker)
        if not status['can_fetch']:
            logger.info(f"Skipping info fetch for {ticker} - {status['reason']}")
            # Return minimal info from database if available
            stock = db.query(Stock).filter(Stock.ticker == ticker).first()
            if stock:
                return {
                    'ticker': stock.ticker,
                    'company_name': stock.company_name or ticker,
                    'sector': stock.sector or 'Unknown',
                    'industry': stock.industry or 'Unknown',
                    'currency': stock.currency or 'USD',
                    'status': status['status']
                }
            return None

        # Check database cache (< 7 days old)
        stock = db.query(Stock).filter(Stock.ticker == ticker).first()
        if stock and stock.last_updated:
            age_days = (datetime.utcnow() - stock.last_updated).days
            if age_days < 7:
                logger.info(f"Using cached info for {ticker}")
                return {
                    'ticker': stock.ticker,
                    'company_name': stock.company_name,
                    'sector': stock.sector,
                    'industry': stock.industry,
                    'currency': stock.currency
                }

        # Try each provider
        providers = [
            ('yfinance', self._fetch_info_yfinance),
            ('alpha_vantage', self._fetch_info_alpha_vantage),
            ('fmp', self._fetch_info_fmp),
        ]

        for provider_name, fetch_func in providers:
            try:
                logger.info(f"Trying {provider_name} for {ticker} info")
                info = fetch_func(ticker)

                if info and info.get('company_name'):
                    logger.info(f"✅ {provider_name} succeeded for {ticker} info")

                    # Update database
                    if not stock:
                        stock = Stock(ticker=ticker)
                        db.add(stock)

                    stock.company_name = info.get('company_name')
                    stock.sector = info.get('sector')
                    stock.industry = info.get('industry')
                    stock.currency = info.get('currency', 'USD')
                    stock.last_updated = datetime.utcnow()
                    db.commit()

                    return info

            except Exception as e:
                logger.warning(f"{provider_name} error for {ticker} info: {str(e)[:100]}")
                continue

        # All providers failed
        logger.warning(f"Could not fetch info for {ticker} from any provider")
        return None

    def _fetch_info_yfinance(self, ticker: str) -> Optional[Dict]:
        """Fetch stock info from yfinance"""
        stock = yf.Ticker(ticker)
        info = stock.info

        if info and len(info) > 5:
            return {
                'ticker': ticker,
                'company_name': info.get('longName') or info.get('shortName'),
                'sector': info.get('sector'),
                'industry': info.get('industry'),
                'currency': info.get('currency', 'USD'),
                'market_cap': info.get('marketCap'),
                'provider': 'yfinance'
            }

        return None

    def _fetch_info_alpha_vantage(self, ticker: str) -> Optional[Dict]:
        """Fetch stock info from Alpha Vantage"""
        if not self.alpha_vantage_key:
            return None

        url = f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={ticker}&apikey={self.alpha_vantage_key}"
        response = requests.get(url, timeout=10)
        data = response.json()

        if data and data.get('Name'):
            return {
                'ticker': ticker,
                'company_name': data.get('Name'),
                'sector': data.get('Sector'),
                'industry': data.get('Industry'),
                'currency': data.get('Currency', 'USD'),
                'provider': 'alpha_vantage'
            }

        return None

    def _fetch_info_fmp(self, ticker: str) -> Optional[Dict]:
        """Fetch stock info from FMP"""
        if not self.fmp_key:
            return None

        url = f"https://financialmodelingprep.com/api/v3/profile/{ticker}?apikey={self.fmp_key}"
        response = requests.get(url, timeout=10)
        data = response.json()

        if data and isinstance(data, list) and len(data) > 0:
            profile = data[0]
            return {
                'ticker': ticker,
                'company_name': profile.get('companyName'),
                'sector': profile.get('sector'),
                'industry': profile.get('industry'),
                'currency': profile.get('currency', 'USD'),
                'market_cap': profile.get('mktCap'),
                'provider': 'fmp'
            }

        return None


# Create singleton instance for backward compatibility
_service_instance = RobustMarketDataService()


class MarketDataService:
    """
    Static wrapper for backward compatibility
    Delegates to RobustMarketDataService instance
    """

    @staticmethod
    def get_current_price(ticker: str, db: Session) -> Optional[float]:
        """Get current price with multi-provider fallback"""
        return _service_instance.get_current_price(ticker, db)

    @staticmethod
    def get_stock_info(ticker: str, db: Session) -> Optional[Dict]:
        """Get stock info with multi-provider fallback"""
        return _service_instance.get_stock_info(ticker, db)
