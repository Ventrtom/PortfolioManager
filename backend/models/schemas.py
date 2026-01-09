from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import Optional


# Transaction schemas
class TransactionBase(BaseModel):
    transaction_type: str = Field(..., description="BUY, SELL, DIVIDEND, FEE, TAX")
    ticker: str
    quantity: Optional[float] = None
    price: Optional[float] = None
    total_amount: float
    transaction_date: date
    notes: Optional[str] = None


class TransactionCreate(TransactionBase):
    pass


class TransactionUpdate(BaseModel):
    transaction_type: Optional[str] = None
    ticker: Optional[str] = None
    quantity: Optional[float] = None
    price: Optional[float] = None
    total_amount: Optional[float] = None
    transaction_date: Optional[date] = None
    notes: Optional[str] = None


class TransactionResponse(TransactionBase):
    id: int
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


class StockResponse(StockBase):
    last_updated: Optional[datetime] = None

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
    cost_basis: float
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


# Parser schema
class ParsedTransaction(BaseModel):
    transaction_type: str
    ticker: str
    quantity: Optional[float] = None
    price: Optional[float] = None
    total_amount: float
    transaction_date: date
    raw_input: str
