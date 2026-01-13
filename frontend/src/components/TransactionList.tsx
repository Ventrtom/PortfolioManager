import { useEffect, useState, useMemo } from 'react';
import { transactionAPI } from '../api/client';
import type { Transaction, TransactionCreate, Currency } from '../types';
import { formatCurrency, formatShortDate } from '../utils/formatters';
import { validateTransactionEdit, formatValidationErrors } from '../utils/validation';
import CurrencySelector from './shared/CurrencySelector';

// Types for filtering and sorting
type SortColumn = 'transaction_date' | 'transaction_type' | 'ticker' | 'total_amount';
type SortDirection = 'asc' | 'desc';

interface FilterCriteria {
  type: string;
  dateFrom: string;
  dateTo: string;
  tickerSearch: string;
}

// Helper function to apply filters
const applyFilters = (transactions: Transaction[], filters: FilterCriteria): Transaction[] => {
  return transactions.filter(txn => {
    // Type filter
    if (filters.type && txn.transaction_type !== filters.type) {
      return false;
    }

    // Date range filter (inclusive)
    if (filters.dateFrom) {
      const txnDate = new Date(txn.transaction_date);
      const fromDate = new Date(filters.dateFrom);
      if (txnDate < fromDate) return false;
    }

    if (filters.dateTo) {
      const txnDate = new Date(txn.transaction_date);
      const toDate = new Date(filters.dateTo);
      toDate.setHours(23, 59, 59, 999); // End of day
      if (txnDate > toDate) return false;
    }

    // Ticker search (case-insensitive, substring match)
    if (filters.tickerSearch) {
      const search = filters.tickerSearch.toLowerCase().trim();
      const ticker = (txn.ticker || '').toLowerCase();
      if (!ticker.includes(search)) return false;
    }

    return true;
  });
};

// Helper function to apply sorting
const applySorting = (
  transactions: Transaction[],
  column: SortColumn | null,
  direction: SortDirection
): Transaction[] => {
  if (!column) {
    // Default sort: date descending
    return [...transactions].sort((a, b) =>
      new Date(b.transaction_date).getTime() - new Date(a.transaction_date).getTime()
    );
  }

  return [...transactions].sort((a, b) => {
    let comparison = 0;

    switch (column) {
      case 'transaction_date':
        comparison = new Date(a.transaction_date).getTime() -
                     new Date(b.transaction_date).getTime();
        break;

      case 'transaction_type':
        comparison = a.transaction_type.localeCompare(b.transaction_type);
        break;

      case 'ticker':
        const tickerA = a.ticker || '';
        const tickerB = b.ticker || '';
        comparison = tickerA.localeCompare(tickerB);
        break;

      case 'total_amount':
        comparison = a.total_amount - b.total_amount;
        break;
    }

    return direction === 'asc' ? comparison : -comparison;
  });
};

interface Props {
  refreshTrigger?: number;
}

