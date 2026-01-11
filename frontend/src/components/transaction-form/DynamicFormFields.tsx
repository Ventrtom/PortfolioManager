import React, { useRef } from 'react';
import type { TransactionCreate, FieldValidation } from '../../types';
import { getFieldConfig } from '../../config/transactionFormConfig';
import FormField from './FormField';

interface DynamicFormFieldsProps {
  formData: Partial<TransactionCreate>;
  fieldValidations: Record<string, FieldValidation>;
  onFieldChange: (fieldName: keyof TransactionCreate, value: any) => void;
  onFieldBlur: (fieldName: keyof TransactionCreate) => void;
  onFieldFocus: (fieldName: keyof TransactionCreate) => void;
  calculationHint?: string | null;
}

const DynamicFormFields: React.FC<DynamicFormFieldsProps> = ({
  formData,
  fieldValidations,
  onFieldChange,
  onFieldBlur,
  onFieldFocus,
  calculationHint
}) => {
  const fieldRefs = useRef<Record<string, HTMLElement | null>>({});

  const transactionType = formData.transaction_type || 'BUY';

  // Field order for rendering
  const fieldOrder: Array<keyof TransactionCreate> = [
    'ticker',
    'quantity',
    'price',
    'total_amount',
    'transaction_date',
    'notes'
  ];

  const getFieldType = (fieldName: keyof TransactionCreate) => {
    switch (fieldName) {
      case 'quantity':
      case 'price':
      case 'total_amount':
        return 'number';
      case 'transaction_date':
        return 'date';
      case 'notes':
        return 'textarea';
      default:
        return 'text';
    }
  };

  return (
    <div className="dynamic-form-fields">
      {fieldOrder.map(fieldName => {
        const config = getFieldConfig(transactionType, fieldName);
        if (!config) return null;

        return (
          <FormField
            key={fieldName}
            fieldName={fieldName}
            fieldConfig={config}
            value={formData[fieldName]}
            validation={fieldValidations[fieldName]}
            onChange={(value) => onFieldChange(fieldName, value)}
            onBlur={() => onFieldBlur(fieldName)}
            onFocus={() => onFieldFocus(fieldName)}
            type={getFieldType(fieldName)}
            calculationHint={fieldName === 'total_amount' ? calculationHint : undefined}
            ref={(el) => {
              fieldRefs.current[fieldName] = el;
            }}
          />
        );
      })}
    </div>
  );
};

export default DynamicFormFields;
