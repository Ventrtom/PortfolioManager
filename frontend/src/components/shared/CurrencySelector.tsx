import React from 'react';
import type { Currency } from '../../types';
import './CurrencySelector.css';

interface CurrencySelectorProps {
  value: Currency;
  onChange: (currency: Currency) => void;
  disabled?: boolean;
}

interface CurrencyInfo {
  code: Currency;
  symbol: string;
  name: string;
}

const CURRENCIES: CurrencyInfo[] = [
  { code: 'CZK', symbol: 'Kč', name: 'Czech Koruna' },
  { code: 'EUR', symbol: '€', name: 'Euro' },
  { code: 'USD', symbol: '$', name: 'US Dollar' },
];

export const CurrencySelector: React.FC<CurrencySelectorProps> = ({
  value,
  onChange,
  disabled = false,
}) => {
  return (
    <div className="currency-selector">
      {CURRENCIES.map((currency) => (
        <button
          key={currency.code}
          type="button"
          className={`currency-option ${value === currency.code ? 'active' : ''}`}
          onClick={() => onChange(currency.code)}
          disabled={disabled}
          title={currency.name}
        >
          <span className="currency-symbol">{currency.symbol}</span>
          <span className="currency-code">{currency.code}</span>
        </button>
      ))}
    </div>
  );
};

export default CurrencySelector;
