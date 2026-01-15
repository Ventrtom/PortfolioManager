"""
Shared test fixtures for exchange rate service tests.
"""
import pytest
import sys
import os
from datetime import date, datetime
from unittest.mock import Mock

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Load .env file so integration tests can access API keys
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.database import Base, ExchangeRate
from services.exchange_rate import (
    ExchangeRateService, ExchangeRateConfig, ExchangeRateResult,
    CurrencyPair, RateSource, Confidence
)
from services.exchange_rate.cache import ExchangeRateCache
from services.exchange_rate.providers.base import ExchangeRateProvider


@pytest.fixture
def test_db():
    """Create in-memory SQLite database for testing"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    session.close()
    engine.dispose()


@pytest.fixture
def mock_provider():
    """Create a mock provider for testing"""
    provider = Mock(spec=ExchangeRateProvider)
    provider.name = "mock-provider"
    provider.stats = Mock()
    provider.stats.is_available = True
    provider.stats.requests_made = 0
    provider.stats.successful_requests = 0
    provider.stats.failed_requests = 0
    provider.stats.rate_limit_hits = 0
    provider.stats.avg_response_time_ms = 0.0
    provider.health_check.return_value = True
    return provider


@pytest.fixture
def mock_config():
    """Create test configuration"""
    return ExchangeRateConfig(
        exchangerate_api_key="test-api-key",
        memory_cache_ttl_seconds=60,
        max_retries=1,
    )


@pytest.fixture
def sample_rate_result():
    """Create a sample exchange rate result"""
    return ExchangeRateResult(
        pair=CurrencyPair("USD", "EUR"),
        rate=0.85,
        rate_date=date(2024, 1, 15),
        source=RateSource.EXCHANGERATE_API,
        confidence=Confidence.HIGH,
        fetched_at=datetime.utcnow()
    )


@pytest.fixture
def populated_db(test_db):
    """Database with sample exchange rates"""
    rates = [
        ExchangeRate(
            base_currency="USD",
            target_currency="EUR",
            rate_date=date(2024, 1, 15),
            rate=0.85,
            source="exchangerate-api.io",
            fetched_at=datetime.utcnow(),
            confidence="high"
        ),
        ExchangeRate(
            base_currency="USD",
            target_currency="CZK",
            rate_date=date(2024, 1, 15),
            rate=22.5,
            source="exchangerate-api.io",
            fetched_at=datetime.utcnow(),
            confidence="high"
        ),
        ExchangeRate(
            base_currency="EUR",
            target_currency="CZK",
            rate_date=date(2024, 1, 15),
            rate=26.5,
            source="exchangerate-api.io",
            fetched_at=datetime.utcnow(),
            confidence="high"
        ),
        ExchangeRate(
            base_currency="EUR",
            target_currency="USD",
            rate_date=date(2024, 1, 15),
            rate=1.18,
            source="exchangerate-api.io",
            fetched_at=datetime.utcnow(),
            confidence="high"
        ),
        ExchangeRate(
            base_currency="CZK",
            target_currency="USD",
            rate_date=date(2024, 1, 15),
            rate=0.044,
            source="exchangerate-api.io",
            fetched_at=datetime.utcnow(),
            confidence="high"
        ),
        ExchangeRate(
            base_currency="CZK",
            target_currency="EUR",
            rate_date=date(2024, 1, 15),
            rate=0.038,
            source="exchangerate-api.io",
            fetched_at=datetime.utcnow(),
            confidence="high"
        ),
    ]

    for rate in rates:
        test_db.add(rate)
    test_db.commit()

    return test_db


@pytest.fixture
def service_with_mocks(mock_provider, mock_config, test_db):
    """Create service with mocked dependencies"""
    cache = ExchangeRateCache(memory_ttl_seconds=60)

    # Create a second mock for fallback provider
    fallback_provider = Mock(spec=ExchangeRateProvider)
    fallback_provider.name = "mock-fallback-provider"
    fallback_provider.stats = Mock()
    fallback_provider.stats.is_available = True
    fallback_provider.stats.requests_made = 0
    fallback_provider.stats.successful_requests = 0
    fallback_provider.stats.failed_requests = 0
    fallback_provider.stats.rate_limit_hits = 0
    fallback_provider.stats.avg_response_time_ms = 0.0
    fallback_provider.health_check.return_value = True

    service = ExchangeRateService(
        config=mock_config,
        primary_provider=mock_provider,
        fallback_provider=fallback_provider,
        cache=cache
    )

    return service, mock_provider, fallback_provider, test_db
