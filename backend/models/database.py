from sqlalchemy import create_engine, Column, Integer, Float, String, Date, DateTime, Text, Boolean, Index, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./portfolio.db")

# SQLite-specific configuration
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # PostgreSQL or other databases don't need check_same_thread
    engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Database models
class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    transaction_type = Column(String, nullable=False)  # BUY, SELL, DIVIDEND, FEE, TAX, DEPOSIT, WITHDRAWAL
    ticker = Column(String, nullable=False, index=True)  # Empty string for DEPOSIT/WITHDRAWAL
    quantity = Column(Float, nullable=True)  # Null for fees/taxes
    price = Column(Float, nullable=True)  # Price per share
    total_amount = Column(Float, nullable=False)  # Total transaction amount
    transaction_date = Column(Date, nullable=False, index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    version = Column(Integer, default=1, nullable=False)  # Optimistic locking

    # Multi-currency support
    transaction_currency = Column(String, default="CZK", nullable=False, index=True)
    amount_usd = Column(Float, nullable=True)
    amount_eur = Column(Float, nullable=True)
    amount_czk = Column(Float, nullable=True)

    # Import tracking fields
    import_source = Column(String, nullable=True)  # e.g., "broker_csv_import"
    import_batch_id = Column(String, nullable=True)  # Timestamp or batch identifier
    broker_transaction_id = Column(String, nullable=True, index=True)  # Original broker ID

    # Exchange rate status tracking
    exchange_rate_status = Column(String, default='complete')  # 'complete', 'partial', 'pending_review'
    exchange_rate_notes = Column(Text, nullable=True)  # JSON with details about missing/flagged rates

    __table_args__ = (
        Index('ix_transactions_ticker_date_type', 'ticker', 'transaction_date', 'transaction_type'),
    )


class Stock(Base):
    __tablename__ = "stocks"

    # Primary identifier - user's original input
    ticker = Column(String, primary_key=True, index=True)

    # Ticker mapping - the symbol that actually works with APIs
    resolved_symbol = Column(String, nullable=True)  # Symbol used for data fetching
    alternative_symbols = Column(Text, nullable=True)  # JSON array: ["GEO", "GEO:US"]

    # Company info
    company_name = Column(String, nullable=True)
    sector = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    currency = Column(String, default="USD")
    last_updated = Column(DateTime, nullable=True)

    # Stock enrichment fields
    market_cap = Column(Float, nullable=True)
    volume = Column(Integer, nullable=True)
    enrichment_status = Column(String, default='pending')  # 'pending', 'in_progress', 'complete', 'failed', 'manual'
    enrichment_attempts = Column(Integer, default=0)
    enrichment_error = Column(Text, nullable=True)
    last_enrichment_attempt = Column(DateTime, nullable=True)
    is_manually_edited = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Price fetch skip flags
    skip_price_fetch = Column(Boolean, default=False)
    skip_price_reason = Column(String, nullable=True)
    skip_price_since = Column(DateTime, nullable=True)
    consecutive_failures = Column(Integer, default=0)


class StockPrice(Base):
    __tablename__ = "stock_prices"

    ticker = Column(String, primary_key=True, index=True)
    price = Column(Float, nullable=False)
    price_date = Column(Date, primary_key=True)

    __table_args__ = (
        Index('ix_stock_prices_ticker_date', 'ticker', 'price_date'),
    )


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"

    base_currency = Column(String, primary_key=True, index=True)  # USD, EUR, CZK
    target_currency = Column(String, primary_key=True, index=True)  # USD, EUR, CZK
    rate_date = Column(Date, primary_key=True, index=True)  # Date of exchange rate
    rate = Column(Float, nullable=False)  # Exchange rate value
    source = Column(String, default="exchangerate-api.io")  # API source
    fetched_at = Column(DateTime, default=datetime.utcnow)  # When we fetched it

    # AI tracking fields
    confidence = Column(String, nullable=True)  # 'high', 'medium', 'low'
    ai_used = Column(Boolean, default=False)
    ai_sources = Column(JSON, nullable=True)  # List of URLs for AI results
    needs_manual_review = Column(Boolean, default=False)
    manual_review_reason = Column(String, nullable=True)

    __table_args__ = (
        Index('ix_exchange_rates_lookup', 'base_currency', 'target_currency', 'rate_date'),
    )


class TransactionHistory(Base):
    __tablename__ = "transaction_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    transaction_id = Column(Integer, index=True, nullable=False)

    # Snapshot of transaction fields at time of change
    transaction_type = Column(String, nullable=False)
    ticker = Column(String, nullable=False, index=True)
    quantity = Column(Float, nullable=True)
    price = Column(Float, nullable=True)
    total_amount = Column(Float, nullable=False)
    transaction_date = Column(Date, nullable=False, index=True)
    notes = Column(Text, nullable=True)

    # Multi-currency support
    transaction_currency = Column(String, nullable=True)
    amount_usd = Column(Float, nullable=True)
    amount_eur = Column(Float, nullable=True)
    amount_czk = Column(Float, nullable=True)

    # Audit metadata
    change_type = Column(String, nullable=False)  # 'CREATE', 'UPDATE', 'DELETE'
    changed_by = Column(String, nullable=True)  # Future: user identification
    changed_at = Column(DateTime, default=datetime.utcnow, index=True)
    changed_fields = Column(Text, nullable=True)  # JSON string of changed fields


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    calculated_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Portfolio Summary fields
    total_value = Column(Float, nullable=False)
    cost_basis = Column(Float, nullable=False)
    unrealized_gain = Column(Float, nullable=False)
    unrealized_gain_percent = Column(Float, nullable=False)
    realized_gain = Column(Float, nullable=False)
    cash_balance = Column(Float, nullable=False)

    # Diversification fields
    number_of_holdings = Column(Integer, nullable=False)
    largest_position_percent = Column(Float, nullable=False)
    top_5_concentration = Column(Float, nullable=False)
    herfindahl_index = Column(Float, nullable=False)
    number_of_sectors = Column(Integer, nullable=False)
    number_of_industries = Column(Integer, nullable=False)

    # Volatility fields
    daily_volatility = Column(Float, nullable=True)
    annualized_volatility = Column(Float, nullable=True)
    sharpe_ratio = Column(Float, nullable=True)
    data_frequency = Column(String, nullable=True)
    data_quality = Column(String, nullable=True)

    # Dividend fields
    total_dividends = Column(Float, nullable=False)
    annual_dividend_income = Column(Float, nullable=False)
    dividend_yield = Column(Float, nullable=False)
    dividend_growth_rate = Column(Float, nullable=True)

    # Metadata
    warnings = Column(Text, nullable=True)  # JSON array of warning strings
    errors = Column(Text, nullable=True)    # JSON array of error strings
    calculation_duration_ms = Column(Integer, nullable=True)

    __table_args__ = (
        Index('ix_snapshot_calculated_at_desc', 'calculated_at'),
    )


# Database initialization
def init_db():
    """Create all tables in the database"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
