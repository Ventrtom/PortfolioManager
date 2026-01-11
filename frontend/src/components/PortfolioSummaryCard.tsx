import type { PortfolioSummary, KPIResponse } from '../types';
import { formatCurrency, formatPercent, getColorForValue } from '../utils/formatters';

interface Props {
  summary: PortfolioSummary;
  kpis: KPIResponse | null;
}

const PortfolioSummaryCard = ({ summary }: Props) => {
  return (
    <div className="summary-cards">
      <div className="summary-card">
        <h3>Total Value</h3>
        <p className="value-large">{formatCurrency(summary.total_value)}</p>
      </div>

      <div className="summary-card">
        <h3>Total Return</h3>
        <p
          className="value-large"
          style={{ color: getColorForValue(summary.total_unrealized_gain) }}
        >
          {formatCurrency(summary.total_unrealized_gain)}
        </p>
        <p
          className="value-small"
          style={{ color: getColorForValue(summary.total_unrealized_gain_percent) }}
        >
          {formatPercent(summary.total_unrealized_gain_percent)}
        </p>
      </div>

      <div className="summary-card">
        <h3>Cost Basis</h3>
        <p className="value-large">{formatCurrency(summary.total_cost_basis)}</p>
      </div>

      <div className="summary-card">
        <h3>Holdings</h3>
        <p className="value-large">{summary.number_of_holdings}</p>
        <p className="value-small">positions</p>
      </div>

      <div className="summary-card">
        <h3>Cash Balance</h3>
        <p className="value-large">{formatCurrency(summary.cash_balance)}</p>
      </div>
    </div>
  );
};

export default PortfolioSummaryCard;
