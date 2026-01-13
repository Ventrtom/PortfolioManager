import type { PortfolioSummary, KPIResponse } from '../types';
import { formatCurrency, formatPercent, getColorForValue } from '../utils/formatters';

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
        <p className="value-large">{formatCurrency(totalAssets, currency)}</p>
        <p className="value-small">
          {formatPercent(stocksPercentage, 1)} stocks • {formatPercent(cashPercentage, 1)} cash
        </p>
      </div>

      {/* Stock Value (holdings only) */}
      <div className="summary-card">
        <h3>📊 Stock Value</h3>
        <p className="value-large">{formatCurrency(summary.total_value, currency)}</p>
        <p className="value-small">current holdings</p>
      </div>

      {/* Cash Balance */}
      <div className="summary-card">
        <h3>💵 Cash Balance</h3>
        <p className="value-large">{formatCurrency(summary.cash_balance, currency)}</p>
        <p className="value-small">available funds</p>
      </div>

      {/* Unrealized Gain */}
      <div className="summary-card">
        <h3>📈 Unrealized Gain</h3>
        <p
          className="value-large"
          style={{ color: getColorForValue(summary.total_unrealized_gain) }}
        >
          {formatCurrency(summary.total_unrealized_gain, currency)}
        </p>
        <p
          className="value-small"
          style={{ color: getColorForValue(summary.total_unrealized_gain_percent) }}
        >
          {formatPercent(summary.total_unrealized_gain_percent)}
        </p>
      </div>

      {/* Realized Gain */}
      <div className="summary-card">
        <h3>💎 Realized Gain</h3>
        <p
          className="value-large"
          style={{ color: getColorForValue(summary.total_realized_gain) }}
        >
          {formatCurrency(summary.total_realized_gain, currency)}
        </p>
        <p className="value-small">from sales</p>
      </div>

      {/* Cost Basis */}
      <div className="summary-card">
        <h3>🏷️ Cost Basis</h3>
        <p className="value-large">{formatCurrency(summary.total_cost_basis, currency)}</p>
        <p className="value-small">total invested</p>
      </div>

      {/* Holdings Count */}
      <div className="summary-card">
        <h3>📦 Holdings</h3>
        <p className="value-large">{summary.number_of_holdings}</p>
        <p className="value-small">active positions</p>
      </div>
    </div>
  );
};

export default PortfolioSummaryCard;
