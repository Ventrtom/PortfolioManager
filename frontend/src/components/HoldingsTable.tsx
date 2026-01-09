import type { Holding } from '../types';
import { formatCurrency, formatPercent, getColorForValue } from '../utils/formatters';

interface Props {
  holdings: Holding[];
}

const HoldingsTable = ({ holdings }: Props) => {
  if (holdings.length === 0) {
    return <p className="no-data">No holdings yet. Add your first transaction to get started!</p>;
  }

  return (
    <div className="table-container">
      <table className="holdings-table">
        <thead>
          <tr>
            <th>Ticker</th>
            <th>Company</th>
            <th>Quantity</th>
            <th>Avg Cost</th>
            <th>Current Price</th>
            <th>Market Value</th>
            <th>Gain/Loss</th>
            <th>Return %</th>
            <th>Sector</th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((holding) => (
            <tr key={holding.ticker}>
              <td className="ticker-cell">{holding.ticker}</td>
              <td>{holding.company_name || holding.ticker}</td>
              <td>{holding.quantity.toFixed(2)}</td>
              <td>{formatCurrency(holding.average_cost)}</td>
              <td>{formatCurrency(holding.current_price)}</td>
              <td className="value-cell">{formatCurrency(holding.market_value)}</td>
              <td style={{ color: getColorForValue(holding.unrealized_gain) }}>
                {formatCurrency(holding.unrealized_gain)}
              </td>
              <td style={{ color: getColorForValue(holding.unrealized_gain_percent) }}>
                {formatPercent(holding.unrealized_gain_percent)}
              </td>
              <td>{holding.sector || 'N/A'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default HoldingsTable;