const TransactionList = ({ refreshTrigger }: Props) => {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Edit mode state
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editData, setEditData] = useState<Partial<TransactionCreate>>({});
  const [saveLoading, setSaveLoading] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  // Filter state
  const [filterType, setFilterType] = useState<string>('');
  const [filterDateFrom, setFilterDateFrom] = useState<string>('');
  const [filterDateTo, setFilterDateTo] = useState<string>('');
  const [filterTicker, setFilterTicker] = useState<string>('');

  // Sort state
  const [sortColumn, setSortColumn] = useState<SortColumn | null>(null);
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

  const fetchTransactions = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await transactionAPI.getAll();
      setTransactions(data);
    } catch (err) {
      setError('Failed to load transactions');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTransactions();
  }, [refreshTrigger]);

  // Compute filtered and sorted transactions
  const processedTransactions = useMemo(() => {
    const filters = {
      type: filterType,
      dateFrom: filterDateFrom,
      dateTo: filterDateTo,
      tickerSearch: filterTicker
    };
    const filtered = applyFilters(transactions, filters);
    return applySorting(filtered, sortColumn, sortDirection);
  }, [transactions, filterType, filterDateFrom, filterDateTo, filterTicker, sortColumn, sortDirection]);

  const handleEdit = (txn: Transaction) => {
    setEditingId(txn.id);
    setEditData({
      transaction_type: txn.transaction_type,
      ticker: txn.ticker,
      quantity: txn.quantity ?? undefined,
      price: txn.price ?? undefined,
      total_amount: txn.total_amount,
      transaction_currency: txn.transaction_currency,
      transaction_date: txn.transaction_date,
      notes: txn.notes ?? '',
    });
    setValidationError(null);
  };

  const handleCancel = () => {
    setEditingId(null);
    setEditData({});
    setValidationError(null);
  };

  const handleSave = async (id: number) => {
    try {
      setSaveLoading(true);
      setValidationError(null);

      // Client-side validation
      const clientValidation = validateTransactionEdit(editData);
      if (!clientValidation.valid) {
        setValidationError(formatValidationErrors(clientValidation.errors));
        return;
      }

      // Call API to update
      await transactionAPI.update(id, editData);

      // Refresh list
      await fetchTransactions();

      // Exit edit mode
      setEditingId(null);
      setEditData({});

      alert('Transaction updated successfully!');
    } catch (err: any) {
      // Handle validation errors from backend
      if (err.response?.status === 400) {
        const detail = err.response.data.detail;
        if (typeof detail === 'object' && detail.message) {
          setValidationError(detail.message);
        } else {
          setValidationError(typeof detail === 'string' ? detail : 'Validation failed');
        }
      } else {
        setValidationError('Failed to update transaction');
      }
      console.error(err);
    } finally {
      setSaveLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this transaction?')) {
      return;
    }

    try {
      await transactionAPI.delete(id);
      fetchTransactions();
    } catch (err) {
      alert('Failed to delete transaction');
    }
  };

  const updateEditField = (field: keyof TransactionCreate, value: any) => {
    setEditData((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const handleSort = (column: SortColumn) => {
    if (sortColumn === column) {
      if (sortDirection === 'desc') {
        setSortDirection('asc');
      } else {
        // Third click resets to default
        setSortColumn(null);
        setSortDirection('desc');
      }
    } else {
      setSortColumn(column);
      setSortDirection('asc');
    }
  };

  const clearFilters = () => {
    setFilterType('');
    setFilterDateFrom('');
    setFilterDateTo('');
    setFilterTicker('');
  };

  if (loading) {
    return <div>Loading transactions...</div>;
  }

  if (error) {
    return <div className="error">{error}</div>;
  }

  if (transactions.length === 0) {
    return <p className="no-data">No transactions yet</p>;
  }

  return (
    <div className="transactions-list">
      <h2>Transaction History</h2>

      {/* Filter Bar */}
      <div className="transactions-filter-bar">
        <select
          className="form-select"
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
        >
          <option value="">All Types</option>
          <option value="BUY">BUY</option>
          <option value="SELL">SELL</option>
          <option value="DIVIDEND">DIVIDEND</option>
          <option value="FEE">FEE</option>
          <option value="TAX">TAX</option>
          <option value="DEPOSIT">DEPOSIT</option>
          <option value="WITHDRAWAL">WITHDRAWAL</option>
          <option value="INTEREST">INTEREST</option>
          <option value="SPLIT">SPLIT</option>
        </select>

        <div className="date-range">
          <span className="filter-label">From:</span>
          <input
            type="date"
            value={filterDateFrom}
            onChange={(e) => setFilterDateFrom(e.target.value)}
            className="edit-input date-input"
          />
        </div>

        <div className="date-range">
          <span className="filter-label">To:</span>
          <input
            type="date"
            value={filterDateTo}
            onChange={(e) => setFilterDateTo(e.target.value)}
            className="edit-input date-input"
          />
        </div>

        <input
          type="text"
          className="search-input"
          placeholder="Search ticker (e.g., AAPL)"
          value={filterTicker}
          onChange={(e) => setFilterTicker(e.target.value)}
        />

        <button onClick={clearFilters} className="cancel-btn">
          Clear Filters
        </button>

        <span className="results-count">
          Showing {processedTransactions.length} of {transactions.length}
        </span>
      </div>

      {/* Date Range Warning */}
      {filterDateFrom && filterDateTo && new Date(filterDateFrom) > new Date(filterDateTo) && (
        <div className="date-range-warning">
          From date is after To date
        </div>
      )}

      {validationError && (
        <div className="validation-error-banner">
          <strong>Validation Error:</strong> {validationError}
        </div>
      )}

      <div className="table-container">
        <table className="transactions-table">
          <thead>
            <tr>
              <th
                className={`sortable-header ${sortColumn === 'transaction_date' ? 'active' : ''}`}
                onClick={() => handleSort('transaction_date')}
              >
                Date {sortColumn === 'transaction_date' && (sortDirection === 'asc' ? ' ▲' : ' ▼')}
              </th>
              <th
                className={`sortable-header ${sortColumn === 'transaction_type' ? 'active' : ''}`}
                onClick={() => handleSort('transaction_type')}
              >
                Type {sortColumn === 'transaction_type' && (sortDirection === 'asc' ? ' ▲' : ' ▼')}
              </th>
              <th
                className={`sortable-header ${sortColumn === 'ticker' ? 'active' : ''}`}
                onClick={() => handleSort('ticker')}
              >
                Ticker {sortColumn === 'ticker' && (sortDirection === 'asc' ? ' ▲' : ' ▼')}
              </th>
              <th>Quantity</th>
              <th>Price</th>
              <th
                className={`sortable-header ${sortColumn === 'total_amount' ? 'active' : ''}`}
                onClick={() => handleSort('total_amount')}
              >
                Total Amount {sortColumn === 'total_amount' && (sortDirection === 'asc' ? ' ▲' : ' ▼')}
              </th>
              <th>Currency</th>
              <th>Notes</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {processedTransactions.map((txn) => {
              const isEditing = editingId === txn.id;

              return (
                <tr key={txn.id} className={isEditing ? 'editing-row' : ''}>
                  <td>
                    {isEditing ? (
                      <input
                        type="date"
                        value={editData.transaction_date || ''}
                        onChange={(e) => updateEditField('transaction_date', e.target.value)}
                        className="edit-input date-input"
                      />
                    ) : (
                      formatShortDate(txn.transaction_date)
                    )}
                  </td>

                  <td>
                    {isEditing ? (
                      <select
                        value={editData.transaction_type || ''}
                        onChange={(e) => updateEditField('transaction_type', e.target.value)}
                        className="edit-input"
                      >
                        <option value="BUY">BUY</option>
                        <option value="SELL">SELL</option>
                        <option value="DIVIDEND">DIVIDEND</option>
                        <option value="FEE">FEE</option>
                        <option value="TAX">TAX</option>
                        <option value="DEPOSIT">DEPOSIT</option>
                        <option value="WITHDRAWAL">WITHDRAWAL</option>
                        <option value="INTEREST">INTEREST</option>
                        <option value="SPLIT">SPLIT</option>
                      </select>
                    ) : (
                      <span className={`type-badge type-${txn.transaction_type.toLowerCase()}`}>
                        {txn.transaction_type}
                      </span>
                    )}
                  </td>

                  <td>
                    {isEditing ? (
                      <input
                        type="text"
                        value={editData.ticker || ''}
                        onChange={(e) => updateEditField('ticker', e.target.value.toUpperCase())}
                        className="edit-input ticker-input"
                      />
                    ) : (
                      <span className="ticker-cell">{txn.ticker}</span>
                    )}
                  </td>

                  <td>
                    {isEditing ? (
                      <input
                        type="number"
                        step="0.01"
                        value={editData.quantity ?? ''}
                        onChange={(e) => updateEditField('quantity', parseFloat(e.target.value) || undefined)}
                        className="edit-input number-input"
                      />
                    ) : (
                      txn.quantity ? txn.quantity.toFixed(2) : '-'
                    )}
                  </td>

                  <td>
                    {isEditing ? (
                      <input
                        type="number"
                        step="0.01"
                        value={editData.price ?? ''}
                        onChange={(e) => updateEditField('price', parseFloat(e.target.value) || undefined)}
                        className="edit-input number-input"
                      />
                    ) : (
                      txn.price ? formatCurrency(txn.price, txn.transaction_currency) : '-'
                    )}
                  </td>

                  <td>
                    {isEditing ? (
                      <input
                        type="number"
                        step="0.01"
                        value={editData.total_amount ?? ''}
                        onChange={(e) => updateEditField('total_amount', parseFloat(e.target.value) || 0)}
                        className="edit-input number-input"
                      />
                    ) : (
                      formatCurrency(txn.total_amount, txn.transaction_currency)
                    )}
                  </td>

                  <td>
                    {isEditing ? (
                      <CurrencySelector
                        value={editData.transaction_currency || 'CZK'}
                        onChange={(currency: Currency) => updateEditField('transaction_currency', currency)}
                      />
                    ) : (
                      <span className="currency-badge">{txn.transaction_currency}</span>
                    )}
                  </td>

                  <td>
                    {isEditing ? (
                      <input
                        type="text"
                        value={editData.notes || ''}
                        onChange={(e) => updateEditField('notes', e.target.value)}
                        className="edit-input notes-input"
                        placeholder="Optional notes"
                      />
                    ) : (
                      <span className="notes-cell">{txn.notes || '-'}</span>
                    )}
                  </td>

                  <td>
                    {isEditing ? (
                      <div className="edit-actions">
                        <button
                          onClick={() => handleSave(txn.id)}
                          className="save-btn"
                          disabled={saveLoading}
                        >
                          {saveLoading ? 'Saving...' : 'Save'}
                        </button>
                        <button
                          onClick={handleCancel}
                          className="cancel-btn"
                          disabled={saveLoading}
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <div className="row-actions">
                        <button
                          onClick={() => handleEdit(txn)}
                          className="edit-btn"
                          title="Edit transaction"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => handleDelete(txn.id)}
                          className="delete-btn"
                          title="Delete transaction"
                        >
                          Delete
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* No Results State */}
      {processedTransactions.length === 0 && transactions.length > 0 && (
        <div className="no-results-state">
          <h3>No transactions match your filters</h3>
          <p>Try adjusting your filter criteria or clear all filters.</p>
          <button onClick={clearFilters} className="cancel-btn">
            Clear All Filters
          </button>
        </div>
      )}
    </div>
  );
};

export default TransactionList;
