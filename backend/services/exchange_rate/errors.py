"""
Custom exceptions for exchange rate service.
"""
from typing import Optional, List


class ExchangeRateError(Exception):
    """Base exception for exchange rate errors"""

    def __init__(self, message: str, code: str, details: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


class NetworkError(ExchangeRateError):
    """Network or connectivity error"""

    def __init__(
        self,
        message: str,
        provider: str,
        original_error: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            code="NETWORK_ERROR",
            details={
                "provider": provider,
                "original_error": str(original_error) if original_error else None
            }
        )
        self.provider = provider
        self.original_error = original_error


class RateLimitError(ExchangeRateError):
    """API rate limit exceeded"""

    def __init__(self, provider: str, retry_after: Optional[int] = None):
        super().__init__(
            message=f"Rate limit exceeded for {provider}",
            code="RATE_LIMIT_EXCEEDED",
            details={"provider": provider, "retry_after": retry_after}
        )
        self.provider = provider
        self.retry_after = retry_after


class InvalidCurrencyError(ExchangeRateError):
    """Invalid or unsupported currency"""

    def __init__(self, currency: str, supported: List[str]):
        super().__init__(
            message=f"Unsupported currency: {currency}. Supported: {supported}",
            code="INVALID_CURRENCY",
            details={"currency": currency, "supported": supported}
        )
        self.currency = currency


class RateNotFoundError(ExchangeRateError):
    """Exchange rate not found for given pair/date"""

    def __init__(self, base: str, target: str, rate_date: str):
        super().__init__(
            message=f"Exchange rate not found: {base}/{target} on {rate_date}",
            code="RATE_NOT_FOUND",
            details={"base": base, "target": target, "date": rate_date}
        )


class ProviderError(ExchangeRateError):
    """Provider-specific error"""

    def __init__(
        self,
        provider: str,
        message: str,
        api_error: Optional[str] = None
    ):
        super().__init__(
            message=message,
            code="PROVIDER_ERROR",
            details={"provider": provider, "api_error": api_error}
        )
        self.provider = provider
