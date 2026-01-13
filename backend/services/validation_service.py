"""
Transaction Validation Service
Provides comprehensive validation for transaction create/update operations
Ensures portfolio integrity and business rule compliance
"""
from typing import Optional, List, Dict, Any
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session
from models.database import Transaction
from models.schemas import TransactionUpdate, TransactionCreate


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
    def validate_transaction_create(
        db: Session,
        transaction_data: TransactionCreate
    ) -> Dict[str, Any]:
        """
        Validate transaction creation against business rules.

        Args:
            db: Database session
            transaction_data: Transaction data to validate

        Returns:
            {
                'valid': bool,
                'errors': [{'field': str, 'message': str, 'code': str, 'metadata': Dict}],
                'warnings': [{'message': str, 'code': str}]
            }
        """
        errors = []
        warnings = []

        # Basic validation
        errors.extend(TransactionValidator._validate_date_create(transaction_data.transaction_date))
        errors.extend(TransactionValidator._validate_quantity_price_create(transaction_data))
        errors.extend(TransactionValidator._validate_type_specific_create(transaction_data))

        # Cash validation for BUY
        if transaction_data.transaction_type.upper() == 'BUY':
            errors.extend(TransactionValidator._validate_cash_for_buy(db, transaction_data))

        # Cash validation for WITHDRAWAL
        if transaction_data.transaction_type.upper() == 'WITHDRAWAL':
            errors.extend(TransactionValidator._validate_cash_for_withdrawal(db, transaction_data))

        # Holdings validation for SELL
        if transaction_data.transaction_type.upper() == 'SELL':
            errors.extend(TransactionValidator._validate_holdings_for_sell(db, transaction_data))

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

        # Validate amount is non-zero (sign is handled automatically by TransactionService)
        if effective['total_amount'] == 0:
            errors.append({
                'field': 'total_amount',
                'message': 'Transaction amount cannot be zero',
                'code': 'AMOUNT_ZERO'
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
        valid_types = ['BUY', 'SELL', 'DIVIDEND', 'FEE', 'TAX', 'DEPOSIT', 'WITHDRAWAL', 'INTEREST', 'SPLIT']
        if txn_type not in valid_types:
            errors.append({
                'field': 'transaction_type',
                'message': f'Invalid transaction type. Must be one of: {", ".join(valid_types)}',
                'code': 'INVALID_TYPE'
            })

        # Ticker must not be empty except for cash transactions
        if txn_type not in ['DEPOSIT', 'WITHDRAWAL', 'INTEREST']:
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

    @staticmethod
    def _validate_date_create(transaction_date: date) -> List[Dict]:
        """Validate transaction date for CREATE operations"""
        errors = []
        new_date = transaction_date

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

        # No dates too far in past (10 years)
        min_date = date.today() - timedelta(days=3650)
        if new_date < min_date:
            errors.append({
                'field': 'transaction_date',
                'message': f'Transaction date cannot be before {min_date.strftime("%Y-%m-%d")}',
                'code': 'DATE_TOO_OLD'
            })

        return errors

    @staticmethod
    def _validate_quantity_price_create(transaction_data: TransactionCreate) -> List[Dict]:
        """Validate quantity and price for CREATE operations"""
        errors = []
        txn_type = transaction_data.transaction_type.upper()

        if txn_type in ['BUY', 'SELL']:
            if not transaction_data.quantity or transaction_data.quantity <= 0:
                errors.append({
                    'field': 'quantity',
                    'message': f'{txn_type} transactions must have positive quantity',
                    'code': 'INVALID_QUANTITY'
                })
            if not transaction_data.price or transaction_data.price <= 0:
                errors.append({
                    'field': 'price',
                    'message': f'{txn_type} transactions must have positive price',
                    'code': 'INVALID_PRICE'
                })

        # Validate amount is non-zero (sign is handled automatically by TransactionService)
        if transaction_data.total_amount == 0:
            errors.append({
                'field': 'total_amount',
                'message': 'Transaction amount cannot be zero',
                'code': 'INVALID_AMOUNT'
            })

        return errors

    @staticmethod
    def _validate_type_specific_create(transaction_data: TransactionCreate) -> List[Dict]:
        """Validate transaction type is valid and has required fields"""
        errors = []
        valid_types = ['BUY', 'SELL', 'DIVIDEND', 'FEE', 'TAX', 'DEPOSIT', 'WITHDRAWAL', 'INTEREST', 'SPLIT']
        txn_type = transaction_data.transaction_type.upper()

        if txn_type not in valid_types:
            errors.append({
                'field': 'transaction_type',
                'message': f'Invalid transaction type. Must be one of: {", ".join(valid_types)}',
                'code': 'INVALID_TYPE'
            })

        # INTEREST-specific validation
        if txn_type == 'INTEREST':
            # Amount is validated above (non-zero check)
            # Sign is handled automatically by TransactionService
            # Quantity and price should be 0 or None
            # (no validation needed - they're optional)
            pass

        # SPLIT-specific validation
        if txn_type == 'SPLIT':
            # Ticker required for stock splits
            if not transaction_data.ticker or not transaction_data.ticker.strip():
                errors.append({
                    'field': 'ticker',
                    'message': 'SPLIT transactions must have a ticker symbol',
                    'code': 'TICKER_REQUIRED'
                })
            # Quantity required (shares added/removed)
            if not transaction_data.quantity:
                errors.append({
                    'field': 'quantity',
                    'message': 'SPLIT transactions must have quantity (net shares change)',
                    'code': 'QUANTITY_REQUIRED'
                })
            # Price should be 0 for splits
            # (no validation needed - it's optional)

        return errors

    @staticmethod
    def _validate_cash_for_buy(db: Session, transaction_data: TransactionCreate) -> List[Dict]:
        """
        Validate sufficient cash balance for BUY transaction.
        Uses grandfathering: skips validation if transaction is before first DEPOSIT.
        Can be bypassed with skip_cash_validation flag (for migrations).
        """
        from services.portfolio_service import PortfolioService
        from services.exchange_rate_service import ExchangeRateService

        errors = []

        # Skip validation if skip_cash_validation flag is set (for migrations)
        if getattr(transaction_data, 'skip_cash_validation', False):
            return errors

        # Check if portfolio has any DEPOSIT transactions
        first_deposit = db.query(Transaction).filter(
            Transaction.transaction_type == 'DEPOSIT'
        ).order_by(Transaction.transaction_date.asc()).first()

        # GRANDFATHERING: If no deposits exist, or transaction is before first deposit,
        # skip validation (backward compatibility for legacy portfolios)
        if not first_deposit or transaction_data.transaction_date < first_deposit.transaction_date:
            return errors

        # Calculate cash balance at transaction date
        cash_balance_at_date = PortfolioService.get_cash_balance_at_date(
            db,
            transaction_data.transaction_date
        )

        # Convert transaction amount to CZK
        currency_amounts = ExchangeRateService.get_all_currency_amounts(
            amount=transaction_data.total_amount,
            transaction_currency=transaction_data.transaction_currency,
            rate_date=transaction_data.transaction_date,
            db=db
        )
        amount_czk = currency_amounts['czk']

        # STRICT MODE: Check if sufficient cash (no overdraft allowed)
        if cash_balance_at_date < amount_czk:
            errors.append({
                'field': 'total_amount',
                'message': f'Insufficient cash balance. Available: {cash_balance_at_date:.2f} CZK, Required: {amount_czk:.2f} CZK. Please add a DEPOSIT transaction or reduce the purchase amount.',
                'code': 'INSUFFICIENT_CASH',
                'metadata': {
                    'available_czk': round(cash_balance_at_date, 2),
                    'required_czk': round(amount_czk, 2),
                    'shortfall_czk': round(amount_czk - cash_balance_at_date, 2),
                    'date': str(transaction_data.transaction_date)
                }
            })

        return errors

    @staticmethod
    def _validate_cash_for_withdrawal(db: Session, transaction_data: TransactionCreate) -> List[Dict]:
        """
        Validate sufficient cash balance for WITHDRAWAL transaction.
        Can be bypassed with skip_cash_validation flag (for migrations).
        """
        from services.portfolio_service import PortfolioService
        from services.exchange_rate_service import ExchangeRateService

        errors = []

        # Skip validation if skip_cash_validation flag is set (for migrations)
        if getattr(transaction_data, 'skip_cash_validation', False):
            return errors

        # Calculate cash balance at transaction date
        cash_balance_at_date = PortfolioService.get_cash_balance_at_date(
            db,
            transaction_data.transaction_date
        )

        # Convert withdrawal amount to CZK (take absolute value since stored as negative)
        currency_amounts = ExchangeRateService.get_all_currency_amounts(
            amount=abs(transaction_data.total_amount),
            transaction_currency=transaction_data.transaction_currency,
            rate_date=transaction_data.transaction_date,
            db=db
        )
        withdrawal_amount_czk = currency_amounts['czk']

        # Check if sufficient cash for withdrawal
        if cash_balance_at_date < withdrawal_amount_czk:
            errors.append({
                'field': 'total_amount',
                'message': f'Insufficient cash for withdrawal. Available: {cash_balance_at_date:.2f} CZK, Requested: {withdrawal_amount_czk:.2f} CZK.',
                'code': 'INSUFFICIENT_CASH_WITHDRAWAL',
                'metadata': {
                    'available_czk': round(cash_balance_at_date, 2),
                    'withdrawal_czk': round(withdrawal_amount_czk, 2),
                    'shortfall_czk': round(withdrawal_amount_czk - cash_balance_at_date, 2),
                    'date': str(transaction_data.transaction_date)
                }
            })

        return errors

    @staticmethod
    def _validate_holdings_for_sell(db: Session, transaction_data: TransactionCreate) -> List[Dict]:
        """
        Validate sufficient holdings for SELL transaction.
        Can be bypassed with skip_fifo_validation flag (for migrations).
        """
        from utils.calculations import FinancialCalculations

        errors = []

        # Skip validation if skip_fifo_validation flag is set (for migrations)
        if getattr(transaction_data, 'skip_fifo_validation', False):
            return errors

        ticker = transaction_data.ticker.upper()
        quantity_to_sell = transaction_data.quantity

        # Get all BUY and SELL transactions for this ticker up to the transaction date
        transactions = db.query(Transaction).filter(
            Transaction.ticker == ticker,
            Transaction.transaction_type.in_(['BUY', 'SELL']),
            Transaction.transaction_date <= transaction_data.transaction_date
        ).order_by(Transaction.transaction_date.asc(), Transaction.id.asc()).all()

        # Calculate available quantity at transaction date
        holdings_dict = {'purchases': [], 'total_quantity': 0}

        for txn in transactions:
            if txn.transaction_type == 'BUY':
                holdings_dict['purchases'].append({
                    'quantity': txn.quantity,
                    'price': txn.price,
                    'date': txn.transaction_date
                })
                holdings_dict['total_quantity'] += txn.quantity
            elif txn.transaction_type == 'SELL':
                _, remaining_purchases = FinancialCalculations.calculate_fifo_cost_basis(
                    holdings_dict['purchases'],
                    txn.quantity
                )
                holdings_dict['purchases'] = remaining_purchases
                holdings_dict['total_quantity'] -= txn.quantity

        available_quantity = holdings_dict['total_quantity']

        # Check if sufficient holdings to sell
        if available_quantity < quantity_to_sell:
            errors.append({
                'field': 'quantity',
                'message': f'Insufficient holdings to sell. Available: {available_quantity} shares, Attempting to sell: {quantity_to_sell} shares.',
                'code': 'INSUFFICIENT_HOLDINGS',
                'metadata': {
                    'ticker': ticker,
                    'available_quantity': available_quantity,
                    'sell_quantity': quantity_to_sell,
                    'shortfall': quantity_to_sell - available_quantity,
                    'date': str(transaction_data.transaction_date)
                }
            })

        return errors
