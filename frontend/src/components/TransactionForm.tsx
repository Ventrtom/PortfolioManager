import { useState } from 'react';
import { transactionAPI } from '../api/client';
import type { TransactionCreate, ParsedTransaction } from '../types';

interface Props {
  onSuccess: () => void;
}

const TransactionForm = ({ onSuccess }: Props) => {
  const [naturalLanguageInput, setNaturalLanguageInput] = useState('');
  const [parsed Transaction, setParsedTransaction] = useState<ParsedTransaction | null>(null);
  const [formData, setFormData] = useState<TransactionCreate>({
    transaction_type: 'BUY',
    ticker: '',
    quantity: 0,
    price: 0,
    total_amount: 0,
    transaction_date: new Date().toISOString().split('T')[0],
    notes: '',
  });
  const [useNaturalLanguage, setUseNaturalLanguage] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleParse = async () => {
    try {
      setError(null);
      setLoading(true);
      const parsed = await transactionAPI.parse(naturalLanguageInput);
      setParsedTransaction(parsed);

      // Populate form with parsed data
      setFormData({
        transaction_type: parsed.transaction_type,
        ticker: parsed.ticker,
        quantity: parsed.quantity || 0,
        price: parsed.price || 0,
        total_amount: parsed.total_amount,
        transaction_date: parsed.transaction_date,
        notes: '',
      });
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to parse transaction');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setError(null);
      setLoading(true);
      await transactionAPI.create(formData);

      // Reset form
      setNaturalLanguageInput('');
      setParsedTransaction(null);
      setFormData({
        transaction_type: 'BUY',
        ticker: '',
        quantity: 0,
        price: 0,
        total_amount: 0,
        transaction_date: new Date().toISOString().split('T')[0],
        notes: '',
      });

      onSuccess();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create transaction');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="transaction-form">
      <h2>Add Transaction</h2>

      <div className="form-toggle">
        <button
          className={useNaturalLanguage ? 'active' : ''}
          onClick={() => setUseNaturalLanguage(true)}
        >
          Natural Language
        </button>
        <button
          className={!useNaturalLanguage ? 'active' : ''}
          onClick={() => setUseNaturalLanguage(false)}
        >
          Manual Entry
        </button>
      </div>

      {error && <div className="error-message">{error}</div>}

      {useNaturalLanguage ? (
        <div className="natural-language-input">
          <label>
            Enter transaction (e.g., "BUY - AAPL - 100 - @150.50 - 01/15/2025"):
          </label>
          <input
            type="text"
            value={naturalLanguageInput}
            onChange={(e) => setNaturalLanguageInput(e.target.value)}
            placeholder="BUY - TICKER - QUANTITY - @PRICE - DATE"
          />
          <button onClick={handleParse} disabled={loading || !naturalLanguageInput}>
            Parse
          </button>

          {parsedTransaction && (
            <div className="parsed-preview">
              <h4>Parsed Transaction:</h4>
              <p>
                {parsedTransaction.transaction_type} {parsedTransaction.quantity} shares of{' '}
                {parsedTransaction.ticker} @ ${parsedTransaction.price?.toFixed(2)} on{' '}
                {new Date(parsedTransaction.transaction_date).toLocaleDateString()}
              </p>
            </div>
          )}
        </div>
      ) : null}

      <form onSubmit={handleSubmit} className="manual-form">
        <div className="form-group">
          <label>Type:</label>
          <select
            value={formData.transaction_type}
            onChange={(e) => setFormData({ ...formData, transaction_type: e.target.value })}
          >
            <option value="BUY">BUY</option>
            <option value="SELL">SELL</option>
            <option value="DIVIDEND">DIVIDEND</option>
            <option value="FEE">FEE</option>
            <option value="TAX">TAX</option>
          </select>
        </div>

        <div className="form-group">
          <label>Ticker:</label>
          <input
            type="text"
            value={formData.ticker}
            onChange={(e) => setFormData({ ...formData, ticker: e.target.value.toUpperCase() })}
            required
          />
        </div>

        {formData.transaction_type !== 'FEE' && formData.transaction_type !== 'TAX' && (
          <>
            <div className="form-group">
              <label>Quantity:</label>
              <input
                type="number"
                step="0.01"
                value={formData.quantity || ''}
                onChange={(e) => setFormData({ ...formData, quantity: parseFloat(e.target.value) })}
                required
              />
            </div>

            <div className="form-group">
              <label>Price:</label>
              <input
                type="number"
                step="0.01"
                value={formData.price || ''}
                onChange={(e) => setFormData({ ...formData, price: parseFloat(e.target.value) })}
                required
              />
            </div>
          </>
        )}

        <div className="form-group">
          <label>Total Amount:</label>
          <input
            type="number"
            step="0.01"
            value={formData.total_amount}
            onChange={(e) => setFormData({ ...formData, total_amount: parseFloat(e.target.value) })}
            required
          />
        </div>

        <div className="form-group">
          <label>Date:</label>
          <input
            type="date"
            value={formData.transaction_date}
            onChange={(e) => setFormData({ ...formData, transaction_date: e.target.value })}
            required
          />
        </div>

        <div className="form-group">
          <label>Notes:</label>
          <textarea
            value={formData.notes || ''}
            onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
          />
        </div>

        <button type="submit" disabled={loading} className="submit-btn">
          {loading ? 'Submitting...' : 'Add Transaction'}
        </button>
      </form>
    </div>
  );
};

export default TransactionForm;
