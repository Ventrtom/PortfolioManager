import type { TransactionTypeConfig } from '../types';

// Field configurations for each transaction type
export const TRANSACTION_FIELD_CONFIGS: Record<string, TransactionTypeConfig> = {
  BUY: {
    ticker: {
      visible: true,
      required: true,
      label: 'Stock Symbol',
      placeholder: 'e.g., AAPL, MSFT, GOOGL',
      helpText: 'Enter the stock ticker symbol you are buying (e.g., AAPL for Apple, MSFT for Microsoft). Use the official exchange symbol.'
    },
    quantity: {
      visible: true,
      required: true,
      label: 'Number of Shares',
      placeholder: 'e.g., 100',
      helpText: 'Enter the total number of shares you are purchasing. For fractional shares, use decimals (e.g., 10.5 shares).'
    },
    price: {
      visible: true,
      required: true,
      label: 'Price per Share',
      placeholder: 'e.g., 150.50',
      helpText: 'Enter the price you paid for each share in dollars. This is the execution price shown on your broker statement.'
    },
    total_amount: {
      visible: true,
      required: true,
      label: 'Total Amount',
      placeholder: 'Auto-calculated or enter manually',
      helpText: 'Total purchase cost (quantity × price). This is automatically calculated, but you can override it to include commissions or fees if needed.',
      autoCalculated: true
    },
    transaction_date: {
      visible: true,
      required: true,
      label: 'Transaction Date',
      placeholder: 'Select date',
      helpText: 'Select the trade execution date (when the buy order was filled), not the settlement date.'
    },
    notes: {
      visible: true,
      required: false,
      label: 'Notes',
      placeholder: 'Optional notes about this transaction',
      helpText: 'Add any extra context: order type (limit/market), investment thesis, or broker details.'
    }
  },
  SELL: {
    ticker: {
      visible: true,
      required: true,
      label: 'Stock Symbol',
      placeholder: 'e.g., AAPL, MSFT, GOOGL',
      helpText: 'Enter the stock ticker symbol you are selling (e.g., AAPL for Apple, MSFT for Microsoft).'
    },
    quantity: {
      visible: true,
      required: true,
      label: 'Number of Shares',
      placeholder: 'e.g., 50',
      helpText: 'Enter the total number of shares you are selling. For fractional shares, use decimals (e.g., 5.5 shares).'
    },
    price: {
      visible: true,
      required: true,
      label: 'Price per Share',
      placeholder: 'e.g., 155.00',
      helpText: 'Enter the price you received for each share in dollars. This is the execution price from your broker statement.'
    },
    total_amount: {
      visible: true,
      required: true,
      label: 'Total Amount',
      placeholder: 'Auto-calculated or enter manually',
      helpText: 'Total sale proceeds (quantity × price). Auto-calculated, but can be adjusted to account for commissions or fees deducted from proceeds.',
      autoCalculated: true
    },
    transaction_date: {
      visible: true,
      required: true,
      label: 'Transaction Date',
      placeholder: 'Select date',
      helpText: 'Select the trade execution date (when the sell order was filled), not the settlement date.'
    },
    notes: {
      visible: true,
      required: false,
      label: 'Notes',
      placeholder: 'Optional notes about this transaction',
      helpText: 'Add context such as: reason for selling, realized gain/loss, or tax considerations.'
    }
  },
  DIVIDEND: {
    ticker: {
      visible: true,
      required: true,
      label: 'Stock Symbol',
      placeholder: 'e.g., AAPL',
      helpText: 'Enter the ticker symbol of the stock that paid you the dividend (e.g., AAPL, MSFT, KO)'
    },
    quantity: {
      visible: false,
      required: false,
      label: '',
      placeholder: ''
    },
    price: {
      visible: false,
      required: false,
      label: '',
      placeholder: ''
    },
    total_amount: {
      visible: true,
      required: true,
      label: 'Dividend Amount',
      placeholder: 'e.g., 125.50',
      helpText: 'Enter the total dividend payment you received in dollars. This is the net amount deposited to your account after any withholding taxes. Enter as a positive number (e.g., 125.50 for $125.50)'
    },
    transaction_date: {
      visible: true,
      required: true,
      label: 'Payment Date',
      placeholder: 'Select date',
      helpText: 'Select the date when the dividend was actually paid/deposited into your account'
    },
    notes: {
      visible: true,
      required: false,
      label: 'Notes',
      placeholder: 'Optional notes about this dividend',
      helpText: 'Add any additional information, such as: dividend type (regular/special), per-share amount, or number of shares held'
    }
  },
  FEE: {
    ticker: {
      visible: true,
      required: false,
      label: 'Associated Stock (Optional)',
      placeholder: 'Leave blank for general fees',
      helpText: 'If this fee relates to a specific stock transaction, enter the ticker (e.g., AAPL). Leave blank for account fees, subscription fees, or general broker charges.'
    },
    quantity: {
      visible: false,
      required: false,
      label: '',
      placeholder: ''
    },
    price: {
      visible: false,
      required: false,
      label: '',
      placeholder: ''
    },
    total_amount: {
      visible: true,
      required: true,
      label: 'Fee Amount',
      placeholder: 'e.g., 9.99',
      helpText: 'Enter the fee amount as a positive number (e.g., 9.99 for $9.99). The system will automatically record it as a negative transaction reducing your portfolio value.'
    },
    transaction_date: {
      visible: true,
      required: true,
      label: 'Fee Date',
      placeholder: 'Select date',
      helpText: 'Select the date when this fee was charged to your account.'
    },
    notes: {
      visible: true,
      required: false,
      label: 'Notes',
      placeholder: 'Optional description of the fee',
      helpText: 'Describe what this fee is for: trading commission, platform subscription, wire transfer, data feed, margin interest, etc.'
    }
  },
  TAX: {
    ticker: {
      visible: true,
      required: false,
      label: 'Associated Stock (Optional)',
      placeholder: 'Leave blank for general taxes',
      helpText: 'If this tax relates to a specific stock dividend or transaction, enter the ticker (e.g., AAPL). Leave blank for general capital gains taxes or account-level withholding.'
    },
    quantity: {
      visible: false,
      required: false,
      label: '',
      placeholder: ''
    },
    price: {
      visible: false,
      required: false,
      label: '',
      placeholder: ''
    },
    total_amount: {
      visible: true,
      required: true,
      label: 'Tax Amount',
      placeholder: 'e.g., 50.00',
      helpText: 'Enter the tax amount as a positive number (e.g., 50.00 for $50.00). The system will automatically record it as a negative transaction. This tracks taxes paid, not tax liability.'
    },
    transaction_date: {
      visible: true,
      required: true,
      label: 'Tax Date',
      placeholder: 'Select date',
      helpText: 'Select the date when this tax was withheld or paid from your account.'
    },
    notes: {
      visible: true,
      required: false,
      label: 'Notes',
      placeholder: 'Optional description of the tax',
      helpText: 'Describe the tax type: dividend withholding, foreign tax, capital gains tax, wash sale adjustment, etc.'
    }
  }
};

