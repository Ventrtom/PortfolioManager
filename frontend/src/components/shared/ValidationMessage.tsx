import React from 'react';
import { FieldState } from '../../types';
import type { FieldValidation } from '../../types';

interface ValidationMessageProps {
  validation: FieldValidation;
  fieldName: string;
}

const ValidationMessage: React.FC<ValidationMessageProps> = ({ validation, fieldName }) => {
  if (validation.state === FieldState.PRISTINE || validation.state === FieldState.TOUCHED) {
    return null;
  }

  const getStateClass = () => {
    switch (validation.state) {
      case FieldState.VALID:
        return 'validation-feedback--valid';
      case FieldState.INVALID:
        return 'validation-feedback--invalid';
      case FieldState.WARNING:
        return 'validation-feedback--warning';
      case FieldState.VALIDATING:
        return 'validation-feedback--validating';
      default:
        return '';
    }
  };

  return (
    <div
      id={`validation-${fieldName}`}
      className={`validation-feedback ${getStateClass()}`}
      role="alert"
      aria-live="polite"
    >
      {validation.icon && (
        <span className="validation-feedback__icon" aria-hidden="true">
          {validation.icon}
        </span>
      )}
      {validation.message && (
        <span className="validation-feedback__message">
          {validation.message}
        </span>
      )}
    </div>
  );
};

export default ValidationMessage;
