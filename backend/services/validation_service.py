"""
Transaction Validation Service
Provides comprehensive validation for transaction create/update operations
Ensures portfolio integrity and business rule compliance
"""
from typing import Optional, List, Dict, Any
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session
from models.database import Transaction
from models.schemas import TransactionUpdate


class ValidationError(Exception):
    """Custom exception for validation failures"""
    def __init__(self, message: str, field: Optional[str] = None, code: Optional[str] = None):
        self.message = message
        self.field = field
        self.code = code
        super().__init__(self.message)


class TransactionValidator:
    """Comprehensive validation for transaction operations"""

    @staticmethod
    def validate_transaction_update(
        db: Session,
        transaction_id: int,
        update_data: TransactionUpdate
    ) -> Dict[str, Any]:
        """
        Validate transaction update against business rules.
        Returns: Dict with 'valid': bool, 'errors': List[Dict], 'warnings': List[Dict]
        """
        errors = []
        warnings = []

        # Get original transaction
        original = db.query(Transaction).filter(Transaction.id == transaction_id).first()
        if not original:
            raise ValidationError("Transaction not found", code="NOT_FOUND")

        # Build effective transaction (merged original + updates)
        effective = TransactionValidator._merge_transaction(original, update_data)

        # Run all validation checks
        errors.extend(TransactionValidator._validate_date(db, effective, original))
        errors.extend(TransactionValidator._validate_quantity_price(effective))
        errors.extend(TransactionValidator._validate_portfolio_integrity(db, effective, original))
        errors.extend(TransactionValidator._validate_type_specific(effective))
        errors.extend(TransactionValidator._validate_fifo_impact(db, effective, original))

        # Generate warnings (non-blocking)
        warnings.extend(TransactionValidator._generate_warnings(db, effective, original))

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }

    @staticmethod
    def _merge_transaction(original: Transaction, updates: TransactionUpdate) -> Dict:
        """Merge original transaction with updates to create effective transaction"""
        update_dict = updates.dict(exclude_unset=True)
        merged = {
            'id': original.id,
            'transaction_type': update_dict.get('transaction_type', original.transaction_type),
            'ticker': update_dict.get('ticker', original.ticker),
            'quantity': update_dict.get('quantity', original.quantity),
            'price': update_dict.get('price', original.price),
            'total_amount': update_dict.get('total_amount', original.total_amount),
            'transaction_date': update_dict.get('transaction_date', original.transaction_date),
            'notes': update_dict.get('notes', original.notes),
        }
        return merged

    @staticmethod
    def _validate_date(db: Session, effective: Dict, original: Transaction) -> List[Dict]:
        """Validate transaction date constraints"""
        errors = []
        new_date = effective['transaction_date']

        # Convert to date object if it's a string
        if isinstance(new_date, str):
            try:
                new_date = datetime.strptime(new_date, '%Y-%m-%d').date()
            except ValueError:
                errors.append({
                    'field': 'transaction_date',
                    'message': 'Invalid date format. Use YYYY-MM-DD',
                    'code': 'DATE_INVALID_FORMAT'
                })
                return errors

        # No future dates
        if new_date > date.today():
            errors.append({
                'field': 'transaction_date',
                'message': 'Transaction date cannot be in the future',
                'code': 'DATE_FUTURE'
            })

        # No dates too far in past (configurable, e.g., 10 years)
        min_date = date.today() - timedelta(days=3650)
        if new_date < min_date:
            errors.append({
                'field': 'transaction_date',
                'message': f'Transaction date cannot be before {min_date.strftime("%Y-%m-%d")}',
                'code': 'DATE_TOO_OLD'
            })

        return errors

    @staticmethod
    def _validate_quantity_price(effective: Dict) -> List[Dict]:
        """Validate quantity and price fields based on transaction type"""
        errors = []
        txn_type = effective['transaction_type'].upper() if effective['transaction_type'] else ''

        # BUY/SELL must have quantity and price
        if txn_type in ['BUY', 'SELL']:
            if effective['quantity'] is None or effective['quantity'] <= 0:
                errors.append({
                    'field': 'quantity',
                    'message': f'{txn_type} transactions must have positive quantity',
                    'code': 'QUANTITY_REQUIRED'
                })
            if effective['price'] is None or effective['price'] <= 0:
                errors.append({
                    'field': 'price',
                    'message': f'{txn_type} transactions must have positive price',
                    'code': 'PRICE_REQUIRED'
                })

        # DIVIDEND must have positive total_amount
        if txn_type == 'DIVIDEND':
            if effective['total_amount'] <= 0:
                errors.append({
                    'field': 'total_amount',
                    'message': 'Dividend must have positive amount',
                    'code': 'AMOUNT_POSITIVE'
                })

        # FEE/TAX should have negative or zero total_amount
        if txn_type in ['FEE', 'TAX']:
            if effective['total_amount'] > 0:
                errors.append({
                    'field': 'total_amount',
                    'message': f'{txn_type} should have negative or zero amount',
                    'code': 'AMOUNT_NEGATIVE'
                })

        return errors

    @staticmethod
    def _validate_portfolio_integrity(
        db: Session,
        effective: Dict,
        original: Transaction
    ) -> List[Dict]:
        """
        CRITICAL: Ensure edits don't violate portfolio integrity
        Can't sell more shares than owned at that point in time
        """
        errors = []

        # Only validate for SELL transactions
        if effective['transaction_type'].upper() != 'SELL':
            return errors

        ticker = effective['ticker']
        txn_date = effective['transaction_date']
        quantity_to_sell = effective['quantity']

        if quantity_to_sell is None or quantity_to_sell <= 0:
            return errors  # Will be caught by _validate_quantity_price

        # Get all transactions for this ticker UP TO this transaction's date
        # Exclude the current transaction being edited
        transactions = db.query(Transaction).filter(
            Transaction.ticker == ticker,
            Transaction.transaction_type.in_(['BUY', 'SELL']),
            Transaction.transaction_date <= txn_date,
            Transaction.id != original.id  # Exclude the one being edited
        ).order_by(Transaction.transaction_date.asc(), Transaction.id.asc()).all()

        # Calculate available quantity at this date
        available_quantity = 0.0
        for txn in transactions:
            if txn.transaction_type == 'BUY':
                available_quantity += txn.quantity if txn.quantity else 0
            elif txn.transaction_type == 'SELL':
                available_quantity -= txn.quantity if txn.quantity else 0

        # Check if we can sell the requested quantity
        if quantity_to_sell > available_quantity:
            errors.append({
                'field': 'quantity',
                'message': f'Cannot sell {quantity_to_sell} shares. Only {available_quantity} shares available at {txn_date}',
                'code': 'INSUFFICIENT_SHARES',
                'metadata': {
                    'available': available_quantity,
                    'requested': quantity_to_sell,
                    'ticker': ticker,
                    'date': str(txn_date)
                }
            })

        return errors

    @staticmethod
    def _validate_type_specific(effective: Dict) -> List[Dict]:
        """Validate type-specific business rules"""
        errors = []
        txn_type = effective['transaction_type'].upper() if effective['transaction_type'] else ''

        # Valid transaction types
        valid_types = ['BUY', 'SELL', 'DIVIDEND', 'FEE', 'TAX']
        if txn_type not in valid_types:
            errors.append({
                'field': 'transaction_type',
                'message': f'Invalid transaction type. Must be one of: {", ".join(valid_types)}',
                'code': 'INVALID_TYPE'
            })

        # Ticker must not be empty
        if not effective['ticker'] or effective['ticker'].strip() == '':
            errors.append({
                'field': 'ticker',
                'message': 'Ticker symbol cannot be empty',
                'code': 'TICKER_REQUIRED'
            })

        return errors

    @staticmethod
    def _validate_fifo_impact(
        db: Session,
        effective: Dict,
        original: Transaction
    ) -> List[Dict]:
        """
        Validate that editing BUY doesn't cause future SELLs to become invalid
        Simulates the full transaction timeline with the edit applied
        """
        errors = []

        # Only check if editing a BUY transaction and quantity is being reduced
        if effective['transaction_type'].upper() != 'BUY':
            return errors

        ticker = effective['ticker']
        original_quantity = original.quantity if original.quantity else 0
        new_quantity = effective['quantity'] if effective['quantity'] else 0

        # Only validate if quantity is being reduced (increasing is always safe)
        if new_quantity >= original_quantity:
            return errors

        # Get ALL transactions for this ticker in chronological order
        all_transactions = db.query(Transaction).filter(
            Transaction.ticker == ticker,
            Transaction.transaction_type.in_(['BUY', 'SELL']),
            Transaction.id != original.id  # Exclude the one being edited
        ).order_by(Transaction.transaction_date.asc(), Transaction.id.asc()).all()

        # Simulate portfolio state with the modified transaction
        running_balance = 0.0
        new_txn_added = False

        for txn in all_transactions:
            # Insert our modified transaction at the correct chronological point
            if not new_txn_added and txn.transaction_date >= effective['transaction_date']:
                running_balance += new_quantity
                new_txn_added = True

            # Process current transaction
            if txn.transaction_type == 'BUY':
                running_balance += txn.quantity if txn.quantity else 0
            elif txn.transaction_type == 'SELL':
                sell_qty = txn.quantity if txn.quantity else 0
                running_balance -= sell_qty

                # Check if we're oversold
                if running_balance < 0:
                    errors.append({
                        'field': 'quantity',
                        'message': f'Reducing BUY quantity to {new_quantity} would cause SELL on {txn.transaction_date} to fail (insufficient shares)',
                        'code': 'FIFO_CHAIN_BROKEN',
                        'metadata': {
                            'affected_sell_date': str(txn.transaction_date),
                            'sell_quantity': sell_qty,
                            'available_before_sell': running_balance + sell_qty,
                            'ticker': ticker
                        }
                    })
                    return errors  # Return immediately on first error

        return errors

    @staticmethod
    def _generate_warnings(
        db: Session,
        effective: Dict,
        original: Transaction
    ) -> List[Dict]:
        """Generate non-blocking warnings for potentially risky edits"""
        warnings = []

        # Warn if changing BUY to SELL or vice versa
        if original.transaction_type != effective['transaction_type']:
            if original.transaction_type in ['BUY', 'SELL'] and effective['transaction_type'] in ['BUY', 'SELL']:
                warnings.append({
                    'message': f'Changing transaction type from {original.transaction_type} to {effective["transaction_type"]} may significantly impact portfolio calculations',
                    'code': 'TYPE_CHANGE_WARNING'
                })

        # Warn if changing ticker
        if original.ticker != effective['ticker']:
            warnings.append({
                'message': 'Changing ticker symbol affects portfolio holdings. Consider creating a new transaction instead.',
                'code': 'TICKER_CHANGE_WARNING'
            })

        # Warn if large quantity change (>50%)
        if original.quantity and effective['quantity']:
            change_pct = abs(effective['quantity'] - original.quantity) / original.quantity
            if change_pct > 0.5:
                warnings.append({
                    'message': f'Large quantity change ({change_pct*100:.1f}%). Please verify this is correct.',
                    'code': 'LARGE_CHANGE_WARNING'
                })

        return warnings
