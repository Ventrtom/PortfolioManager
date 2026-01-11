import { useEffect, useState } from 'react';
import type { TransactionCreate } from '../types';

interface AutoCalculationResult {
  calculatedValue: number | null;
  calculationHint: string | null;
  shouldUpdate: boolean;
}

/**
 * Custom hook for auto-calculating total_amount for BUY/SELL transactions
 */
export const useAutoCalculation = (
  formData: Partial<TransactionCreate>,
  manuallyEditedFields: Set<string>
): AutoCalculationResult => {
  const [calculationHint, setCalculationHint] = useState<string | null>(null);

  useEffect(() => {
    const transactionType = formData.transaction_type?.toUpperCase();

    // Only auto-calculate for BUY and SELL
    if (transactionType !== 'BUY' && transactionType !== 'SELL') {
      setCalculationHint(null);
      return;
    }

    const quantity = formData.quantity || 0;
    const price = formData.price || 0;

    // Check if we have valid values to calculate
    if (quantity > 0 && price > 0) {
      const calculated = quantity * price;

      // Check if user has manually edited total_amount
      if (manuallyEditedFields.has('total_amount')) {
        setCalculationHint('Manual override');
      } else {
        setCalculationHint(`${quantity} × $${price.toFixed(2)} = $${calculated.toFixed(2)}`);
      }
    } else {
      setCalculationHint(null);
    }
  }, [formData.quantity, formData.price, formData.transaction_type, manuallyEditedFields]);

  const transactionType = formData.transaction_type?.toUpperCase();
  const quantity = formData.quantity || 0;
  const price = formData.price || 0;

  // Determine if we should auto-update the value
  if (
    (transactionType === 'BUY' || transactionType === 'SELL') &&
    quantity > 0 &&
    price > 0 &&
    !manuallyEditedFields.has('total_amount')
  ) {
    const calculated = quantity * price;
    return {
      calculatedValue: transactionType === 'BUY' ? calculated : -calculated,
      calculationHint,
      shouldUpdate: true
    };
  }

  return {
    calculatedValue: null,
    calculationHint,
    shouldUpdate: false
  };
};
