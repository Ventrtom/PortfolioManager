import { useEffect, useState } from 'react';
import { portfolioAPI, analyticsAPI } from '../api/client';
import type { PortfolioSummary, Holding, IndustryAllocation, KPIResponseWithMetadata, Currency } from '../types';
import { formatCurrency } from '../utils/formatters';
import HoldingsTable from './HoldingsTable';
import AllocationChart from './AllocationChart';
import PortfolioSummaryCard from './PortfolioSummaryCard';
import CurrencySelector from './shared/CurrencySelector';

const Dashboard = () => {
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [allocation, setAllocation] = useState<IndustryAllocation[]>([]);
  const [kpis, setKPIs] = useState<KPIResponseWithMetadata | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isRecalculating, setIsRecalculating] = useState(false);
  const [selectedCurrency, setSelectedCurrency] = useState<Currency>('CZK');

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Only load cached KPIs on initial dashboard load (fast)
      // Holdings and allocation will be loaded on manual refresh
      const kpisData = await analyticsAPI.getKPIs(selectedCurrency);
      setKPIs(kpisData);

      // Derive summary from KPIs to avoid redundant calculations
      if (kpisData.portfolio_summary) {
        setSummary(kpisData.portfolio_summary);
      }
    } catch (err) {
      setError('Failed to load portfolio data. Make sure the backend is running.');
      console.error('Error fetching dashboard data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleRecalculate = async () => {
    try {
      setIsRecalculating(true);
      setError(null);

      const recalculatedKPIs = await analyticsAPI.recalculateKPIs();
      // After recalculation (always in CZK), fetch in selected currency
      const convertedKPIs = await analyticsAPI.getKPIs(selectedCurrency);
      setKPIs(convertedKPIs);

      // Also refresh other dashboard data
      const [summaryData, holdingsData, allocationData] = await Promise.all([
        portfolioAPI.getSummary(),
        portfolioAPI.getHoldings(),
        portfolioAPI.getIndustryAllocation(),
      ]);

      setSummary(summaryData);
      setHoldings(holdingsData);
      setAllocation(allocationData);
    } catch (err) {
      setError('Failed to recalculate KPIs');
      console.error('Error recalculating KPIs:', err);
    } finally {
      setIsRecalculating(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // Refetch KPIs when currency changes
  useEffect(() => {
    if (!loading && kpis) {
      const refetchKPIs = async () => {
        try {
          const kpisData = await analyticsAPI.getKPIs(selectedCurrency);
          setKPIs(kpisData);
          // Update summary from the new KPIs
          if (kpisData.portfolio_summary) {
            setSummary(kpisData.portfolio_summary);
          }
        } catch (err) {
          console.error('Error fetching KPIs in new currency:', err);
        }
      };
      refetchKPIs();
    }
  }, [selectedCurrency]);

  if (loading) {
    return <div className="loading">Loading portfolio data...</div>;
  }

  if (error) {
    return (
      <div className="error">
        <p>{error}</p>
        <button onClick={fetchData}>Retry</button>
      </div>
    );
  }

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h1>Portfolio Dashboard</h1>
        <div className="dashboard-actions">
          <CurrencySelector
            value={selectedCurrency}
            onChange={setSelectedCurrency}
          />
          {kpis?.metadata && (
            <span className="last-updated">
              Last updated: {new Date(kpis.metadata.calculated_at).toLocaleString()}
              {kpis.metadata.calculation_duration_ms && (
                <span className="duration"> ({kpis.metadata.calculation_duration_ms}ms)</span>
              )}
            </span>
          )}
          <button
            onClick={handleRecalculate}
            disabled={isRecalculating}
            className="refresh-button"
          >
            {isRecalculating ? 'Recalculating...' : 'Refresh Data'}
          </button>
        </div>
      </div>

      {kpis?.portfolio_summary?.conversion_warnings && (
        <div className="conversion-warning">
          <strong>⚠️ Exchange Rate Warning:</strong>
          <ul>
            {kpis.portfolio_summary.conversion_warnings.map((warning, idx) => (
              <li key={idx}>{warning}</li>
            ))}
          </ul>
        </div>
      )}

      {summary && <PortfolioSummaryCard summary={summary} kpis={kpis} currency={selectedCurrency} />}

      <div className="dashboard-grid">
        <div className="holdings-section">
          <h2>Current Holdings</h2>
          {holdings.length > 0 ? (
            <HoldingsTable holdings={holdings} />
          ) : (
            <div className="no-data">
              <p>Click "Refresh Data" to load detailed holdings with current prices</p>
            </div>
          )}
        </div>

        <div className="allocation-section">
          <h2>Industry Allocation</h2>
          {allocation.length > 0 ? (
            <AllocationChart data={allocation} />
          ) : (
            <div className="no-data">
              <p>Click "Refresh Data" to load allocation data</p>
            </div>
          )}
        </div>
      </div>

      {kpis && (
        <div className="kpis-grid">
          <div className="kpi-card">
            <h3>Diversification</h3>
            <div className="kpi-content">
              <p>Holdings: {kpis.diversification.number_of_holdings}</p>
              <p>Sectors: {kpis.diversification.number_of_sectors}</p>
              <p>Largest Position: {kpis.diversification.largest_position_percent.toFixed(2)}%</p>
              <p>Top 5 Concentration: {kpis.diversification.top_5_concentration.toFixed(2)}%</p>
            </div>
          </div>

          <div className="kpi-card">
            <h3>Volatility</h3>
            <div className="kpi-content">
              <p>Daily: {(kpis.volatility.daily_volatility * 100).toFixed(2)}%</p>
              <p>Annualized: {(kpis.volatility.annualized_volatility * 100).toFixed(2)}%</p>
              {kpis.volatility.sharpe_ratio && (
                <p>Sharpe Ratio: {kpis.volatility.sharpe_ratio.toFixed(2)}</p>
              )}
            </div>
          </div>

          <div className="kpi-card">
            <h3>Dividends</h3>
            <div className="kpi-content">
              <p>Total: {formatCurrency(kpis.dividends.total_dividends, kpis.portfolio_summary.currency || 'CZK')}</p>
              <p>Annual Income: {formatCurrency(kpis.dividends.annual_dividend_income, kpis.portfolio_summary.currency || 'CZK')}</p>
              <p>Yield: {kpis.dividends.dividend_yield.toFixed(2)}%</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Dashboard;
