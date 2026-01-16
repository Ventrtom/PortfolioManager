from pydantic import BaseModel, Field, validator
from datetime import date, datetime
from typing import Optional, Dict, List


# Transaction schemas
class TransactionBase(BaseModel):
    transaction_type: str = Field(..., description="BUY, SELL, DIVIDEND, FEE, TAX, DEPOSIT, WITHDRAWAL, INTEREST, SPLIT")
    ticker: Optional[str] = Field(default='', description="Stock ticker (empty for DEPOSIT/WITHDRAWAL/INTEREST)")
    quantity: Optional[float] = None
    price: Optional[float] = None
    total_amount: float
    transaction_currency: str = Field(default="CZK", description="USD, EUR, or CZK")
    transaction_date: date
    notes: Optional[str] = None

    @validator('transaction_type')
    def validate_transaction_type(cls, v):
        valid_types = ['BUY', 'SELL', 'DIVIDEND', 'FEE', 'TAX', 'DEPOSIT', 'WITHDRAWAL', 'INTEREST', 'SPLIT']
        if v and v.upper() not in valid_types:
            raise ValueError(f'Transaction type must be one of: {", ".join(valid_types)}')
        return v.upper() if v else None

    @validator('transaction_currency')
    def validate_currency(cls, v):
        if v and v.upper() not in ['USD', 'EUR', 'CZK']:
            raise ValueError('Currency must be USD, EUR, or CZK')
        return v.upper() if v else 'CZK'


class TransactionCreate(TransactionBase):
    # Migration/import flags to bypass validation
    skip_cash_validation: bool = Field(default=False, description="Skip cash balance validation (for migrations only)")
    skip_fifo_validation: bool = Field(default=False, description="Skip FIFO holdings validation (for migrations only)")
    skip_price_validation: bool = Field(default=False, description="Skip price validation (for migrations only)")
    skip_exchange_rate_conversion: bool = Field(default=False, description="Skip multi-currency conversion (for migrations with pre-converted amounts)")

    # Import tracking fields
    import_source: Optional[str] = Field(default=None, description="Source of import (e.g., 'broker_csv_import')")
    import_batch_id: Optional[str] = Field(default=None, description="Batch ID for grouped imports")
    broker_transaction_id: Optional[str] = Field(default=None, description="Original broker transaction ID")


class TransactionUpdate(BaseModel):
    transaction_type: Optional[str] = None
    ticker: Optional[str] = None
    quantity: Optional[float] = None
    price: Optional[float] = None
    total_amount: Optional[float] = None
    transaction_currency: Optional[str] = None
    transaction_date: Optional[date] = None
    notes: Optional[str] = None


class TransactionResponse(TransactionBase):
    id: int
    amount_usd: Optional[float] = None
    amount_eur: Optional[float] = None
    amount_czk: Optional[float] = None
    exchange_rate_status: Optional[str] = 'complete'  # 'complete', 'partial', 'pending_review'
    exchange_rate_notes: Optional[str] = None  # JSON with details about missing/flagged rates
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Stock schemas
class StockBase(BaseModel):
    ticker: str
    company_name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    currency: str = "USD"
    market_cap: Optional[float] = None
    volume: Optional[int] = None


class StockCreate(BaseModel):
    ticker: str


class StockUpdate(BaseModel):
    company_name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    market_cap: Optional[float] = None
    currency: Optional[str] = None


class StockResponse(StockBase):
    enrichment_status: str
    enrichment_error: Optional[str] = None
    is_manually_edited: bool
    alternative_symbols: List[str] = []
    last_updated: Optional[str] = None
    # Portfolio context
    holdings_quantity: float = 0
    holdings_value: float = 0
    cost_basis: float = 0
    unrealized_gain: float = 0
    # Price fetch skip flags
    skip_price_fetch: bool = False
    skip_price_reason: Optional[str] = None
    skip_price_since: Optional[datetime] = None
    consecutive_failures: int = 0

    class Config:
        from_attributes = True


