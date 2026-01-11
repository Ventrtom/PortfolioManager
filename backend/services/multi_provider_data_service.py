"""
Multi-Provider Market Data Service
Supports multiple data sources with automatic fallback:
1. yfinance (Yahoo Finance) - Primary, free, no API key needed
2. Alpha Vantage - Free tier: 25 requests/day
3. Finnhub - Free tier: 60 calls/minute
4. Financial Modeling Prep - Free tier: 250 requests/day
"""

import yfinance as yf
import requests
import time
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from models.database import Stock
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataProvider:
    """Base class for data providers"""

    def __init__(self, name: str, api_key: Optional[str] = None):
        self.name = name
        self.api_key = api_key
        self.last_request_time = None
        self.request_count = 0
        self.rate_limit_reset = None

    def can_make_request(self) -> bool:
        """Check if we can make a request based on rate limits"""
        return True

    def get_stock_info(self, ticker: str) -> Optional[Dict]:
        """Fetch stock information - to be implemented by subclasses"""
        raise NotImplementedError


class YFinanceProvider(DataProvider):
    """Yahoo Finance provider via yfinance library"""

    def __init__(self):
        super().__init__("yfinance")
        self.min_request_interval = 0.5  # 500ms between requests

    def can_make_request(self) -> bool:
        if self.last_request_time:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.min_request_interval:
                time.sleep(self.min_request_interval - elapsed)
        return True

    def get_stock_info(self, ticker: str) -> Optional[Dict]:
        """Fetch stock info from Yahoo Finance"""
        try:
            self.can_make_request()
            self.last_request_time = time.time()

            stock_obj = yf.Ticker(ticker)
            info = stock_obj.info

            # Check if we got valid data
            if not info or len(info) < 5:
                logger.warning(f"{self.name}: No data for {ticker}")
                return None

            # Check for rate limit indicators
            if 'error' in str(info).lower() or '429' in str(info):
                logger.warning(f"{self.name}: Rate limited for {ticker}")
                return None

            company_name = info.get("longName") or info.get("shortName")
            sector = info.get("sector")
            industry = info.get("industry")
            currency = info.get("currency", "USD")
            market_cap = info.get("marketCap")
            volume = info.get("volume") or info.get("averageVolume")

            # Must have at least company name to be valid
            if not company_name:
                logger.warning(f"{self.name}: No company name for {ticker}")
                return None

            logger.info(f"{self.name}: Successfully fetched {ticker}")
            return {
                "ticker": ticker,
                "company_name": company_name,
                "sector": sector,
                "industry": industry,
                "currency": currency,
                "market_cap": market_cap,
                "volume": volume,
                "provider": self.name
            }

        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "Too Many Requests" in error_msg:
                logger.warning(f"{self.name}: Rate limited - {ticker}")
            else:
                logger.error(f"{self.name}: Error fetching {ticker}: {e}")
            return None


