// Transaction types
export interface Transaction {
  id: number;
  transaction_type: 'BUY' | 'SELL' | 'DIVIDEND' | 'FEE' | 'TAX';
  ticker: string;
  quantity?: number | null;
  price?: number | null;
  total_amount: number;
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
  transaction_date: string;
  notes?: string | null;
}

export interface ParsedTransaction {
  transaction_type: string;
  ticker: string;
  quantity?: number | null;
  price?: number | null;
  total_amount: number;
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

// Stock types
export interface Stock {
  ticker: string;
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
  // Portfolio context
  holdings_quantity: number;
  holdings_value: number;
  cost_basis: number;
  unrealized_gain: number;
}

export interface StockFilterCriteria {
  search?: string;
  sector?: string;
  industry?: string;
  status?: string;
  has_holdings?: boolean;
}
