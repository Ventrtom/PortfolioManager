/**
 * Client-side validation for transaction edits
 * Provides immediate feedback before sending to backend
 */
import type { TransactionCreate, FieldValidation, ValidationError } from '../types';
import { FieldState } from '../types';

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
  if (data.quantity !== undefined && data.quantity !== null) {
    if (data.quantity <= 0) {
      errors.push('Quantity must be positive');
    }
    if (!Number.isFinite(data.quantity)) {
      errors.push('Quantity must be a valid number');
    }
  }

  // Price validation
  if (data.price !== undefined && data.price !== null) {
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

/**
 * Validate a single field and return detailed validation result
 */
export const validateField = (
  fieldName: keyof TransactionCreate,
  value: any,
  formData: Partial<TransactionCreate>
): FieldValidation => {
  switch (fieldName) {
    case 'ticker':
      return validateTicker(value, formData);
    case 'quantity':
      return validateQuantity(value, formData);
    case 'price':
      return validatePrice(value, formData);
    case 'total_amount':
      return validateTotalAmount(value, formData);
    case 'transaction_date':
      return validateDate(value);
    case 'transaction_type':
      return validateTransactionType(value);
    default:
      return { state: FieldState.PRISTINE };
  }
};

/**
 * Validate ticker field
 */
const validateTicker = (value: any, formData: Partial<TransactionCreate>): FieldValidation => {
  const transactionType = formData.transaction_type?.toUpperCase();

  // Ticker is optional for FEE and TAX
  if (transactionType === 'FEE' || transactionType === 'TAX') {
    if (!value || value.trim() === '') {
      return { state: FieldState.VALID, message: 'Optional - defaults to CASH', icon: '' };
    }
  }

  // Ticker is required for BUY, SELL, DIVIDEND
  if (!value || value.trim() === '') {
    return { state: FieldState.INVALID, message: 'Ticker is required', icon: '❌' };
  }

  if (value.length > 10) {
    return { state: FieldState.INVALID, message: 'Ticker too long (max 10 chars)', icon: '❌' };
  }

  if (!/^[A-Z.]+$/.test(value)) {
    if (/^[a-z.]+$/.test(value)) {
      return { state: FieldState.WARNING, message: 'Will be converted to uppercase', icon: '⚠️' };
    }
    return { state: FieldState.WARNING, message: 'Ticker should contain only letters and dots', icon: '⚠️' };
  }

  return { state: FieldState.VALID, icon: '✅' };
};

/**
 * Validate quantity field
 */
const validateQuantity = (value: any, formData: Partial<TransactionCreate>): FieldValidation => {
  const transactionType = formData.transaction_type?.toUpperCase();

  // Quantity not needed for DIVIDEND, FEE, TAX
  if (transactionType === 'DIVIDEND' || transactionType === 'FEE' || transactionType === 'TAX') {
    return { state: FieldState.PRISTINE };
  }

  // Required for BUY and SELL
  if (value === undefined || value === null || value === '') {
    return { state: FieldState.INVALID, message: 'Quantity is required', icon: '❌' };
  }

  const numValue = Number(value);

  if (!Number.isFinite(numValue)) {
    return { state: FieldState.INVALID, message: 'Must be a valid number', icon: '❌' };
  }

  if (numValue <= 0) {
    return { state: FieldState.INVALID, message: 'Quantity must be positive', icon: '❌' };
  }

  return { state: FieldState.VALID, icon: '✅' };
};

/**
 * Validate price field
 */
const validatePrice = (value: any, formData: Partial<TransactionCreate>): FieldValidation => {
  const transactionType = formData.transaction_type?.toUpperCase();

  // Price not needed for DIVIDEND, FEE, TAX
  if (transactionType === 'DIVIDEND' || transactionType === 'FEE' || transactionType === 'TAX') {
    return { state: FieldState.PRISTINE };
  }

  // Required for BUY and SELL
  if (value === undefined || value === null || value === '') {
    return { state: FieldState.INVALID, message: 'Price is required', icon: '❌' };
  }

  const numValue = Number(value);

  if (!Number.isFinite(numValue)) {
    return { state: FieldState.INVALID, message: 'Must be a valid number', icon: '❌' };
  }

  if (numValue <= 0) {
    return { state: FieldState.INVALID, message: 'Price must be positive', icon: '❌' };
  }

  return { state: FieldState.VALID, icon: '✅' };
};

/**
 * Validate total_amount field
 */
const validateTotalAmount = (value: any, formData: Partial<TransactionCreate>): FieldValidation => {
  if (value === undefined || value === null || value === '') {
    return { state: FieldState.INVALID, message: 'Amount is required', icon: '❌' };
  }

  const numValue = Number(value);

  if (!Number.isFinite(numValue)) {
    return { state: FieldState.INVALID, message: 'Must be a valid number', icon: '❌' };
  }

  if (numValue === 0) {
    return { state: FieldState.INVALID, message: 'Amount cannot be zero', icon: '❌' };
  }

  const transactionType = formData.transaction_type?.toUpperCase();

  // Warning if sign doesn't match typical convention
  if (transactionType === 'BUY' || transactionType === 'DIVIDEND') {
    if (numValue < 0) {
      return { state: FieldState.WARNING, message: 'Amount is usually positive for this type', icon: '⚠️' };
    }
  }

  if (transactionType === 'SELL' || transactionType === 'FEE' || transactionType === 'TAX') {
    if (numValue > 0) {
      return { state: FieldState.WARNING, message: 'Amount is usually negative for this type', icon: '⚠️' };
    }
  }

  return { state: FieldState.VALID, icon: '✅' };
};

/**
 * Validate transaction_date field
 */
const validateDate = (value: any): FieldValidation => {
  if (!value) {
    return { state: FieldState.INVALID, message: 'Date is required', icon: '❌' };
  }

  const date = new Date(value);
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  if (isNaN(date.getTime())) {
    return { state: FieldState.INVALID, message: 'Invalid date format', icon: '❌' };
  }

  if (date > today) {
    return { state: FieldState.INVALID, message: 'Date cannot be in the future', icon: '❌' };
  }

  const tenYearsAgo = new Date();
  tenYearsAgo.setFullYear(tenYearsAgo.getFullYear() - 10);
  tenYearsAgo.setHours(0, 0, 0, 0);

  if (date < tenYearsAgo) {
    return { state: FieldState.INVALID, message: 'Date cannot be more than 10 years old', icon: '❌' };
  }

  return { state: FieldState.VALID, icon: '✅' };
};

/**
 * Validate transaction_type field
 */
const validateTransactionType = (value: any): FieldValidation => {
  const validTypes = ['BUY', 'SELL', 'DIVIDEND', 'FEE', 'TAX'];

  if (!value) {
    return { state: FieldState.INVALID, message: 'Transaction type is required', icon: '❌' };
  }

  if (!validTypes.includes(value.toUpperCase())) {
    return { state: FieldState.INVALID, message: 'Invalid transaction type', icon: '❌' };
  }

  return { state: FieldState.VALID, icon: '✅' };
};

/**
 * Validate all fields and return comprehensive result
 */
export const validateAllFields = (formData: Partial<TransactionCreate>): {
  valid: boolean;
  errors: ValidationError[];
  fieldValidations: Record<string, FieldValidation>;
} => {
  const fieldValidations: Record<string, FieldValidation> = {};
  const errors: ValidationError[] = [];

  const fieldsToValidate: Array<keyof TransactionCreate> = [
    'transaction_type',
    'ticker',
    'quantity',
    'price',
    'total_amount',
    'transaction_date'
  ];

  fieldsToValidate.forEach(fieldName => {
    const validation = validateField(fieldName, formData[fieldName], formData);
    fieldValidations[fieldName] = validation;

    if (validation.state === FieldState.INVALID) {
      errors.push({
        field: fieldName,
        message: validation.message || 'Invalid value'
      });
    }
  });

  return {
    valid: errors.length === 0,
    errors,
    fieldValidations
  };
};