class AlphaVantageProvider(DataProvider):
    """Alpha Vantage API provider"""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__("AlphaVantage", api_key or os.getenv("ALPHA_VANTAGE_API_KEY"))
        self.base_url = "https://www.alphavantage.co/query"
        self.daily_limit = 25
        self.min_request_interval = 12  # 12 seconds between requests for free tier

    def can_make_request(self) -> bool:
        if not self.api_key:
            return False

        # Check daily limit
        if self.request_count >= self.daily_limit:
            if self.rate_limit_reset and datetime.now() < self.rate_limit_reset:
                return False
            else:
                self.request_count = 0
                self.rate_limit_reset = None

        # Check rate limit
        if self.last_request_time:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.min_request_interval:
                time.sleep(self.min_request_interval - elapsed)

        return True

    def get_stock_info(self, ticker: str) -> Optional[Dict]:
        """Fetch stock info from Alpha Vantage"""
        try:
            if not self.can_make_request():
                logger.debug(f"{self.name}: Rate limited, skipping {ticker}")
                return None

            self.last_request_time = time.time()
            self.request_count += 1

            # Get company overview
            params = {
                "function": "OVERVIEW",
                "symbol": ticker,
                "apikey": self.api_key
            }

            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Check for errors
            if "Error Message" in data or "Note" in data:
                logger.warning(f"{self.name}: API error for {ticker}")
                return None

            if not data or "Symbol" not in data:
                logger.warning(f"{self.name}: No data for {ticker}")
                return None

            logger.info(f"{self.name}: Successfully fetched {ticker}")
            return {
                "ticker": ticker,
                "company_name": data.get("Name"),
                "sector": data.get("Sector"),
                "industry": data.get("Industry"),
                "currency": data.get("Currency", "USD"),
                "market_cap": int(data.get("MarketCapitalization", 0)) if data.get("MarketCapitalization") else None,
                "volume": None,  # Not in overview
                "provider": self.name
            }

        except Exception as e:
            logger.error(f"{self.name}: Error fetching {ticker}: {e}")
            return None


class FinnhubProvider(DataProvider):
    """Finnhub API provider"""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__("Finnhub", api_key or os.getenv("FINNHUB_API_KEY"))
        self.base_url = "https://finnhub.io/api/v1"
        self.requests_per_minute = 60
        self.min_request_interval = 1.0  # 1 second between requests

    def can_make_request(self) -> bool:
        if not self.api_key:
            return False

        if self.last_request_time:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.min_request_interval:
                time.sleep(self.min_request_interval - elapsed)

        return True

    def get_stock_info(self, ticker: str) -> Optional[Dict]:
        """Fetch stock info from Finnhub"""
        try:
            if not self.can_make_request():
                logger.debug(f"{self.name}: Rate limited, skipping {ticker}")
                return None

            self.last_request_time = time.time()

            # Get company profile
            headers = {"X-Finnhub-Token": self.api_key}
            url = f"{self.base_url}/stock/profile2"
            params = {"symbol": ticker}

            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            if not data or "name" not in data:
                logger.warning(f"{self.name}: No data for {ticker}")
                return None

            logger.info(f"{self.name}: Successfully fetched {ticker}")
            return {
                "ticker": ticker,
                "company_name": data.get("name"),
                "sector": data.get("finnhubIndustry"),
                "industry": data.get("finnhubIndustry"),  # Finnhub uses same field
                "currency": data.get("currency", "USD"),
                "market_cap": data.get("marketCapitalization") * 1_000_000 if data.get("marketCapitalization") else None,
                "volume": None,  # Need separate call for quote data
                "provider": self.name
            }

        except Exception as e:
            logger.error(f"{self.name}: Error fetching {ticker}: {e}")
            return None


class FinancialModelingPrepProvider(DataProvider):
    """Financial Modeling Prep API provider"""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__("FMP", api_key or os.getenv("FMP_API_KEY"))
        self.base_url = "https://financialmodelingprep.com/api/v3"
        self.daily_limit = 250
        self.min_request_interval = 0.5

    def can_make_request(self) -> bool:
        if not self.api_key:
            return False

        # Check daily limit
        if self.request_count >= self.daily_limit:
            if self.rate_limit_reset and datetime.now() < self.rate_limit_reset:
                return False
            else:
                self.request_count = 0
                self.rate_limit_reset = None

        if self.last_request_time:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.min_request_interval:
                time.sleep(self.min_request_interval - elapsed)

        return True

    def get_stock_info(self, ticker: str) -> Optional[Dict]:
        """Fetch stock info from Financial Modeling Prep"""
        try:
            if not self.can_make_request():
                logger.debug(f"{self.name}: Rate limited, skipping {ticker}")
                return None

            self.last_request_time = time.time()
            self.request_count += 1

            # Get company profile
            url = f"{self.base_url}/profile/{ticker}"
            params = {"apikey": self.api_key}

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if not data or len(data) == 0:
                logger.warning(f"{self.name}: No data for {ticker}")
                return None

            profile = data[0]

            logger.info(f"{self.name}: Successfully fetched {ticker}")
            return {
                "ticker": ticker,
                "company_name": profile.get("companyName"),
                "sector": profile.get("sector"),
                "industry": profile.get("industry"),
                "currency": profile.get("currency", "USD"),
                "market_cap": profile.get("mktCap"),
                "volume": profile.get("volAvg"),
                "provider": self.name
            }

        except Exception as e:
            logger.error(f"{self.name}: Error fetching {ticker}: {e}")
            return None


