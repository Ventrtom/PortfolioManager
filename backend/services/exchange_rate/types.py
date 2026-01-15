"""
Data types for exchange rate service.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, List, Dict
from enum import Enum


class RateSource(Enum):
    """Source of exchange rate data"""
    IDENTITY = "identity"
    DATABASE_CACHE = "database_cache"
    MEMORY_CACHE = "memory_cache"
    FRANKFURTER = "frankfurter"
    EXCHANGERATE_API = "exchangerate-api.io"
    EXCHANGERATE_HOST = "exchangerate.host"
    HISTORICAL_FALLBACK = "historical"
    MANUAL_OVERRIDE = "manual_override"


class Confidence(Enum):
    """Confidence level in the rate"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class CurrencyPair:
    """Immutable currency pair"""
    base: str
    target: str

    def __post_init__(self):
        object.__setattr__(self, 'base', self.base.upper())
        object.__setattr__(self, 'target', self.target.upper())

    @property
    def is_identity(self) -> bool:
        return self.base == self.target

    def __str__(self) -> str:
        return f"{self.base}/{self.target}"


@dataclass
class ExchangeRateResult:
    """Result of an exchange rate lookup"""
    pair: CurrencyPair
    rate: float
    rate_date: date
    source: RateSource
    confidence: Confidence
    fetched_at: datetime

    is_stale: bool = False
    staleness_days: int = 0
    needs_review: bool = False
    review_reason: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "base": self.pair.base,
            "target": self.pair.target,
            "rate": self.rate,
            "rate_date": self.rate_date.isoformat(),
            "source": self.source.value,
            "confidence": self.confidence.value,
            "fetched_at": self.fetched_at.isoformat(),
            "is_stale": self.is_stale,
            "staleness_days": self.staleness_days,
            "needs_review": self.needs_review,
            "review_reason": self.review_reason,
        }


@dataclass
class ConversionResult:
    """Result of a currency conversion"""
    original_amount: float
    original_currency: str
    converted_amount: float
    target_currency: str
    rate_used: ExchangeRateResult

    def to_dict(self) -> dict:
        return {
            "original_amount": self.original_amount,
            "original_currency": self.original_currency,
            "converted_amount": self.converted_amount,
            "target_currency": self.target_currency,
            "rate": self.rate_used.rate,
            "rate_source": self.rate_used.source.value,
        }


@dataclass
class MultiCurrencyResult:
    """Result of converting to all supported currencies"""
    usd: Optional[float]
    eur: Optional[float]
    czk: Optional[float]
    source_currency: str
    source_amount: float
    rates_used: Dict[str, ExchangeRateResult] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    failed_conversions: List[str] = field(default_factory=list)

    @property
    def needs_review(self) -> bool:
        return any(r.needs_review for r in self.rates_used.values())

    @property
    def is_complete(self) -> bool:
        return len(self.failed_conversions) == 0

    def to_dict(self) -> dict:
        return {
            "usd": self.usd,
            "eur": self.eur,
            "czk": self.czk,
            "source_currency": self.source_currency,
            "source_amount": self.source_amount,
            "is_complete": self.is_complete,
            "needs_review": self.needs_review,
            "warnings": self.warnings,
            "failed_conversions": self.failed_conversions,
        }


@dataclass
class ProviderStats:
    """Statistics for a provider"""
    name: str
    requests_made: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rate_limit_hits: int = 0
    avg_response_time_ms: float = 0.0
    last_request_time: Optional[datetime] = None
    is_available: bool = True