// Natural language examples by transaction type
export const NATURAL_LANGUAGE_EXAMPLES: Record<string, string[]> = {
  BUY: [
    'BUY - AAPL - 100 - @150.50 - 01/15/2025',
    'BUY - MSFT - 50 - @380.25 - 2025-01-10',
    'BUY - GOOGL - 25 - @140.75 - 15.01.2025'
  ],
  SELL: [
    'SELL - AAPL - 50 - @155.00 - 01/20/2025',
    'SELL - TSLA - 100 - @250.50 - 2025-01-18',
    'SELL - NVDA - 10 - @520.00 - 18.01.2025'
  ],
  DIVIDEND: [
    'DIVIDEND - AAPL - 125.50 - 01/15/2025',
    'DIVIDEND - MSFT - 87.25 - 2025-01-10',
    'DIVIDEND - KO - 45.00 - 10.01.2025'
  ],
  FEE: [
    'FEE - - 9.99 - 01/15/2025',
    'FEE - AAPL - 5.00 - 2025-01-10',
    'FEE - - 12.50 - 15.01.2025'
  ],
  TAX: [
    'TAX - - 15.50 - 01/15/2025',
    'TAX - AAPL - 25.00 - 2025-01-10',
    'TAX - - 30.00 - 10.01.2025'
  ]
};

// Helper function to get field configuration for a transaction type
export const getFieldConfig = (transactionType: string, fieldName: string) => {
  return TRANSACTION_FIELD_CONFIGS[transactionType]?.[fieldName];
};

// Helper function to get all visible fields for a transaction type
export const getVisibleFields = (transactionType: string): string[] => {
  const config = TRANSACTION_FIELD_CONFIGS[transactionType];
  if (!config) return [];
  return Object.keys(config).filter(field => config[field].visible);
};

// Helper function to get all required fields for a transaction type
export const getRequiredFields = (transactionType: string): string[] => {
  const config = TRANSACTION_FIELD_CONFIGS[transactionType];
  if (!config) return [];
  return Object.keys(config).filter(field => config[field].visible && config[field].required);
};
