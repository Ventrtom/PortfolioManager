import { useState, useEffect, useCallback } from 'react';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip as ChartTooltip,
  Legend,
  Filler,
} from 'chart.js';
import { stockAPI } from '../api/client';
import type { Stock, HistoricalPrice } from '../types';
import CalcTooltip from './CalcTooltip';
import './StockDetailDialog.css';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  ChartTooltip,
  Legend,
  Filler
);

interface StockDetailDialogProps {
  stock: Stock;
  onClose: () => void;
  onStockUpdated?: () => void;
}

type TabType = 'info' | 'chart' | 'edit';
type DateRangeType = '1M' | '3M' | '6M' | '1Y' | 'ALL';

const StockDetailDialog = ({ stock, onClose, onStockUpdated }: StockDetailDialogProps) => {
  const [activeTab, setActiveTab] = useState<TabType>('info');
  const [historicalPrices, setHistoricalPrices] = useState<HistoricalPrice[]>([]);
  const [loadingPrices, setLoadingPrices] = useState(false);
  const [priceError, setPriceError] = useState<string | null>(null);
  const [dateRange, setDateRange] = useState<DateRangeType>('1Y');

  // Add/edit price state
  const [newPriceDate, setNewPriceDate] = useState('');
  const [newPriceValue, setNewPriceValue] = useState('');
  const [editingDate, setEditingDate] = useState<string | null>(null);
  const [editingPrice, setEditingPrice] = useState('');
  const [saving, setSaving] = useState(false);

  const getDateRange = useCallback((range: DateRangeType): { start: string; end: string } => {
    const end = new Date();
    const start = new Date();

    switch (range) {
      case '1M':
        start.setMonth(start.getMonth() - 1);
        break;
      case '3M':
        start.setMonth(start.getMonth() - 3);
        break;
      case '6M':
        start.setMonth(start.getMonth() - 6);
        break;
      case '1Y':
        start.setFullYear(start.getFullYear() - 1);
        break;
      case 'ALL':
        start.setFullYear(start.getFullYear() - 10);
        break;
    }

    return {
      start: start.toISOString().split('T')[0],
      end: end.toISOString().split('T')[0],
    };
  }, []);

  const fetchPrices = useCallback(async () => {
    setLoadingPrices(true);
    setPriceError(null);

    try {
      const { start, end } = getDateRange(dateRange);
      const response = await stockAPI.getHistoricalPrices(stock.ticker, start, end);
      setHistoricalPrices(response.prices);
    } catch (err: any) {
      setPriceError(err.response?.data?.detail || 'Failed to load historical prices');
    } finally {
      setLoadingPrices(false);
    }
  }, [stock.ticker, dateRange, getDateRange]);

  useEffect(() => {
    if (activeTab === 'chart' || activeTab === 'edit') {
      fetchPrices();
    }
  }, [activeTab, fetchPrices]);

  const handleAddPrice = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPriceDate || !newPriceValue) return;

    setSaving(true);
    try {
      await stockAPI.addHistoricalPrice(stock.ticker, newPriceDate, parseFloat(newPriceValue));
      setNewPriceDate('');
      setNewPriceValue('');
      await fetchPrices();
      onStockUpdated?.();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to add price');
    } finally {
      setSaving(false);
    }
  };

  const handleUpdatePrice = async (priceDate: string) => {
    if (!editingPrice) return;

    setSaving(true);
    try {
      await stockAPI.updateHistoricalPrice(stock.ticker, priceDate, parseFloat(editingPrice));
      setEditingDate(null);
      setEditingPrice('');
      await fetchPrices();
      onStockUpdated?.();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to update price');
    } finally {
      setSaving(false);
    }
  };

  const handleDeletePrice = async (priceDate: string) => {
    if (!confirm(`Delete price for ${priceDate}?`)) return;

    try {
      await stockAPI.deleteHistoricalPrice(stock.ticker, priceDate);
      await fetchPrices();
      onStockUpdated?.();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to delete price');
    }
  };

  const startEdit = (price: HistoricalPrice) => {
    setEditingDate(price.price_date);
    setEditingPrice(price.price.toString());
  };

  const cancelEdit = () => {
    setEditingDate(null);
    setEditingPrice('');
  };

  const formatUSD = (value: number | null | undefined): string => {
    if (value === null || value === undefined) return '-';
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value);
  };

  const formatCZK = (value: number | null | undefined): string => {
    if (value === null || value === undefined) return '-';
    return new Intl.NumberFormat('cs-CZ', { style: 'currency', currency: 'CZK', maximumFractionDigits: 0 }).format(value);
  };

  // Format currency in native currency (for historical prices which are stored in native currency)
  const formatCurrency = formatUSD;

  const formatNumber = (value: number | null | undefined): string => {
    if (value === null || value === undefined) return '-';
    return new Intl.NumberFormat('en-US').format(value);
  };

  const formatMarketCap = (value: number | null | undefined): string => {
    if (value === null || value === undefined) return '-';
    if (value >= 1e12) return `$${(value / 1e12).toFixed(2)}T`;
    if (value >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
    if (value >= 1e6) return `$${(value / 1e6).toFixed(2)}M`;
    return formatCurrency(value);
  };

  const formatDate = (dateStr: string | null | undefined): string => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString();
  };

  const getStatusClass = (status: string): string => {
    const statusClasses: Record<string, string> = {
      complete: 'status-complete',
      pending: 'status-pending',
      in_progress: 'status-inprogress',
      failed: 'status-failed',
      manual: 'status-manual',
    };
    return statusClasses[status] || '';
  };

  const chartData = {
    labels: historicalPrices.map((p) => p.price_date),
    datasets: [
      {
        label: `${stock.ticker} Price`,
        data: historicalPrices.map((p) => p.price),
        borderColor: '#3b82f6',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        fill: true,
        tension: 0.1,
        pointRadius: 0,
        pointHoverRadius: 4,
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx: any) => `$${ctx.parsed.y.toFixed(2)}`,
        },
      },
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: { maxTicksLimit: 8 },
      },
      y: {
        grid: { color: '#e5e7eb' },
        ticks: {
          callback: (value: any) => `$${value}`,
        },
      },
    },
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="stock-detail-dialog" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="detail-header">
          <div className="header-info">
            <h2>{stock.ticker}</h2>
            {stock.company_name && <span className="company-name">{stock.company_name}</span>}
          </div>
          <button className="close-btn" onClick={onClose}>
            &times;
          </button>
        </div>

        {/* Tabs */}
        <div className="detail-tabs">
          <button
            className={`detail-tab ${activeTab === 'info' ? 'active' : ''}`}
            onClick={() => setActiveTab('info')}
          >
            Info
          </button>
          <button
            className={`detail-tab ${activeTab === 'chart' ? 'active' : ''}`}
            onClick={() => setActiveTab('chart')}
          >
            Chart
          </button>
          <button
            className={`detail-tab ${activeTab === 'edit' ? 'active' : ''}`}
            onClick={() => setActiveTab('edit')}
          >
            Edit Prices
          </button>
        </div>

        {/* Content */}
        <div className="detail-content">
          {/* Info Tab */}
          {activeTab === 'info' && (
            <div className="info-grid">
              <div className="info-card">
                <h4>Basic Info</h4>
                <div className="info-row">
                  <span className="info-label">Ticker</span>
                  <span className="info-value">{stock.ticker}</span>
                </div>
                {stock.resolved_symbol && stock.resolved_symbol !== stock.ticker && (
                  <div className="info-row">
                    <span className="info-label">Resolved Symbol</span>
                    <span className="info-value">{stock.resolved_symbol}</span>
                  </div>
                )}
                <div className="info-row">
                  <span className="info-label">Company</span>
                  <span className="info-value">{stock.company_name || '-'}</span>
                </div>
                <div className="info-row">
                  <span className="info-label">Sector</span>
                  <span className="info-value">{stock.sector || '-'}</span>
                </div>
                <div className="info-row">
                  <span className="info-label">Industry</span>
                  <span className="info-value">{stock.industry || '-'}</span>
                </div>
              </div>

              <div className="info-card">
                <h4>Market Data</h4>
                <div className="info-row">
                  <span className="info-label">Market Cap</span>
                  <span className="info-value">{formatMarketCap(stock.market_cap)}</span>
                </div>
                <div className="info-row">
                  <span className="info-label">Volume</span>
                  <span className="info-value">{formatNumber(stock.volume)}</span>
                </div>
                <div className="info-row">
                  <span className="info-label">Currency</span>
                  <span className="info-value">{stock.currency}</span>
                </div>
              </div>

              <div className="info-card">
                <h4>Holdings (CZK)</h4>
                <div className="info-row">
                  <span className="info-label">Quantity</span>
                  <span className="info-value">
                    <CalcTooltip
                      formula="Quantity = Total Bought − Total Sold (FIFO)"
                      calculation={`${formatNumber(stock.holdings_quantity)} shares held`}
                    >
                      {formatNumber(stock.holdings_quantity)}
                    </CalcTooltip>
                  </span>
                </div>
                <div className="info-row">
                  <span className="info-label">Current Price</span>
                  <span className="info-value">
                    {stock.current_price_czk ? (
                      <CalcTooltip
                        formula={`Current Price (CZK) = Current Price (${stock.currency}) × Today's Exchange Rate`}
                        calculation={`${formatUSD(stock.current_price)} → ${formatCZK(stock.current_price_czk)}`}
                      >
                        {formatCZK(stock.current_price_czk)}
                      </CalcTooltip>
                    ) : '-'}
                    <span className="native-price"> ({formatUSD(stock.current_price)})</span>
                  </span>
                </div>
                <div className="info-row">
                  <span className="info-label">Average Cost</span>
                  <span className="info-value">
                    {stock.average_cost_czk ? (
                      <CalcTooltip
                        formula="Average Cost (CZK) = Cost Basis (CZK) ÷ Quantity"
                        calculation={`${formatCZK(stock.cost_basis_czk)} ÷ ${formatNumber(stock.holdings_quantity)} = ${formatCZK(stock.average_cost_czk)}`}
                      >
                        {formatCZK(stock.average_cost_czk)}
                      </CalcTooltip>
                    ) : '-'}
                  </span>
                </div>
                <div className="info-row">
                  <span className="info-label">Market Value</span>
                  <span className="info-value">
                    <CalcTooltip
                      formula="Market Value (CZK) = Quantity × Current Price (CZK)"
                      calculation={`${formatNumber(stock.holdings_quantity)} × ${formatCZK(stock.current_price_czk)} = ${formatCZK(stock.holdings_value_czk)}`}
                    >
                      {formatCZK(stock.holdings_value_czk)}
                    </CalcTooltip>
                  </span>
                </div>
                <div className="info-row">
                  <span className="info-label">Cost Basis</span>
                  <span className="info-value">
                    <CalcTooltip
                      formula="Cost Basis (CZK) = Σ(Purchase Amount in CZK at transaction date) using FIFO"
                      calculation={`Total paid: ${formatCZK(stock.cost_basis_czk)} (converted at each transaction date)`}
                    >
                      {formatCZK(stock.cost_basis_czk)}
                    </CalcTooltip>
                  </span>
                </div>
                <div className="info-row">
                  <span className="info-label">Unrealized P&L</span>
                  <span className="info-value">
                    <CalcTooltip
                      formula="Unrealized P&L (CZK) = Market Value (CZK) − Cost Basis (CZK)"
                      calculation={`${formatCZK(stock.holdings_value_czk)} − ${formatCZK(stock.cost_basis_czk)} = ${formatCZK(stock.unrealized_gain_czk)}`}
                    >
                      <span style={{ color: stock.unrealized_gain_czk >= 0 ? '#10b981' : '#ef4444' }}>
                        {formatCZK(stock.unrealized_gain_czk)}
                        {stock.cost_basis_czk > 0 && (
                          <span className="pnl-percent">
                            {' '}({((stock.unrealized_gain_czk / stock.cost_basis_czk) * 100).toFixed(2)}%)
                          </span>
                        )}
                      </span>
                    </CalcTooltip>
                  </span>
                </div>
              </div>

              <div className="info-card">
                <h4>Status</h4>
                <div className="info-row">
                  <span className="info-label">Enrichment</span>
                  <span className={`info-value status-badge ${getStatusClass(stock.enrichment_status)}`}>
                    {stock.enrichment_status}
                  </span>
                </div>
                <div className="info-row">
                  <span className="info-label">Last Updated</span>
                  <span className="info-value">{formatDate(stock.last_updated)}</span>
                </div>
                <div className="info-row">
                  <span className="info-label">Skip Price Fetch</span>
                  <span className="info-value">{stock.skip_price_fetch ? 'Yes' : 'No'}</span>
                </div>
                {stock.skip_price_fetch && stock.skip_price_reason && (
                  <div className="info-row">
                    <span className="info-label">Skip Reason</span>
                    <span className="info-value">{stock.skip_price_reason}</span>
                  </div>
                )}
                <div className="info-row">
                  <span className="info-label">Consecutive Failures</span>
                  <span className="info-value">{stock.consecutive_failures}</span>
                </div>
              </div>
            </div>
          )}

          {/* Chart Tab */}
          {activeTab === 'chart' && (
            <div className="chart-section">
              <div className="chart-controls">
                {(['1M', '3M', '6M', '1Y', 'ALL'] as DateRangeType[]).map((range) => (
                  <button
                    key={range}
                    className={`range-btn ${dateRange === range ? 'active' : ''}`}
                    onClick={() => setDateRange(range)}
                  >
                    {range}
                  </button>
                ))}
                <button className="refresh-btn" onClick={fetchPrices} disabled={loadingPrices}>
                  {loadingPrices ? 'Loading...' : 'Refresh'}
                </button>
              </div>

              {priceError && (
                <div className="error-message">
                  {priceError}
                  <button onClick={fetchPrices} className="retry-btn">
                    Retry
                  </button>
                </div>
              )}

              {loadingPrices ? (
                <div className="loading-chart">Loading price data...</div>
              ) : historicalPrices.length > 0 ? (
                <div className="price-chart-container">
                  <Line data={chartData} options={chartOptions} />
                </div>
              ) : (
                <div className="no-data">No historical prices available for this period.</div>
              )}
            </div>
          )}

          {/* Edit Prices Tab */}
          {activeTab === 'edit' && (
            <div className="edit-section">
              <form className="price-form" onSubmit={handleAddPrice}>
                <div className="form-group">
                  <label>Date</label>
                  <input
                    type="date"
                    value={newPriceDate}
                    onChange={(e) => setNewPriceDate(e.target.value)}
                    max={new Date().toISOString().split('T')[0]}
                    required
                  />
                </div>
                <div className="form-group">
                  <label>Price ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    value={newPriceValue}
                    onChange={(e) => setNewPriceValue(e.target.value)}
                    placeholder="0.00"
                    required
                  />
                </div>
                <button type="submit" className="add-btn" disabled={saving}>
                  {saving ? 'Adding...' : 'Add Price'}
                </button>
              </form>

              {priceError && <div className="error-message">{priceError}</div>}

              {loadingPrices ? (
                <div className="loading">Loading prices...</div>
              ) : (
                <div className="price-table-container">
                  <table className="price-table">
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Price</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {historicalPrices.length === 0 ? (
                        <tr>
                          <td colSpan={3} className="no-data">
                            No historical prices found.
                          </td>
                        </tr>
                      ) : (
                        [...historicalPrices]
                          .sort((a, b) => b.price_date.localeCompare(a.price_date))
                          .map((price) => (
                            <tr key={price.price_date}>
                              <td>{price.price_date}</td>
                              <td>
                                {editingDate === price.price_date ? (
                                  <input
                                    type="number"
                                    step="0.01"
                                    min="0.01"
                                    value={editingPrice}
                                    onChange={(e) => setEditingPrice(e.target.value)}
                                    className="edit-input"
                                    autoFocus
                                  />
                                ) : (
                                  formatCurrency(price.price)
                                )}
                              </td>
                              <td className="actions-cell">
                                {editingDate === price.price_date ? (
                                  <>
                                    <button
                                      className="save-btn"
                                      onClick={() => handleUpdatePrice(price.price_date)}
                                      disabled={saving}
                                    >
                                      Save
                                    </button>
                                    <button className="cancel-btn" onClick={cancelEdit}>
                                      Cancel
                                    </button>
                                  </>
                                ) : (
                                  <>
                                    <button className="edit-btn" onClick={() => startEdit(price)}>
                                      Edit
                                    </button>
                                    <button
                                      className="delete-btn"
                                      onClick={() => handleDeletePrice(price.price_date)}
                                    >
                                      Delete
                                    </button>
                                  </>
                                )}
                              </td>
                            </tr>
                          ))
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default StockDetailDialog;
