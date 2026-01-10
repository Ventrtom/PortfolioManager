import { useEffect, useState } from 'react';
import { transactionAPI } from '../api/client';
import type { Transaction, TransactionCreate } from '../types';
import { formatCurrency, formatShortDate } from '../utils/formatters';
import { validateTransactionEdit, formatValidationErrors } from '../utils/validation';

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

  const handleEdit = (txn: Transaction) => {
    setEditingId(txn.id);
    setEditData({
      transaction_type: txn.transaction_type,
      ticker: txn.ticker,
      quantity: txn.quantity ?? undefined,
      price: txn.price ?? undefined,
      total_amount: txn.total_amount,
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

      {validationError && (
        <div className="validation-error-banner">
          <strong>Validation Error:</strong> {validationError}
        </div>
      )}

      <div className="table-container">
        <table className="transactions-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Type</th>
              <th>Ticker</th>
              <th>Quantity</th>
              <th>Price</th>
              <th>Total Amount</th>
              <th>Notes</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {transactions.map((txn) => {
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
                      txn.price ? formatCurrency(txn.price) : '-'
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
                      formatCurrency(txn.total_amount)
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
    </div>
  );
};

export default TransactionList;
