import type { PortfolioSummary, KPIResponse } from '../types';
import { formatCurrency, formatPercent, getColorForValue } from '../utils/formatters';
import CalcTooltip from './CalcTooltip';

interface Props {
  summary: PortfolioSummary;
  kpis: KPIResponse | null;
  currency: string;
}

const PortfolioSummaryCard = ({ summary, currency }: Props) => {
  // Calculate total assets (stocks + cash)
  const totalAssets = summary.total_value + summary.cash_balance;
  const cashPercentage = totalAssets > 0 ? (summary.cash_balance / totalAssets) * 100 : 0;
  const stocksPercentage = totalAssets > 0 ? (summary.total_value / totalAssets) * 100 : 0;

  return (
    <div className="summary-cards">
      {/* Total Assets Card (NEW - stocks + cash) */}
      <div className="summary-card highlight">
        <h3>💰 Total Assets</h3>
        <p className="value-large">
          <CalcTooltip
            formula="Total Assets = Stock Value + Cash Balance"
            calculation={`${formatCurrency(summary.total_value, currency)} + ${formatCurrency(summary.cash_balance, currency)} = ${formatCurrency(totalAssets, currency)}`}
          >
            {formatCurrency(totalAssets, currency)}
          </CalcTooltip>
        </p>
        <p className="value-small">
          {formatPercent(stocksPercentage, 1)} stocks • {formatPercent(cashPercentage, 1)} cash
        </p>
      </div>

      {/* Stock Value (holdings only) */}
      <div className="summary-card">
        <h3>📊 Stock Value</h3>
        <p className="value-large">
          <CalcTooltip
            formula="Stock Value (CZK) = Σ(Quantity × Current Price × Today's Exchange Rate)"
            calculation={`Sum of all holdings' market values converted to CZK at today's exchange rate. Total: ${formatCurrency(summary.total_value, currency)}`}
          >
            {formatCurrency(summary.total_value, currency)}
          </CalcTooltip>
        </p>
        <p className="value-small">current holdings</p>
      </div>

      {/* Cash Balance */}
      <div className="summary-card">
        <h3>💵 Cash Balance</h3>
        <p className="value-large">
          <CalcTooltip
            formula="Cash Balance = Σ(DEPOSIT) − Σ(WITHDRAWAL) + Σ(DIVIDEND) + Σ(SELL) − Σ(BUY)"
            calculation={`Net cash from all transactions converted to CZK. Total: ${formatCurrency(summary.cash_balance, currency)}`}
          >
            {formatCurrency(summary.cash_balance, currency)}
          </CalcTooltip>
        </p>
        <p className="value-small">available funds</p>
      </div>

      {/* Unrealized Gain */}
      <div className="summary-card">
        <h3>📈 Unrealized Gain</h3>
        <p
          className="value-large"
          style={{ color: getColorForValue(summary.total_unrealized_gain) }}
        >
          <CalcTooltip
            formula="Unrealized Gain = Stock Value − Cost Basis"
            calculation={`${formatCurrency(summary.total_value, currency)} − ${formatCurrency(summary.total_cost_basis, currency)} = ${formatCurrency(summary.total_unrealized_gain, currency)}`}
          >
            {formatCurrency(summary.total_unrealized_gain, currency)}
          </CalcTooltip>
        </p>
        <p
          className="value-small"
          style={{ color: getColorForValue(summary.total_unrealized_gain_percent) }}
        >
          <CalcTooltip
            formula="Unrealized Gain % = (Unrealized Gain ÷ Cost Basis) × 100"
            calculation={`(${formatCurrency(summary.total_unrealized_gain, currency)} ÷ ${formatCurrency(summary.total_cost_basis, currency)}) × 100 = ${formatPercent(summary.total_unrealized_gain_percent)}`}
          >
            {formatPercent(summary.total_unrealized_gain_percent)}
          </CalcTooltip>
        </p>
      </div>

      {/* Realized Gain */}
      <div className="summary-card">
        <h3>💎 Realized Gain</h3>
        <p
          className="value-large"
          style={{ color: getColorForValue(summary.total_realized_gain) }}
        >
          <CalcTooltip
            formula="Realized Gain = Σ(Sale Proceeds − Cost Basis of Sold Shares)"
            calculation={`Sum of profits/losses from all SELL transactions using FIFO method. Total: ${formatCurrency(summary.total_realized_gain, currency)}`}
          >
            {formatCurrency(summary.total_realized_gain, currency)}
          </CalcTooltip>
        </p>
        <p className="value-small">from sales</p>
      </div>

      {/* Cost Basis */}
      <div className="summary-card">
        <h3>🏷️ Cost Basis</h3>
        <p className="value-large">
          <CalcTooltip
            formula="Cost Basis (CZK) = Σ(Purchase Amount × Exchange Rate at Transaction Date)"
            calculation={`Sum of all BUY transactions converted to CZK at each transaction's date using FIFO method. Total: ${formatCurrency(summary.total_cost_basis, currency)}`}
          >
            {formatCurrency(summary.total_cost_basis, currency)}
          </CalcTooltip>
        </p>
        <p className="value-small">total invested</p>
      </div>

      {/* Holdings Count */}
      <div className="summary-card">
        <h3>📦 Holdings</h3>
        <p className="value-large">
          <CalcTooltip
            formula="Holdings = Count of stocks with Quantity > 0"
            calculation={`Number of unique stocks currently held in portfolio: ${summary.number_of_holdings}`}
          >
            {summary.number_of_holdings}
          </CalcTooltip>
        </p>
        <p className="value-small">active positions</p>
      </div>
    </div>
  );
};

export default PortfolioSummaryCard;