class MultiProviderDataService:
    """
    Service that tries multiple data providers in sequence until one succeeds
    Implements intelligent fallback and rate limit handling
    """

    def __init__(self):
        # Initialize all providers
        self.providers: List[DataProvider] = [
            YFinanceProvider(),
            AlphaVantageProvider(),
            FinnhubProvider(),
            FinancialModelingPrepProvider(),
        ]

        # Filter out providers without API keys (except yfinance)
        self.active_providers = [
            p for p in self.providers
            if p.name == "yfinance" or p.api_key
        ]

        logger.info(f"Initialized MultiProviderDataService with {len(self.active_providers)} active providers: {[p.name for p in self.active_providers]}")

        # Cache for failed tickers per provider
        self._provider_failures: Dict[str, Dict[str, datetime]] = {}

    def get_stock_info(self, ticker: str, db: Session) -> Optional[Dict]:
        """
        Try to fetch stock info from multiple providers with fallback
        Returns first successful result or None if all fail
        """

        # Check database cache first (less than 7 days old)
        stock = db.query(Stock).filter(Stock.ticker == ticker).first()
        if stock and stock.last_updated:
            days_old = (datetime.utcnow() - stock.last_updated).days
            if days_old < 7 and stock.company_name:
                logger.info(f"Using cached data for {ticker} ({days_old} days old)")
                return {
                    "ticker": stock.ticker,
                    "company_name": stock.company_name,
                    "sector": stock.sector,
                    "industry": stock.industry,
                    "currency": stock.currency,
                    "market_cap": stock.market_cap,
                    "volume": stock.volume,
                    "provider": "cache"
                }

        # Try each provider in sequence
        for provider in self.active_providers:
            try:
                # Check if this provider recently failed for this ticker
                provider_key = f"{provider.name}:{ticker}"
                if provider_key in self._provider_failures:
                    last_failure = self._provider_failures[provider_key]
                    if datetime.now() - last_failure < timedelta(minutes=15):
                        logger.debug(f"Skipping {provider.name} for {ticker} - recently failed")
                        continue

                logger.info(f"Trying {provider.name} for {ticker}")
                result = provider.get_stock_info(ticker)

                if result and result.get("company_name"):
                    logger.info(f"✓ Successfully fetched {ticker} from {provider.name}")

                    # Clear failure cache for this provider
                    if provider_key in self._provider_failures:
                        del self._provider_failures[provider_key]

                    return result
                else:
                    # Mark as failed for this provider
                    self._provider_failures[provider_key] = datetime.now()
                    logger.debug(f"{provider.name} returned no data for {ticker}")

            except Exception as e:
                logger.error(f"{provider.name} error for {ticker}: {e}")
                self._provider_failures[f"{provider.name}:{ticker}"] = datetime.now()
                continue

        logger.warning(f"All providers failed for {ticker}")
        return None

    def get_provider_status(self) -> Dict[str, any]:
        """Get status of all providers for debugging"""
        return {
            "active_providers": [p.name for p in self.active_providers],
            "total_providers": len(self.providers),
            "provider_details": [
                {
                    "name": p.name,
                    "has_api_key": bool(p.api_key) if p.name != "yfinance" else "N/A",
                    "request_count": p.request_count
                }
                for p in self.active_providers
            ]
        }
