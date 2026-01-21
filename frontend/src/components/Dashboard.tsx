import { useEffect, useState } from 'react';
import { portfolioAPI, analyticsAPI } from '../api/client';
import type { PortfolioSummary, Holding, IndustryAllocation, KPIResponseWithMetadata, WidgetLoadingState } from '../types';
import { formatCurrency } from '../utils/formatters';
import HoldingsTable from './HoldingsTable';
import AllocationChart from './AllocationChart';
import PortfolioSummaryCard from './PortfolioSummaryCard';

const Dashboard = () => {
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [allocation, setAllocation] = useState<IndustryAllocation[]>([]);
  const [kpis, setKPIs] = useState<KPIResponseWithMetadata | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isRecalculating, setIsRecalculating] = useState(false);
  const [widgetLoading, setWidgetLoading] = useState<WidgetLoadingState>({});

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Only load cached KPIs on initial dashboard load (fast)
      // Holdings and allocation will be loaded on manual refresh
      const kpisData = await analyticsAPI.getKPIs('CZK');
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
      // After recalculation, fetch fresh KPIs in CZK
      const convertedKPIs = await analyticsAPI.getKPIs('CZK');
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

  // Individual widget refresh handlers
  const handleRefreshSummary = async () => {
    setWidgetLoading(prev => ({ ...prev, summary: true }));
    try {
      const summaryData = await portfolioAPI.getSummary();
      setSummary(summaryData);
    } catch (err) {
      console.error('Failed to refresh summary:', err);
    } finally {
      setWidgetLoading(prev => ({ ...prev, summary: false }));
    }
  };

  const handleRefreshDiversification = async () => {
    setWidgetLoading(prev => ({ ...prev, diversification: true }));
    try {
      const data = await analyticsAPI.getDiversification();
      if (kpis) {
        setKPIs({ ...kpis, diversification: data });
      }
    } catch (err) {
      console.error('Failed to refresh diversification:', err);
    } finally {
      setWidgetLoading(prev => ({ ...prev, diversification: false }));
    }
  };

  const handleRefreshVolatility = async () => {
    setWidgetLoading(prev => ({ ...prev, volatility: true }));
    try {
      const data = await analyticsAPI.getVolatility();
      if (kpis) {
        setKPIs({ ...kpis, volatility: data });
      }
    } catch (err) {
      console.error('Failed to refresh volatility:', err);
    } finally {
      setWidgetLoading(prev => ({ ...prev, volatility: false }));
    }
  };

  const handleRefreshDividends = async () => {
    setWidgetLoading(prev => ({ ...prev, dividends: true }));
    try {
      const data = await analyticsAPI.getDividends();
      if (kpis) {
        setKPIs({ ...kpis, dividends: data });
      }
    } catch (err) {
      console.error('Failed to refresh dividends:', err);
    } finally {
      setWidgetLoading(prev => ({ ...prev, dividends: false }));
    }
  };

  const handleRefreshHoldings = async () => {
    setWidgetLoading(prev => ({ ...prev, holdings: true }));
    try {
      const holdingsData = await portfolioAPI.getHoldings();
      setHoldings(holdingsData);
    } catch (err) {
      console.error('Failed to refresh holdings:', err);
    } finally {
      setWidgetLoading(prev => ({ ...prev, holdings: false }));
    }
  };

  const handleRefreshAllocation = async () => {
    setWidgetLoading(prev => ({ ...prev, allocation: true }));
    try {
      const allocationData = await portfolioAPI.getIndustryAllocation();
      setAllocation(allocationData);
    } catch (err) {
      console.error('Failed to refresh allocation:', err);
    } finally {
      setWidgetLoading(prev => ({ ...prev, allocation: false }));
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
        <div className="dashboard-actions">
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
            {isRecalculating ? 'Recalculating...' : 'Refresh All'}
          </button>
        </div>
      </div>

      {summary && (
        <div className="widget-section">
          <div className="widget-header">
            <h2>Portfolio Summary</h2>
            <button
              onClick={handleRefreshSummary}
              disabled={widgetLoading.summary}
              className="widget-refresh-btn"
            >
              {widgetLoading.summary ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>
          <PortfolioSummaryCard summary={summary} kpis={kpis} currency="CZK" />
        </div>
      )}

      <div className="dashboard-grid">
        <div className="holdings-section">
          <div className="widget-header">
            <h2>Current Holdings</h2>
            <button
              onClick={handleRefreshHoldings}
              disabled={widgetLoading.holdings}
              className="widget-refresh-btn"
            >
              {widgetLoading.holdings ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>
          {holdings.length > 0 ? (
            <HoldingsTable holdings={holdings} />
          ) : (
            <div className="no-data">
              <p>Click "Refresh" to load detailed holdings with current prices</p>
            </div>
          )}
        </div>

        <div className="allocation-section">
          <div className="widget-header">
            <h2>Industry Allocation</h2>
            <button
              onClick={handleRefreshAllocation}
              disabled={widgetLoading.allocation}
              className="widget-refresh-btn"
            >
              {widgetLoading.allocation ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>
          {allocation.length > 0 ? (
            <AllocationChart data={allocation} />
          ) : (
            <div className="no-data">
              <p>Click "Refresh" to load allocation data</p>
            </div>
          )}
        </div>
      </div>

      {kpis && (
        <div className="kpis-grid">
          <div className="kpi-card">
            <div className="kpi-card-header">
              <h3>Diversification</h3>
              <button
                onClick={handleRefreshDiversification}
                disabled={widgetLoading.diversification}
                className="widget-refresh-btn"
              >
                {widgetLoading.diversification ? 'Refreshing...' : 'Refresh'}
              </button>
            </div>
            <div className="kpi-content">
              <p>Holdings: {kpis.diversification.number_of_holdings}</p>
              <p>Sectors: {kpis.diversification.number_of_sectors}</p>
              <p>Largest Position: {kpis.diversification.largest_position_percent.toFixed(2)}%</p>
              <p>Top 5 Concentration: {kpis.diversification.top_5_concentration.toFixed(2)}%</p>
            </div>
          </div>

          <div className="kpi-card">
            <div className="kpi-card-header">
              <h3>Volatility</h3>
              <button
                onClick={handleRefreshVolatility}
                disabled={widgetLoading.volatility}
                className="widget-refresh-btn"
              >
                {widgetLoading.volatility ? 'Refreshing...' : 'Refresh'}
              </button>
            </div>
            <div className="kpi-content">
              <p>Daily: {(kpis.volatility.daily_volatility * 100).toFixed(2)}%</p>
              <p>Annualized: {(kpis.volatility.annualized_volatility * 100).toFixed(2)}%</p>
              {kpis.volatility.sharpe_ratio && (
                <p>Sharpe Ratio: {kpis.volatility.sharpe_ratio.toFixed(2)}</p>
              )}
            </div>
          </div>

          <div className="kpi-card">
            <div className="kpi-card-header">
              <h3>Dividends</h3>
              <button
                onClick={handleRefreshDividends}
                disabled={widgetLoading.dividends}
                className="widget-refresh-btn"
              >
                {widgetLoading.dividends ? 'Refreshing...' : 'Refresh'}
              </button>
            </div>
            <div className="kpi-content">
              <p>Total: {formatCurrency(kpis.dividends.total_dividends, 'CZK')}</p>
              <p>Annual Income: {formatCurrency(kpis.dividends.annual_dividend_income, 'CZK')}</p>
              <p>Yield: {kpis.dividends.dividend_yield.toFixed(2)}%</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Dashboard;
