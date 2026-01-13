import React from 'react';
import type { Transaction, Currency } from '../../types';
import './MultiCurrencyDisplay.css';

interface MultiCurrencyDisplayProps {
  transaction: Transaction;
  mode?: 'primary' | 'all' | 'primary-with-usd';
}

const CURRENCY_SYMBOLS: Record<Currency, string> = {
  USD: '$',
  EUR: '€',
  CZK: 'Kč'
};

const formatAmount = (amount: number | null | undefined, currency: Currency, showCode: boolean = false): string => {
  if (amount === null || amount === undefined) {
    return 'N/A';
  }

  const symbol = CURRENCY_SYMBOLS[currency];
  const formatted = amount.toFixed(2);

  if (showCode) {
    return `${formatted} ${currency}`;
  }

  // For CZK, put symbol after the number
  if (currency === 'CZK') {
    return `${formatted} ${symbol}`;
  }

  // For USD and EUR, put symbol before
  return `${symbol}${formatted}`;
};

export const MultiCurrencyDisplay: React.FC<MultiCurrencyDisplayProps> = ({
  transaction,
  mode = 'primary-with-usd'
}) => {
  const { transaction_currency, amount_usd, amount_eur, amount_czk } = transaction;

  // Get primary amount based on transaction currency
  const primaryAmount = {
    USD: amount_usd,
    EUR: amount_eur,
    CZK: amount_czk
  }[transaction_currency];

  // If currency amounts are not available, fall back to total_amount
  const displayAmount = primaryAmount ?? transaction.total_amount;

  if (mode === 'primary') {
    return (
      <span className="currency-display primary">
        {formatAmount(displayAmount, transaction_currency)}
      </span>
    );
  }

  if (mode === 'primary-with-usd') {
    return (
      <div className="multi-currency-display">
        <span className="primary-amount">
          {formatAmount(displayAmount, transaction_currency)}
        </span>
        {transaction_currency !== 'USD' && amount_usd !== null && amount_usd !== undefined && (
          <span className="secondary-amount">
            ({formatAmount(amount_usd, 'USD')})
          </span>
        )}
      </div>
    );
  }

  // mode === 'all'
  return (
    <div className="multi-currency-display-all">
      <div className="currency-row">
        <span className="currency-label">USD:</span>
        <span className="currency-value">{formatAmount(amount_usd, 'USD')}</span>
      </div>
      <div className="currency-row">
        <span className="currency-label">EUR:</span>
        <span className="currency-value">{formatAmount(amount_eur, 'EUR')}</span>
      </div>
      <div className="currency-row">
        <span className="currency-label">CZK:</span>
        <span className="currency-value">{formatAmount(amount_czk, 'CZK')}</span>
      </div>
    </div>
  );
};

export default MultiCurrencyDisplay;
