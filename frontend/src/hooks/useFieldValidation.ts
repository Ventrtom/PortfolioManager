import { useState, useCallback, useEffect, useRef } from 'react';
import { FieldState } from '../types';
import type { TransactionCreate, FieldValidation } from '../types';
import { validateField } from '../utils/validation';

/**
 * Custom hook for field-level validation with debouncing
 */
export const useFieldValidation = (
  fieldName: keyof TransactionCreate,
  value: any,
  formData: Partial<TransactionCreate>,
  delay: number = 500
) => {
  const [validation, setValidation] = useState<FieldValidation>({
    state: FieldState.PRISTINE
  });
  const [touched, setTouched] = useState(false);
  const timeoutRef = useRef<number | null>(null);

  // Debounced validation on change
  useEffect(() => {
    if (!touched) return;

    // Clear previous timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    // Set validating state immediately
    setValidation({ state: FieldState.VALIDATING, icon: '⏳' });

    // Debounce the actual validation
    timeoutRef.current = setTimeout(() => {
      const result = validateField(fieldName, value, formData);
      setValidation(result);
    }, delay);

    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, [value, formData, fieldName, delay, touched]);

  // Immediate validation (for blur events)
  const validateImmediately = useCallback(() => {
    setTouched(true);
    const result = validateField(fieldName, value, formData);
    setValidation(result);
  }, [fieldName, value, formData]);

  // Mark field as touched
  const markTouched = useCallback(() => {
    setTouched(true);
  }, []);

  // Reset validation state
  const resetValidation = useCallback(() => {
    setTouched(false);
    setValidation({ state: FieldState.PRISTINE });
  }, []);

  return {
    validation,
    touched,
    validateImmediately,
    markTouched,
    resetValidation
  };
};
