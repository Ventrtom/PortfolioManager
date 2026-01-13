import { useState, useRef, useEffect } from 'react';
import { transactionAPI } from '../api/client';
import { FieldState } from '../types';
import type { TransactionCreate, ParsedTransaction, FieldValidation, ValidationError, Transaction } from '../types';
import { validateAllFields } from '../utils/validation';
import { useAutoCalculation } from '../hooks/useAutoCalculation';
import { getVisibleFields } from '../config/transactionFormConfig';
import NaturalLanguageInput from './transaction-form/NaturalLanguageInput';
import ManualEntryForm from './transaction-form/ManualEntryForm';
import MultiCurrencyDisplay from './shared/MultiCurrencyDisplay';

interface Props {
  onSuccess: () => void;
}

const TransactionForm = ({ onSuccess }: Props) => {
  // Form mode state
  const [useNaturalLanguage, setUseNaturalLanguage] = useState(true);

  // Natural language state
  const [naturalLanguageInput, setNaturalLanguageInput] = useState('');
  const [parsedTransaction, setParsedTransaction] = useState<ParsedTransaction | null>(null);
  const [parsingState, setParsingState] = useState<'idle' | 'parsing' | 'success' | 'error'>('idle');
  const [parseError, setParseError] = useState<string | null>(null);

  // Form data state
  const [formData, setFormData] = useState<Partial<TransactionCreate>>({
    transaction_type: 'BUY',
    ticker: '',
    quantity: 0,
    price: 0,
    total_amount: 0,
    transaction_currency: 'CZK', // Default to CZK
    transaction_date: new Date().toISOString().split('T')[0],
    notes: '',
  });

  // Validation state
  const [fieldValidations, setFieldValidations] = useState<Record<string, FieldValidation>>({});
  const [formErrors, setFormErrors] = useState<ValidationError[]>([]);

  // Auto-calculation state
  const [manuallyEditedFields, setManuallyEditedFields] = useState<Set<string>>(new Set());

  // General state
  const [error, setError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState(false);
  const [savedTransaction, setSavedTransaction] = useState<Transaction | null>(null);

  // Track previous transaction type for type change detection
  const previousType = useRef<string>(formData.transaction_type || 'BUY');

  // Field refs for scrolling
  const fieldRefs = useRef<Record<string, HTMLElement | null>>({});

  // Auto-calculation hook
  const { calculatedValue, calculationHint, shouldUpdate } = useAutoCalculation(
    formData,
    manuallyEditedFields
  );

  // Auto-update total_amount if calculation says we should
  useEffect(() => {
    if (shouldUpdate && calculatedValue !== null) {
      setFormData(prev => ({
        ...prev,
        total_amount: calculatedValue
      }));
    }
  }, [shouldUpdate, calculatedValue]);

  // Handle type change with confirmation
  const handleTypeChange = (newType: string) => {
    const currentVisibleFields = getVisibleFields(previousType.current);
    const newVisibleFields = getVisibleFields(newType);

    // Find fields that will be hidden
    const fieldsToHide = currentVisibleFields.filter(field => !newVisibleFields.includes(field));

    // Check if any of those fields have data
    const hasDataInHiddenFields = fieldsToHide.some(field => {
      const value = formData[field as keyof TransactionCreate];
      return value !== undefined && value !== null && value !== '' && value !== 0;
    });

    if (hasDataInHiddenFields) {
      const fieldNames = fieldsToHide.map(f => f.charAt(0).toUpperCase() + f.slice(1)).join(', ');
      const confirmed = window.confirm(
        `Changing to ${newType} will clear these fields: ${fieldNames}.\n\nDo you want to continue?`
      );

      if (!confirmed) {
        return; // Don't change type
      }
    }

    // Clear hidden fields and update type
    const updatedData = { ...formData, transaction_type: newType };
    fieldsToHide.forEach(field => {
      delete updatedData[field as keyof TransactionCreate];
    });

    setFormData(updatedData);
    setManuallyEditedFields(new Set()); // Reset manual edit tracking
    previousType.current = newType;

    // Clear validation for hidden fields
    const newValidations = { ...fieldValidations };
    fieldsToHide.forEach(field => {
      delete newValidations[field];
    });
    setFieldValidations(newValidations);
  };

  // Handle field changes
  const handleFieldChange = (fieldName: keyof TransactionCreate, value: any) => {
    setFormData(prev => ({ ...prev, [fieldName]: value }));

    // Track if user manually edited total_amount
    if (fieldName === 'total_amount') {
      setManuallyEditedFields(prev => new Set(prev).add(fieldName));
    }

    // Uppercase ticker automatically
    if (fieldName === 'ticker' && typeof value === 'string') {
      setFormData(prev => ({ ...prev, ticker: value.toUpperCase() }));
    }
  };

  // Handle field blur (validate immediately)
  const handleFieldBlur = (fieldName: keyof TransactionCreate) => {
    // Run validation on this field
    const result = validateAllFields({ ...formData, [fieldName]: formData[fieldName] });
    setFieldValidations(prev => ({
      ...prev,
      [fieldName]: result.fieldValidations[fieldName] || { state: FieldState.PRISTINE }
    }));
  };

  // Handle field focus
  const handleFieldFocus = () => {
    // Clear any form-level errors when user starts editing
    if (formErrors.length > 0) {
      setFormErrors([]);
    }
  };

  // Handle natural language parsing
  const handleParse = async () => {
    try {
      setError(null);
      setParsingState('parsing');
      const parsed = await transactionAPI.parse(naturalLanguageInput);

      // Populate form with parsed data
      setFormData({
        transaction_type: parsed.transaction_type,
        ticker: parsed.ticker.toUpperCase(),
        quantity: parsed.quantity || 0,
        price: parsed.price || 0,
        total_amount: parsed.total_amount,
        transaction_date: parsed.transaction_date,
        notes: '',
      });

      setParsedTransaction(parsed);
      setParsingState('success');

      // Validate parsed data immediately
      const validation = validateAllFields({
        transaction_type: parsed.transaction_type,
        ticker: parsed.ticker,
        quantity: parsed.quantity || 0,
        price: parsed.price || 0,
        total_amount: parsed.total_amount,
        transaction_date: parsed.transaction_date,
      });

      if (!validation.valid) {
        setFormErrors(validation.errors);
        setFieldValidations(validation.fieldValidations);
      } else {
        setFormErrors([]);
        setFieldValidations(validation.fieldValidations);
      }
    } catch (err: any) {
      setParsingState('error');
      setParseError(err.response?.data?.detail || 'Failed to parse transaction');
    }
  };

  // Scroll to field helper
  const scrollToField = (fieldName: string) => {
    const field = fieldRefs.current[fieldName];
    if (field) {
      field.scrollIntoView({ behavior: 'smooth', block: 'center' });
      field.focus();
    }
  };

  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validate all fields
    const validation = validateAllFields(formData);

    if (!validation.valid) {
      setFormErrors(validation.errors);
      setFieldValidations(validation.fieldValidations);

      // Focus on first error field
      if (validation.errors.length > 0) {
        scrollToField(validation.errors[0].field);
      }

      return;
    }

    try {
      setError(null);

      // Prepare transaction data
      let transactionToSubmit = { ...formData } as TransactionCreate;

      // Handle cash-only transaction types (no ticker)
      if (['DEPOSIT', 'WITHDRAWAL', 'FEE', 'TAX', 'INTEREST'].includes(formData.transaction_type || '')) {
        transactionToSubmit.ticker = '';  // Empty ticker for cash transactions
      }

      // Always send positive amount - backend applies correct sign based on type
      transactionToSubmit.total_amount = Math.abs(transactionToSubmit.total_amount);

      const createdTransaction = await transactionAPI.create(transactionToSubmit);

      // Save transaction to show currency breakdown
      setSavedTransaction(createdTransaction);

      // Show success message
      setSubmitSuccess(true);

      // Call parent's onSuccess callback
      onSuccess();

      // Wait a bit then reset form
      setTimeout(() => {
        resetForm();
      }, 2500);
    } catch (err: any) {
      // Parse structured validation errors from backend
      if (err.response?.data?.detail) {
        const detail = err.response.data.detail;

        if (typeof detail === 'object' && detail.code === 'INSUFFICIENT_CASH') {
          setError(
            `❌ ${detail.message}\n\n` +
            `Tip: Add a DEPOSIT transaction to increase your available cash balance.`
          );
        } else if (typeof detail === 'object' && detail.message) {
          setError(detail.message);
        } else if (typeof detail === 'string') {
          setError(detail);
        } else {
          setError('Failed to create transaction. Please check your inputs.');
        }
      } else {
        setError(err.message || 'An unexpected error occurred.');
      }

      // Try to parse backend validation errors
      if (err.response?.data?.errors) {
        setFormErrors(err.response.data.errors);
      }
    }
  };

  // Reset form
  const resetForm = () => {
    setFormData({
      transaction_type: 'BUY',
      ticker: '',
      quantity: 0,
      price: 0,
      total_amount: 0,
      transaction_currency: 'CZK',
      transaction_date: new Date().toISOString().split('T')[0],
      notes: '',
    });
    setNaturalLanguageInput('');
    setParsedTransaction(null);
    setParsingState('idle');
    setParseError(null);
    setFieldValidations({});
    setFormErrors([]);
    setManuallyEditedFields(new Set());
    setError(null);
    setSubmitSuccess(false);
    setSavedTransaction(null);
    previousType.current = 'BUY';
  };

  return (
    <div className="transaction-form">
      <h2>Add Transaction</h2>

      <div className="form-toggle">
        <button
          type="button"
          className={useNaturalLanguage ? 'active' : ''}
          onClick={() => setUseNaturalLanguage(true)}
        >
          Natural Language
        </button>
        <button
          type="button"
          className={!useNaturalLanguage ? 'active' : ''}
          onClick={() => setUseNaturalLanguage(false)}
        >
          Manual Entry
        </button>
      </div>

      {error && (
        <div className="error-banner" role="alert">
          <span className="error-banner__icon">❌</span>
          <span>{error}</span>
        </div>
      )}

      {submitSuccess && savedTransaction && (
        <div className="success-banner" role="alert">
          <span className="success-banner__icon">✅</span>
          <div>
            <strong>Transaction added successfully!</strong>
            <MultiCurrencyDisplay transaction={savedTransaction} mode="all" />
          </div>
        </div>
      )}

      {useNaturalLanguage ? (
        <NaturalLanguageInput
          transactionType={formData.transaction_type || 'BUY'}
          naturalLanguageInput={naturalLanguageInput}
          onInputChange={setNaturalLanguageInput}
          onTypeChange={handleTypeChange}
          onParse={handleParse}
          parsedTransaction={parsedTransaction}
          parseError={parseError}
          parsingState={parsingState}
        />
      ) : null}

      <ManualEntryForm
        formData={formData}
        fieldValidations={fieldValidations}
        formErrors={formErrors}
        onFieldChange={handleFieldChange}
        onFieldBlur={handleFieldBlur}
        onFieldFocus={handleFieldFocus}
        onTypeChange={handleTypeChange}
        onSubmit={handleSubmit}
        calculationHint={calculationHint}
        scrollToField={scrollToField}
      />
    </div>
  );
};

export default TransactionForm;
