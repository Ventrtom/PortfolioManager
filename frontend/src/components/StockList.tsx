import { useEffect, useState } from 'react';
import { stockAPI } from '../api/client';
import type { Stock, StockFilterCriteria } from '../types';

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
      alert('Enrichment triggered. Refresh in a few seconds.');
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to trigger enrichment');
    }
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

  const getStatusBadge = (status: string) => {
    const colors: { [key: string]: string } = {
      complete: 'status-complete',
      pending: 'status-pending',
      in_progress: 'status-inprogress',
      failed: 'status-failed',
      manual: 'status-manual',
    };
    return <span className={`status-badge ${colors[status]}`}>{status}</span>;
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

                  <td>{getStatusBadge(stock.enrichment_status)}</td>

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
    </div>
  );
};

export default StockList;