# Portfolio schemas
class Holding(BaseModel):
    ticker: str
    company_name: Optional[str] = None
    quantity: float
    average_cost: float
    current_price: float
    market_value: float
    cost_basis: float  # Cost in stock's native currency
    cost_basis_czk: Optional[float] = None  # Cost normalized to CZK at transaction dates
    unrealized_gain: float
    unrealized_gain_percent: float
    sector: Optional[str] = None
    industry: Optional[str] = None


class PortfolioSummary(BaseModel):
    total_value: float
    total_cost_basis: float
    total_unrealized_gain: float
    total_unrealized_gain_percent: float
    total_realized_gain: float
    cash_balance: float
    number_of_holdings: int
    currency: str = "CZK"  # Base currency for all values
    conversion_warnings: Optional[List[str]] = None  # Exchange rate warnings


class IndustryAllocation(BaseModel):
    industry: str
    value: float
    percentage: float
    count: int


class SectorAllocation(BaseModel):
    sector: str
    value: float
    percentage: float
    count: int


# Analytics schemas
class PerformanceDataPoint(BaseModel):
    date: date
    portfolio_value: float
    total_return: float
    total_return_percent: float


class DiversificationMetrics(BaseModel):
    number_of_holdings: int
    largest_position_percent: float
    top_5_concentration: float
    herfindahl_index: float
    number_of_sectors: int
    number_of_industries: int


class VolatilityMetrics(BaseModel):
    daily_volatility: float
    annualized_volatility: float
    sharpe_ratio: Optional[float] = None
    data_frequency: Optional[str] = None  # 'daily', 'weekly', 'monthly', 'unknown'
    data_quality: Optional[str] = None  # 'high', 'medium', 'low', 'insufficient'
    warnings: Optional[List[str]] = None  # Calculation warnings


class DividendSummary(BaseModel):
    total_dividends: float
    annual_dividend_income: float
    dividend_yield: float
    dividend_growth_rate: Optional[float] = None


class KPIResponse(BaseModel):
    portfolio_summary: PortfolioSummary
    diversification: DiversificationMetrics
    volatility: VolatilityMetrics
    dividends: DividendSummary
    warnings: Optional[List[str]] = None  # Aggregated warnings from all KPIs
    errors: Optional[List[str]] = None  # Aggregated errors


class SnapshotMetadata(BaseModel):
    calculated_at: datetime
    calculation_duration_ms: Optional[int] = None


class KPIResponseWithMetadata(KPIResponse):
    metadata: SnapshotMetadata


class SnapshotHistoryItem(BaseModel):
    id: int
    calculated_at: datetime
    total_value: float
    unrealized_gain: float
    unrealized_gain_percent: float
    daily_volatility: Optional[float]
    annualized_volatility: Optional[float]
    sharpe_ratio: Optional[float]
    dividend_yield: float

    class Config:
        from_attributes = True


# Parser schema
class ParsedTransaction(BaseModel):
    transaction_type: str
    ticker: str
    quantity: Optional[float] = None
    price: Optional[float] = None
    total_amount: float
    transaction_date: date
    raw_input: str


# Validation schemas
class ValidationErrorDetail(BaseModel):
    field: Optional[str] = None
    message: str
    code: str
    metadata: Optional[Dict] = None


class ValidationResponse(BaseModel):
    valid: bool
    errors: List[ValidationErrorDetail] = []
    warnings: List[ValidationErrorDetail] = []


# Audit trail schemas
class TransactionHistoryResponse(BaseModel):
    id: int
    transaction_id: int
    transaction_type: str
    ticker: str
    quantity: Optional[float]
    price: Optional[float]
    total_amount: float
    transaction_date: date
    notes: Optional[str]
    change_type: str
    changed_by: Optional[str]
    changed_at: datetime
    changed_fields: Optional[str]

    class Config:
        from_attributes = True


# Currency refresh schemas
class CurrencyRefreshRequest(BaseModel):
    transaction_ids: Optional[List[int]] = None  # None = refresh all


class CurrencyRefreshResponse(BaseModel):
    updated: int
    failed: int
    errors: List[str] = []
