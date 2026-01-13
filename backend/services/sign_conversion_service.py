"""
Transaction Sign Convention Service
Centralizes all transaction sign conversion logic

Sign Convention (Semantic):
- NEGATIVE (money OUT): BUY, FEE, TAX, WITHDRAWAL - reduce cash balance
- POSITIVE (money IN): SELL, DIVIDEND, DEPOSIT, INTEREST - increase cash balance

User Experience:
- Users always enter positive amounts in the UI
- Backend automatically applies correct sign based on transaction type
"""
from typing import Dict


class SignConversionService:
    """
    Handles automatic sign conversion for transaction types.

    Convention:
    - User always enters positive amounts in UI
    - Backend automatically applies correct sign based on transaction type
    - Negative: BUY, FEE, TAX, WITHDRAWAL (money out - reduce cash)
    - Positive: SELL, DIVIDEND, DEPOSIT, INTEREST (money in - increase cash)
    """

    # Transaction types that should be stored as NEGATIVE (money OUT)
    NEGATIVE_TYPES = {'BUY', 'FEE', 'TAX', 'WITHDRAWAL'}

    # Transaction types that should be stored as POSITIVE (money IN)
    POSITIVE_TYPES = {'SELL', 'DIVIDEND', 'DEPOSIT', 'INTEREST', 'SPLIT'}

    @staticmethod
    def apply_sign_convention(transaction_type: str, amount: float) -> float:
        """
        Apply sign convention to transaction amount.

        Args:
            transaction_type: Type of transaction (e.g., 'BUY', 'FEE', etc.)
            amount: Amount value (can be positive or negative)

        Returns:
            Amount with correct sign applied

        Examples:
            apply_sign_convention('BUY', 5000.0) -> -5000.0 (spending money)
            apply_sign_convention('BUY', -5000.0) -> -5000.0 (already correct)
            apply_sign_convention('FEE', 100.0) -> -100.0 (cost)
            apply_sign_convention('SELL', 6000.0) -> 6000.0 (receiving money)
            apply_sign_convention('DEPOSIT', 1000.0) -> 1000.0 (adding cash)
            apply_sign_convention('DEPOSIT', -1000.0) -> 1000.0 (fix wrong sign)
        """
        txn_type = transaction_type.upper()

        if txn_type in SignConversionService.NEGATIVE_TYPES:
            # Should be negative (money OUT) - force negative
            return -abs(amount)
        elif txn_type in SignConversionService.POSITIVE_TYPES:
            # Should be positive (money IN) - force positive
            return abs(amount)
        else:
            # Unknown type - return as-is (validation will catch this)
            return amount

    @staticmethod
    def get_expected_sign(transaction_type: str) -> Dict[str, any]:
        """
        Get information about expected sign for transaction type.

        Returns:
            {
                'should_be_negative': bool,
                'should_be_positive': bool,
                'description': str,
                'semantic_meaning': str
            }
        """
        txn_type = transaction_type.upper()

        if txn_type in SignConversionService.NEGATIVE_TYPES:
            return {
                'should_be_negative': True,
                'should_be_positive': False,
                'description': f'{txn_type} reduces cash balance (stored as negative)',
                'semantic_meaning': 'money_out'
            }
        elif txn_type in SignConversionService.POSITIVE_TYPES:
            return {
                'should_be_negative': False,
                'should_be_positive': True,
                'description': f'{txn_type} increases cash balance (stored as positive)',
                'semantic_meaning': 'money_in'
            }
        else:
            return {
                'should_be_negative': False,
                'should_be_positive': False,
                'description': 'Unknown transaction type',
                'semantic_meaning': 'unknown'
            }

    @staticmethod
    def validate_sign_convention(transaction_type: str, amount: float) -> Dict[str, any]:
        """
        Check if amount follows sign convention.

        Returns:
            {
                'valid': bool,
                'current_sign': str,  # 'positive', 'negative', or 'zero'
                'expected_sign': str,
                'needs_correction': bool,
                'corrected_amount': float,
                'description': str
            }
        """
        txn_type = transaction_type.upper()

        if amount == 0:
            current_sign = 'zero'
        elif amount > 0:
            current_sign = 'positive'
        else:
            current_sign = 'negative'

        expected_info = SignConversionService.get_expected_sign(txn_type)

        if expected_info['should_be_negative']:
            expected_sign = 'negative'
            valid = amount < 0
        elif expected_info['should_be_positive']:
            expected_sign = 'positive'
            valid = amount > 0
        else:
            expected_sign = 'unknown'
            valid = True  # No convention for unknown types

        return {
            'valid': valid,
            'current_sign': current_sign,
            'expected_sign': expected_sign,
            'needs_correction': not valid and expected_sign != 'unknown',
            'corrected_amount': SignConversionService.apply_sign_convention(txn_type, amount),
            'description': expected_info['description']
        }

    @staticmethod
    def is_money_out_transaction(transaction_type: str) -> bool:
        """Check if transaction type represents money leaving the portfolio"""
        return transaction_type.upper() in SignConversionService.NEGATIVE_TYPES

    @staticmethod
    def is_money_in_transaction(transaction_type: str) -> bool:
        """Check if transaction type represents money entering the portfolio"""
        return transaction_type.upper() in SignConversionService.POSITIVE_TYPES

    @staticmethod
    def get_all_transaction_types_by_sign() -> Dict[str, list]:
        """
        Get all transaction types grouped by their sign convention.

        Returns:
            {
                'negative': ['BUY', 'FEE', 'TAX', 'WITHDRAWAL'],
                'positive': ['SELL', 'DIVIDEND', 'DEPOSIT', 'INTEREST', 'SPLIT']
            }
        """
        return {
            'negative': sorted(list(SignConversionService.NEGATIVE_TYPES)),
            'positive': sorted(list(SignConversionService.POSITIVE_TYPES))
        }
