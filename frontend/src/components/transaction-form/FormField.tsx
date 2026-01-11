import React, { forwardRef } from 'react';
import { FieldState } from '../../types';
import type { FieldConfig, FieldValidation } from '../../types';
import Tooltip from '../shared/Tooltip';
import Badge from '../shared/Badge';
import ValidationMessage from '../shared/ValidationMessage';

interface FormFieldProps {
  fieldName: string;
  fieldConfig: FieldConfig;
  value: any;
  validation?: FieldValidation;
  onChange: (value: any) => void;
  onBlur?: () => void;
  onFocus?: () => void;
  type?: 'text' | 'number' | 'date' | 'textarea';
  calculationHint?: string | null;
}

const FormField = forwardRef<HTMLInputElement | HTMLTextAreaElement, FormFieldProps>(
  (
    {
      fieldName,
      fieldConfig,
      value,
      validation,
      onChange,
      onBlur,
      onFocus,
      type = 'text',
      calculationHint
    },
    ref
  ) => {
    if (!fieldConfig.visible) {
      return null;
    }

    const getValidationClass = () => {
      if (!validation || validation.state === FieldState.PRISTINE || validation.state === FieldState.TOUCHED) {
        return '';
      }
      return `form-input--${validation.state}`;
    };

    const inputId = `input-${fieldName}`;
    const labelId = `label-${fieldName}`;
    const helpId = `help-${fieldName}`;
    const validationId = `validation-${fieldName}`;

    const getAriaDescribedBy = () => {
      const ids: string[] = [];
      if (fieldConfig.helpText) ids.push(helpId);
      if (validation && validation.state !== FieldState.PRISTINE) ids.push(validationId);
      return ids.length > 0 ? ids.join(' ') : undefined;
    };

    const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      if (type === 'number') {
        const numValue = parseFloat(e.target.value);
        onChange(isNaN(numValue) ? 0 : numValue);
      } else {
        onChange(e.target.value);
      }
    };

    return (
      <div className={`form-group ${getValidationClass()}`}>
        <label id={labelId} htmlFor={inputId}>
          {fieldConfig.label}
          {fieldConfig.required && <Badge type="required" />}
          {!fieldConfig.required && <Badge type="optional" />}
          {fieldConfig.autoCalculated && <Badge type="auto" />}
          {fieldConfig.helpText && <Tooltip content={fieldConfig.helpText} />}
        </label>

        <div className="input-wrapper">
          {type === 'textarea' ? (
            <textarea
              ref={ref as React.Ref<HTMLTextAreaElement>}
              id={inputId}
              value={value || ''}
              onChange={handleChange}
              onBlur={onBlur}
              onFocus={onFocus}
              placeholder={fieldConfig.placeholder}
              className={`form-input ${getValidationClass()}`}
              aria-labelledby={labelId}
              aria-describedby={getAriaDescribedBy()}
              aria-invalid={validation?.state === FieldState.INVALID}
              aria-required={fieldConfig.required}
              rows={3}
            />
          ) : (
            <input
              ref={ref as React.Ref<HTMLInputElement>}
              id={inputId}
              type={type}
              value={value || (type === 'number' ? 0 : '')}
              onChange={handleChange}
              onBlur={onBlur}
              onFocus={onFocus}
              placeholder={fieldConfig.placeholder}
              className={`form-input ${getValidationClass()}`}
              aria-labelledby={labelId}
              aria-describedby={getAriaDescribedBy()}
              aria-invalid={validation?.state === FieldState.INVALID}
              aria-required={fieldConfig.required}
              step={type === 'number' ? '0.01' : undefined}
            />
          )}

          {fieldConfig.helpText && (
            <div id={helpId} className="sr-only">
              {fieldConfig.helpText}
            </div>
          )}

          {validation && <ValidationMessage validation={validation} fieldName={fieldName} />}

          {calculationHint && (
            <div className="calculation-hint">
              <span className="calculation-hint__icon" aria-hidden="true">
                🧮
              </span>
              <span>{calculationHint}</span>
            </div>
          )}
        </div>
      </div>
    );
  }
);

FormField.displayName = 'FormField';

export default FormField;
