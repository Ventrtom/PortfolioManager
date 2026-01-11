import React from 'react';
import type { TransactionCreate, FieldValidation, ValidationError } from '../../types';
import DynamicFormFields from './DynamicFormFields';

interface ManualEntryFormProps {
  formData: Partial<TransactionCreate>;
  fieldValidations: Record<string, FieldValidation>;
  formErrors: ValidationError[];
  onFieldChange: (fieldName: keyof TransactionCreate, value: any) => void;
  onFieldBlur: (fieldName: keyof TransactionCreate) => void;
  onFieldFocus: (fieldName: keyof TransactionCreate) => void;
  onTypeChange: (type: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  calculationHint?: string | null;
  scrollToField?: (fieldName: string) => void;
}

const ManualEntryForm: React.FC<ManualEntryFormProps> = ({
  formData,
  fieldValidations,
  formErrors,
  onFieldChange,
  onFieldBlur,
  onFieldFocus,
  onTypeChange,
  onSubmit,
  calculationHint,
  scrollToField
}) => {
  return (
    <form onSubmit={onSubmit} className="manual-entry-form">
      {formErrors.length > 0 && (
        <div className="error-banner" role="alert">
          <div className="error-banner__header">
            <span className="error-banner__icon" aria-hidden="true">
              ❌
            </span>
            <strong>
              {formErrors.length} {formErrors.length === 1 ? 'error' : 'errors'} prevent
              {formErrors.length === 1 ? 's' : ''} submission:
            </strong>
          </div>
          <ul className="error-banner__list">
            {formErrors.map((error, idx) => (
              <li key={idx}>
                {scrollToField ? (
                  <button
                    type="button"
                    className="error-banner__link"
                    onClick={() => scrollToField(error.field)}
                  >
                    {error.field}: {error.message}
                  </button>
                ) : (
                  <span>
                    {error.field}: {error.message}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="form-group">
        <label htmlFor="transaction-type">
          Transaction Type
          <span className="form-field__badge form-field__badge--required">Required</span>
        </label>
        <select
          id="transaction-type"
          value={formData.transaction_type || 'BUY'}
          onChange={(e) => onTypeChange(e.target.value)}
          className="form-input form-select"
          required
        >
          <option value="BUY">BUY</option>
          <option value="SELL">SELL</option>
          <option value="DIVIDEND">DIVIDEND</option>
          <option value="FEE">FEE</option>
          <option value="TAX">TAX</option>
        </select>
      </div>

      <DynamicFormFields
        formData={formData}
        fieldValidations={fieldValidations}
        onFieldChange={onFieldChange}
        onFieldBlur={onFieldBlur}
        onFieldFocus={onFieldFocus}
        calculationHint={calculationHint}
      />

      <div className="form-actions">
        <button type="submit" className="btn btn-primary">
          Add Transaction
        </button>
      </div>
    </form>
  );
};

export default ManualEntryForm;
