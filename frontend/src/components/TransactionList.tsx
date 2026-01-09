import { useEffect, useState } from 'react';
import { transactionAPI } from '../api/client';
import type { Transaction } from '../types';
import { formatCurrency, formatShortDate } from '../utils/formatters';

interface Props {
  refreshTrigger?: number;
}

const TransactionList = ({ refreshTrigger }: Props) => {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
            {transactions.map((txn) => (
              <tr key={txn.id}>
                <td>{formatShortDate(txn.transaction_date)}</td>
                <td>
                  <span className={`type-badge type-${txn.transaction_type.toLowerCase()}`}>
                    {txn.transaction_type}
                  </span>
                </td>
                <td className="ticker-cell">{txn.ticker}</td>
                <td>{txn.quantity ? txn.quantity.toFixed(2) : '-'}</td>
                <td>{txn.price ? formatCurrency(txn.price) : '-'}</td>
                <td>{formatCurrency(txn.total_amount)}</td>
                <td className="notes-cell">{txn.notes || '-'}</td>
                <td>
                  <button
                    onClick={() => handleDelete(txn.id)}
                    className="delete-btn"
                    title="Delete transaction"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default TransactionList;
