/**
 * Client-side validation for transaction edits
 * Provides immediate feedback before sending to backend
 */
import type { TransactionCreate } from '../types';

export interface ValidationResult {
  valid: boolean;
  errors: string[];
}

/**
 * Validate transaction edit data before submitting to API
 * Catches common errors client-side for better UX
 */
export const validateTransactionEdit = (
  data: Partial<TransactionCreate>
): ValidationResult => {
  const errors: string[] = [];

  // Date validation
  if (data.transaction_date) {
    const txnDate = new Date(data.transaction_date);
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    if (txnDate > today) {
      errors.push('Transaction date cannot be in the future');
    }

    // Check for very old dates (10 years)
    const tenYearsAgo = new Date();
    tenYearsAgo.setFullYear(tenYearsAgo.getFullYear() - 10);
    tenYearsAgo.setHours(0, 0, 0, 0);

    if (txnDate < tenYearsAgo) {
      errors.push('Transaction date cannot be more than 10 years old');
    }
  }

  // Quantity validation
  if (data.quantity !== undefined) {
    if (data.quantity <= 0) {
      errors.push('Quantity must be positive');
    }
    if (!Number.isFinite(data.quantity)) {
      errors.push('Quantity must be a valid number');
    }
  }

  // Price validation
  if (data.price !== undefined) {
    if (data.price <= 0) {
      errors.push('Price must be positive');
    }
    if (!Number.isFinite(data.price)) {
      errors.push('Price must be a valid number');
    }
  }

  // Total amount validation
  if (data.total_amount !== undefined) {
    if (data.total_amount === 0) {
      errors.push('Total amount cannot be zero');
    }
    if (!Number.isFinite(data.total_amount)) {
      errors.push('Total amount must be a valid number');
    }
  }

  // Ticker validation
  if (data.ticker !== undefined) {
    if (data.ticker.trim() === '') {
      errors.push('Ticker symbol cannot be empty');
    }
    if (data.ticker.length > 10) {
      errors.push('Ticker symbol too long (max 10 characters)');
    }
  }

  // Transaction type validation
  if (data.transaction_type !== undefined) {
    const validTypes = ['BUY', 'SELL', 'DIVIDEND', 'FEE', 'TAX'];
    if (!validTypes.includes(data.transaction_type.toUpperCase())) {
      errors.push('Invalid transaction type');
    }
  }

  return {
    valid: errors.length === 0,
    errors,
  };
};

/**
 * Format validation errors for display
 */
export const formatValidationErrors = (errors: string[]): string => {
  return errors.join('; ');
};
