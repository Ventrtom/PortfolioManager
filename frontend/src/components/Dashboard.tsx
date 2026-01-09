import { useEffect, useState } from 'react';
import { portfolioAPI, analyticsAPI } from '../api/client';
import type { PortfolioSummary, Holding, IndustryAllocation, KPIResponse } from '../types';
import { formatCurrency, formatPercent, getColorForValue } from '../utils/formatters';
import HoldingsTable from './HoldingsTable';
import AllocationChart from './AllocationChart';
import PortfolioSummaryCard from './PortfolioSummaryCard';

const Dashboard = () => {
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [allocation, setAllocation] = useState<IndustryAllocation[]>([]);
  const [kpis, setKPIs] = useState<KPIResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);

      const [summaryData, holdingsData, allocationData, kpisData] = await Promise.all([
        portfolioAPI.getSummary(),
        portfolioAPI.getHoldings(),
        portfolioAPI.getIndustryAllocation(),
        analyticsAPI.getKPIs(),
      ]);

      setSummary(summaryData);
      setHoldings(holdingsData);
      setAllocation(allocationData);
      setKPIs(kpisData);
    } catch (err) {
      setError('Failed to load portfolio data. Make sure the backend is running.');
      console.error('Error fetching dashboard data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

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
        <button onClick={fetchData} className="refresh-btn">
          Refresh
        </button>
      </div>

      {summary && <PortfolioSummaryCard summary={summary} kpis={kpis} />}

      <div className="dashboard-grid">
        <div className="holdings-section">
          <h2>Current Holdings</h2>
          <HoldingsTable holdings={holdings} />
        </div>

        <div className="allocation-section">
          <h2>Industry Allocation</h2>
          <AllocationChart data={allocation} />
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
              <p>Total: {formatCurrency(kpis.dividends.total_dividends)}</p>
              <p>Annual Income: {formatCurrency(kpis.dividends.annual_dividend_income)}</p>
              <p>Yield: {kpis.dividends.dividend_yield.toFixed(2)}%</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Dashboard;
