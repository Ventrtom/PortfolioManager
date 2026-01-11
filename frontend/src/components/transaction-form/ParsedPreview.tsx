import React from 'react';
import type { ParsedTransaction } from '../../types';

interface ParsedPreviewProps {
  parsedTransaction: ParsedTransaction | null;
  parseError: string | null;
  parsingState: 'idle' | 'parsing' | 'success' | 'error';
}

const ParsedPreview: React.FC<ParsedPreviewProps> = ({
  parsedTransaction,
  parseError,
  parsingState
}) => {
  if (parsingState === 'idle') {
    return null;
  }

  if (parsingState === 'parsing') {
    return (
      <div className="parsing-indicator">
        <span className="parsing-indicator__spinner">⏳</span>
        <span>Parsing your input...</span>
      </div>
    );
  }

  if (parsingState === 'error' && parseError) {
    return (
      <div className="parsed-preview parsed-preview--error">
        <span className="parsed-preview__icon" aria-hidden="true">
          ⚠️
        </span>
        <div className="parsed-preview__details">
          <strong>Could not parse:</strong>
          <p>{parseError}</p>
          <small>Check the format examples above</small>
        </div>
      </div>
    );
  }

  if (parsingState === 'success' && parsedTransaction) {
    const formatAmount = (amount: number) => {
      return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD'
      }).format(Math.abs(amount));
    };

    const formatTransaction = () => {
      const type = parsedTransaction.transaction_type.toUpperCase();
      const ticker = parsedTransaction.ticker;
      const amount = formatAmount(parsedTransaction.total_amount);

      switch (type) {
        case 'BUY':
          return `BUY ${parsedTransaction.quantity} shares of ${ticker} @ ${formatAmount(parsedTransaction.price || 0)} on ${parsedTransaction.transaction_date}`;
        case 'SELL':
          return `SELL ${parsedTransaction.quantity} shares of ${ticker} @ ${formatAmount(parsedTransaction.price || 0)} on ${parsedTransaction.transaction_date}`;
        case 'DIVIDEND':
          return `DIVIDEND of ${amount} from ${ticker} on ${parsedTransaction.transaction_date}`;
        case 'FEE':
          return `FEE of ${amount}${ticker && ticker !== 'CASH' ? ` for ${ticker}` : ''} on ${parsedTransaction.transaction_date}`;
        case 'TAX':
          return `TAX of ${amount}${ticker && ticker !== 'CASH' ? ` for ${ticker}` : ''} on ${parsedTransaction.transaction_date}`;
        default:
          return `${type} transaction on ${parsedTransaction.transaction_date}`;
      }
    };

    return (
      <div className="parsed-preview parsed-preview--success">
        <span className="parsed-preview__icon" aria-hidden="true">
          ✅
        </span>
        <div className="parsed-preview__details">
          <strong>Parsed Successfully:</strong>
          <p>{formatTransaction()}</p>
          <p>Total: {formatAmount(parsedTransaction.total_amount)}</p>
        </div>
      </div>
    );
  }

  return null;
};

export default ParsedPreview;
