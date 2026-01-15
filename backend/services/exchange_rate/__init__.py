"""
Exchange rate service package.

Provides reliable exchange rate fetching with caching and provider fallback.

Example usage:
    from services.exchange_rate import ExchangeRateService

    service = ExchangeRateService()
    rate = service.get_rate("USD", "EUR", date(2024, 1, 15), db)
"""
from .service import ExchangeRateService
from .types import (
    ExchangeRateResult,
    ConversionResult,
    MultiCurrencyResult,
    CurrencyPair,
    RateSource,
    Confidence,
)
from .errors import (
    ExchangeRateError,
    NetworkError,
    RateLimitError,
    InvalidCurrencyError,
    RateNotFoundError,
    ProviderError,
)
from .config import ExchangeRateConfig

__all__ = [
    # Main service
    "ExchangeRateService",

    # Types
    "ExchangeRateResult",
    "ConversionResult",
    "MultiCurrencyResult",
    "CurrencyPair",
    "RateSource",
    "Confidence",

    # Errors
    "ExchangeRateError",
    "NetworkError",
    "RateLimitError",
    "InvalidCurrencyError",
    "RateNotFoundError",
    "ProviderError",

    # Config
    "ExchangeRateConfig",
]
