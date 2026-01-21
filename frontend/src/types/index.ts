// Currency types
export type Currency = 'USD' | 'EUR' | 'CZK';

// Widget loading state types
export type WidgetId = 'summary' | 'diversification' | 'volatility' | 'dividends' | 'holdings' | 'allocation';

export type WidgetLoadingState = {
  [key in WidgetId]?: boolean;
};

// Transaction types
export type TransactionType = 'BUY' | 'SELL' | 'DIVIDEND' | 'FEE' | 'TAX' | 'DEPOSIT' | 'WITHDRAWAL' | 'INTEREST' | 'SPLIT';

export type ExchangeRateStatus = 'complete' | 'partial' | 'pending_review';

export interface Transaction {
  id: number;
  transaction_type: TransactionType;
  ticker: string;
  quantity?: number | null;
  price?: number | null;
  total_amount: number;
  transaction_currency: Currency;
  amount_usd?: number | null;
  amount_eur?: number | null;
  amount_czk?: number | null;
  exchange_rate_status?: ExchangeRateStatus;
  exchange_rate_notes?: string | null;
  transaction_date: string;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

export interface TransactionCreate {
  transaction_type: string;
  ticker: string;
  quantity?: number | null;
  price?: number | null;
  total_amount: number;
  transaction_currency: Currency;
  transaction_date: string;
  notes?: string | null;
}

export interface ParsedTransaction {
  transaction_type: string;
  ticker: string;
  quantity?: number | null;
  price?: number | null;
  total_amount: number;
  transaction_currency?: Currency;
  transaction_date: string;
  raw_input: string;
}

// Form validation and configuration types
export const FieldState = {
  PRISTINE: 'pristine',
  TOUCHED: 'touched',
  VALIDATING: 'validating',
  VALID: 'valid',
  INVALID: 'invalid',
  WARNING: 'warning'
} as const;

export type FieldState = typeof FieldState[keyof typeof FieldState];

export interface FieldValidation {
  state: FieldState;
  message?: string;
  icon?: string;
}

export interface FieldConfig {
  visible: boolean;
  required: boolean;
  label: string;
  placeholder: string;
  helpText?: string;
  autoCalculated?: boolean;
}

export interface TransactionTypeConfig {
  [fieldName: string]: FieldConfig;
}

export interface ValidationError {
  field: string;
  message: string;
  code?: string;
}

// Portfolio types
export interface Holding {
  ticker: string;
  company_name?: string | null;
  quantity: number;
  average_cost: number;
  current_price: number;
  market_value: number;
  cost_basis: number;
  unrealized_gain: number;
  unrealized_gain_percent: number;
  sector?: string | null;
  industry?: string | null;
}

export interface PortfolioSummary {
  total_value: number;
  total_cost_basis: number;
  total_unrealized_gain: number;
  total_unrealized_gain_percent: number;
  total_realized_gain: number;
  cash_balance: number;
  number_of_holdings: number;
}

export interface IndustryAllocation {
  industry: string;
  value: number;
  percentage: number;
  count: number;
}

export interface SectorAllocation {
  sector: string;
  value: number;
  percentage: number;
  count: number;
}

// Analytics types
export interface PerformanceDataPoint {
  date: string;
  portfolio_value: number;
  total_return: number;
  total_return_percent: number;
}

export interface DiversificationMetrics {
  number_of_holdings: number;
  largest_position_percent: number;
  top_5_concentration: number;
  herfindahl_index: number;
  number_of_sectors: number;
  number_of_industries: number;
}

export interface VolatilityMetrics {
  daily_volatility: number;
  annualized_volatility: number;
  sharpe_ratio?: number | null;
}

export interface DividendSummary {
  total_dividends: number;
  annual_dividend_income: number;
  dividend_yield: number;
  dividend_growth_rate?: number | null;
}

export interface KPIResponse {
  portfolio_summary: PortfolioSummary;
  diversification: DiversificationMetrics;
  volatility: VolatilityMetrics;
  dividends: DividendSummary;
}

export interface SnapshotMetadata {
  calculated_at: string;
  calculation_duration_ms?: number;
}

export interface KPIResponseWithMetadata extends KPIResponse {
  metadata: SnapshotMetadata;
}

export interface SnapshotHistoryItem {
  id: number;
  calculated_at: string;
  total_value: number;
  unrealized_gain: number;
  unrealized_gain_percent: number;
  daily_volatility?: number;
  annualized_volatility?: number;
  sharpe_ratio?: number;
  dividend_yield: number;
}

// Stock types
export interface Stock {
  ticker: string;
  resolved_symbol: string | null;
  company_name: string | null;
  sector: string | null;
  industry: string | null;
  currency: string;
  market_cap: number | null;
  volume: number | null;
  enrichment_status: 'pending' | 'in_progress' | 'complete' | 'failed' | 'manual';
  enrichment_error: string | null;
  is_manually_edited: boolean;
  alternative_symbols: string[];
  last_updated: string | null;
  // Portfolio context - native currency (usually USD)
  holdings_quantity: number;
  holdings_value: number;  // Market value in native currency
  cost_basis: number;  // Cost basis in native currency
  unrealized_gain: number;  // Unrealized gain in native currency
  current_price: number | null;  // Current price in native currency
  average_cost: number | null;  // Average cost per share in native currency
  // Portfolio context - CZK (base currency for display)
  current_price_czk: number | null;  // Current price in CZK
  holdings_value_czk: number;  // Market value in CZK
  cost_basis_czk: number;  // Cost basis in CZK (at transaction dates)
  unrealized_gain_czk: number;  // Unrealized gain in CZK
  average_cost_czk: number | null;  // Average cost per share in CZK
  // Price fetch skip flags
  skip_price_fetch: boolean;
  skip_price_reason: string | null;
  skip_price_since: string | null;
  consecutive_failures: number;
}

export interface StockFilterCriteria {
  search?: string;
  sector?: string;
  industry?: string;
  status?: string;
  has_holdings?: boolean;
}

// Historical Price types
export interface HistoricalPrice {
  ticker: string;
  price_date: string;
  price: number;
}

export interface HistoricalPriceSeriesResponse {
  ticker: string;
  prices: HistoricalPrice[];
  count: number;
}
