import { useEffect, useState } from 'react';
import { stockAPI } from '../api/client';
import type { Stock, StockFilterCriteria } from '../types';
import ManualReviewChat from './ManualReviewChat';
import StockDetailDialog from './StockDetailDialog';

const StockList = () => {
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter states
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSector, setSelectedSector] = useState<string>('');
  const [selectedIndustry, setSelectedIndustry] = useState<string>('');
  const [selectedStatus, setSelectedStatus] = useState<string>('');
  const [showOnlyHoldings, setShowOnlyHoldings] = useState(false);

  // Edit state (inline editing for flagged stocks)
  const [editingTicker, setEditingTicker] = useState<string | null>(null);
  const [editData, setEditData] = useState<Partial<Stock>>({});
  const [saveLoading, setSaveLoading] = useState(false);

  // Create modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newTicker, setNewTicker] = useState('');
  const [createLoading, setCreateLoading] = useState(false);

  // Manual review chat state
  const [showManualReviewChat, setShowManualReviewChat] = useState(false);
  const [manualReviewTicker, setManualReviewTicker] = useState<string | null>(null);

  // Per-stock refresh state
  const [refreshingTicker, setRefreshingTicker] = useState<string | null>(null);

  // Stock detail dialog state
  const [detailStock, setDetailStock] = useState<Stock | null>(null);

  // Filter options
  const [sectors, setSectors] = useState<string[]>([]);
  const [industries, setIndustries] = useState<string[]>([]);

  const fetchStocks = async () => {
    try {
      setLoading(true);
      setError(null);

      const filters: StockFilterCriteria = {
        search: searchQuery || undefined,
        sector: selectedSector || undefined,
        industry: selectedIndustry || undefined,
        status: selectedStatus || undefined,
        has_holdings: showOnlyHoldings || undefined,
      };

      const data = await stockAPI.getAll(filters);
      setStocks(data);
    } catch (err) {
      setError('Failed to load stocks');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const fetchFilters = async () => {
    try {
      const [sectorData, industryData] = await Promise.all([
        stockAPI.getSectors(),
        stockAPI.getIndustries(),
      ]);
      setSectors(sectorData);
      setIndustries(industryData);
    } catch (err) {
      console.error('Failed to load filters:', err);
    }
  };

  useEffect(() => {
    fetchStocks();
    fetchFilters();
  }, []);

  useEffect(() => {
    fetchStocks();
  }, [searchQuery, selectedSector, selectedIndustry, selectedStatus, showOnlyHoldings]);

  const handleCreate = async () => {
    if (!newTicker.trim()) {
      alert('Please enter a ticker symbol');
      return;
    }

    try {
      setCreateLoading(true);
      await stockAPI.create(newTicker.toUpperCase());
      setShowCreateModal(false);
      setNewTicker('');
      fetchStocks();
      alert('Stock added! Enrichment running in background.');
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to create stock');
    } finally {
      setCreateLoading(false);
    }
  };

  const handleEdit = (stock: Stock) => {
    setEditingTicker(stock.ticker);
    setEditData({
      company_name: stock.company_name || '',
      sector: stock.sector || '',
      industry: stock.industry || '',
      market_cap: stock.market_cap || undefined,
      currency: stock.currency,
    });
  };

  const handleCancel = () => {
    setEditingTicker(null);
    setEditData({});
  };

  const handleSave = async (ticker: string) => {
    try {
      setSaveLoading(true);
      await stockAPI.update(ticker, editData);
      setEditingTicker(null);
      setEditData({});
      fetchStocks();
      alert('Stock updated successfully!');
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to update stock');
    } finally {
      setSaveLoading(false);
    }
  };

  const handleDelete = async (ticker: string) => {
    if (!confirm(`Delete ${ticker}? This will fail if transactions exist.`)) {
      return;
    }

    try {
      await stockAPI.delete(ticker);
      fetchStocks();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to delete stock');
    }
  };

  const handleRetryEnrichment = async (ticker: string) => {
    try {
      await stockAPI.triggerEnrichment(ticker);
      fetchStocks();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to trigger enrichment');
    }
  };

  const handleRefreshStock = async (ticker: string) => {
    if (refreshingTicker) return; // Prevent multiple concurrent refreshes

    setRefreshingTicker(ticker);
    try {
      const updatedStock = await stockAPI.triggerEnrichment(ticker);
      // Update just this stock in the list
      setStocks((prev) => prev.map((s) => (s.ticker === ticker ? updatedStock : s)));
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to refresh stock data');
    } finally {
      setRefreshingTicker(null);
    }
  };

  const formatRelativeTime = (dateString: string | null): string => {
    if (!dateString) return 'Never';
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays}d ago`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
    return date.toLocaleDateString();
  };

  const updateEditField = (field: keyof Stock, value: any) => {
    setEditData((prev) => ({ ...prev, [field]: value }));
  };

  const formatCurrency = (value: number | null): string => {
    if (value === null) return '-';
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value);
  };

  const formatNumber = (value: number | null): string => {
    if (value === null) return '-';
    return new Intl.NumberFormat('en-US').format(value);
  };

  const getColorForValue = (value: number): string => {
    if (value > 0) return 'var(--color-profit)';
    if (value < 0) return 'var(--color-loss)';
    return 'inherit';
  };

  const handleOpenManualReview = (ticker: string) => {
    setManualReviewTicker(ticker);
    setShowManualReviewChat(true);
  };

  const handleCloseManualReview = () => {
    setShowManualReviewChat(false);
    setManualReviewTicker(null);
  };

  const handleManualReviewResolved = () => {
    // Refresh stocks after manual review completes
    fetchStocks();
  };

  const handleOpenDetail = (stock: Stock) => {
    setDetailStock(stock);
  };

  const handleCloseDetail = () => {
    setDetailStock(null);
  };

  const handleStockUpdated = () => {
    // Refresh stocks after price edit in detail dialog
    fetchStocks();
  };

  const getStatusBadge = (stock: Stock) => {
    const status = stock.enrichment_status;
    const colors: { [key: string]: string } = {
      complete: 'status-complete',
      pending: 'status-pending',
      in_progress: 'status-inprogress',
      failed: 'status-failed',
      manual: 'status-manual',
    };

    const badge = <span className={`status-badge ${colors[status]}`}>{status}</span>;

    // Make MANUAL status clickable
    if (status === 'manual') {
      return (
        <span
          className="status-badge-wrapper clickable"
          onClick={() => handleOpenManualReview(stock.ticker)}
          title="Click to open AI chat and resolve this ticker manually"
        >
          {badge}
        </span>
      );
    }

    return badge;
  };

  if (loading) {
    return <div>Loading stocks...</div>;
  }

  if (error) {
    return <div className="error">{error}</div>;
  }

  return (
    <div className="stock-list">
      <div className="stock-list-header">
        <h2>Stock List</h2>
        <button onClick={() => setShowCreateModal(true)} className="create-btn">
          + Add Stock
        </button>
      </div>

      {/* Filter Bar */}
      <div className="filter-bar">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search by ticker or company name"
          className="search-input"
        />

        <select value={selectedSector} onChange={(e) => setSelectedSector(e.target.value)}>
          <option value="">All Sectors</option>
          {sectors.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>

        <select value={selectedIndustry} onChange={(e) => setSelectedIndustry(e.target.value)}>
          <option value="">All Industries</option>
          {industries.map((i) => (
            <option key={i} value={i}>
              {i}
            </option>
          ))}
        </select>

        <select value={selectedStatus} onChange={(e) => setSelectedStatus(e.target.value)}>
          <option value="">All Status</option>
          <option value="complete">Complete</option>
          <option value="pending">Pending</option>
          <option value="failed">Failed</option>
          <option value="manual">Manual</option>
        </select>

        <label>
          <input
            type="checkbox"
            checked={showOnlyHoldings}
            onChange={(e) => setShowOnlyHoldings(e.target.checked)}
          />
          Holdings Only
        </label>

        <button onClick={fetchStocks} className="refresh-btn">
          Refresh
        </button>
      </div>

      {/* Stock Table */}
      <div className="table-container">
        <table className="stock-table">
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Company</th>
              <th>Sector</th>
              <th>Industry</th>
              <th>Market Cap</th>
              <th>Volume</th>
              <th>Holdings</th>
              <th>Value</th>
              <th>P&L</th>
              <th>Status</th>
              <th>Updated</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {stocks.map((stock) => {
              const isEditing = editingTicker === stock.ticker;
              const canEdit = stock.enrichment_status === 'failed' || stock.enrichment_status === 'manual';

              return (
                <tr key={stock.ticker} className={isEditing ? 'editing-row' : ''}>
                  <td>
                    <strong>{stock.ticker}</strong>
                    {stock.resolved_symbol && stock.resolved_symbol !== stock.ticker && (
                      <span className="resolved-ticker"> ({stock.resolved_symbol})</span>
                    )}
                  </td>

                  <td>
                    {isEditing ? (
                      <input
                        type="text"
                        value={(editData.company_name as string) || ''}
                        onChange={(e) => updateEditField('company_name', e.target.value)}
                        className="edit-input"
                      />
                    ) : (
                      stock.company_name || '-'
                    )}
                  </td>

                  <td>
                    {isEditing ? (
                      <input
                        type="text"
                        value={(editData.sector as string) || ''}
                        onChange={(e) => updateEditField('sector', e.target.value)}
                        className="edit-input"
                      />
                    ) : (
                      stock.sector || '-'
                    )}
                  </td>

                  <td>
                    {isEditing ? (
                      <input
                        type="text"
                        value={(editData.industry as string) || ''}
                        onChange={(e) => updateEditField('industry', e.target.value)}
                        className="edit-input"
                      />
                    ) : (
                      stock.industry || '-'
                    )}
                  </td>

                  <td>
                    {isEditing ? (
                      <input
                        type="number"
                        value={editData.market_cap || ''}
                        onChange={(e) => updateEditField('market_cap', parseFloat(e.target.value))}
                        className="edit-input"
                      />
                    ) : (
                      formatCurrency(stock.market_cap)
                    )}
                  </td>

                  <td>{stock.volume ? formatNumber(stock.volume) : '-'}</td>

                  <td>
                    {stock.holdings_quantity > 0 ? stock.holdings_quantity.toFixed(2) : '-'}
                  </td>
                  <td>
                    {stock.holdings_value > 0 ? formatCurrency(stock.holdings_value) : '-'}
                  </td>
                  <td style={{ color: getColorForValue(stock.unrealized_gain) }}>
                    {stock.unrealized_gain !== 0 ? formatCurrency(stock.unrealized_gain) : '-'}
                  </td>

                  <td>{getStatusBadge(stock)}</td>

                  <td>
                    <span
                      className={`last-updated-cell ${refreshingTicker === stock.ticker ? 'refreshing' : ''}`}
                      onClick={() => handleRefreshStock(stock.ticker)}
                      title={`Click to refresh data. Last updated: ${stock.last_updated || 'Never'}`}
                    >
                      {refreshingTicker === stock.ticker ? (
                        <span className="refresh-spinner">Refreshing...</span>
                      ) : (
                        formatRelativeTime(stock.last_updated)
                      )}
                    </span>
                  </td>

                  <td>
                    {isEditing ? (
                      <div className="edit-actions">
                        <button
                          onClick={() => handleSave(stock.ticker)}
                          className="save-btn"
                          disabled={saveLoading}
                        >
                          {saveLoading ? 'Saving...' : 'Save'}
                        </button>
                        <button onClick={handleCancel} className="cancel-btn" disabled={saveLoading}>
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <div className="row-actions">
                        <button
                          onClick={() => handleOpenDetail(stock)}
                          className="detail-btn"
                          title="View stock details"
                        >
                          Details
                        </button>
                        {canEdit && (
                          <button
                            onClick={() => handleEdit(stock)}
                            className="edit-btn"
                            title="Edit manually"
                          >
                            Edit
                          </button>
                        )}
                        {stock.enrichment_status === 'failed' && (
                          <button
                            onClick={() => handleRetryEnrichment(stock.ticker)}
                            className="retry-btn"
                            title="Retry enrichment"
                          >
                            Retry
                          </button>
                        )}
                        {stock.holdings_quantity === 0 && (
                          <button
                            onClick={() => handleDelete(stock.ticker)}
                            className="delete-btn"
                            title="Delete"
                          >
                            Delete
                          </button>
                        )}
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {stocks.length === 0 && <p className="no-data">No stocks found. Create one to get started!</p>}

      {/* Create Modal */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h3>Add New Stock</h3>
            <input
              type="text"
              value={newTicker}
              onChange={(e) => setNewTicker(e.target.value.toUpperCase())}
              placeholder="Ticker symbol (e.g., AAPL, GEO.US)"
              className="modal-input"
              autoFocus
            />
            <div className="modal-actions">
              <button onClick={handleCreate} className="create-btn" disabled={createLoading}>
                {createLoading ? 'Creating...' : 'Create'}
              </button>
              <button onClick={() => setShowCreateModal(false)} className="cancel-btn">
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Manual Review Chat */}
      {showManualReviewChat && manualReviewTicker && (
        <ManualReviewChat
          ticker={manualReviewTicker}
          onClose={handleCloseManualReview}
          onResolved={handleManualReviewResolved}
        />
      )}

      {/* Stock Detail Dialog */}
      {detailStock && (
        <StockDetailDialog
          stock={detailStock}
          onClose={handleCloseDetail}
          onStockUpdated={handleStockUpdated}
        />
      )}
    </div>
  );
};

export default StockList;
