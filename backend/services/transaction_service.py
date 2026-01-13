from sqlalchemy.orm import Session
from models.database import Transaction
from models.schemas import TransactionCreate, TransactionUpdate
from datetime import datetime
from typing import List, Optional, Dict


class TransactionService:
    """Service for managing transaction CRUD operations"""

    @staticmethod
    def create_transaction(db: Session, transaction: TransactionCreate) -> Transaction:
        """Create a new transaction with validation, audit trail, and multi-currency support"""
        from services.audit_service import AuditService
        from services.exchange_rate_service import ExchangeRateService
        from services.validation_service import TransactionValidator, ValidationError
        from services.sign_conversion_service import SignConversionService
        import logging

        logger = logging.getLogger(__name__)

        # VALIDATION: Check business rules before creating
        validation_result = TransactionValidator.validate_transaction_create(db, transaction)

        if not validation_result['valid']:
            # Raise exception with detailed errors
            error_messages = [err['message'] for err in validation_result['errors']]
            raise ValidationError(
                message='; '.join(error_messages),
                field=validation_result['errors'][0]['field'] if validation_result['errors'] else None,
                code=validation_result['errors'][0]['code'] if validation_result['errors'] else None
            )

        # AUTOMATIC SIGN CONVERSION: Apply semantic sign convention
        # User enters positive amounts, we convert based on transaction type
        corrected_amount = SignConversionService.apply_sign_convention(
            transaction.transaction_type,
            transaction.total_amount
        )

        # Log if correction was applied (for debugging/audit)
        if corrected_amount != transaction.total_amount:
            logger.info(
                f"Sign conversion applied: {transaction.transaction_type} "
                f"{transaction.total_amount} -> {corrected_amount}"
            )

        # Update amount with correct sign
        transaction.total_amount = corrected_amount

        # Get currency amounts for all three currencies (with corrected sign)
        if getattr(transaction, 'skip_exchange_rate_conversion', False):
            # Skip conversion for migrations - use total_amount as CZK amount
            currency_amounts = {
                'usd': None,
                'eur': None,
                'czk': transaction.total_amount
            }
        else:
            currency_amounts = ExchangeRateService.get_all_currency_amounts(
                amount=transaction.total_amount,
                transaction_currency=transaction.transaction_currency,
                rate_date=transaction.transaction_date,
                db=db
            )

        db_transaction = Transaction(
            transaction_type=transaction.transaction_type.upper(),
            ticker=transaction.ticker.upper() if transaction.ticker else '',  # Empty for DEPOSIT/WITHDRAWAL
            quantity=transaction.quantity,
            price=transaction.price,
            total_amount=transaction.total_amount,
            transaction_currency=transaction.transaction_currency,
            amount_usd=currency_amounts['usd'],
            amount_eur=currency_amounts['eur'],
            amount_czk=currency_amounts['czk'],
            transaction_date=transaction.transaction_date,
            notes=transaction.notes,
            import_source=getattr(transaction, 'import_source', None),
            import_batch_id=getattr(transaction, 'import_batch_id', None),
            broker_transaction_id=getattr(transaction, 'broker_transaction_id', None)
        )
        db.add(db_transaction)
        db.flush()  # Get ID before audit recording

        # Record creation in audit trail
        AuditService.record_change(db, db_transaction, 'CREATE')

        db.commit()
        db.refresh(db_transaction)
        return db_transaction

    @staticmethod
    def get_transaction(db: Session, transaction_id: int) -> Optional[Transaction]:
        """Get a single transaction by ID"""
        return db.query(Transaction).filter(Transaction.id == transaction_id).first()

    @staticmethod
    def get_all_transactions(
        db: Session,
        skip: int = 0,
        limit: int = 1000,
        ticker: Optional[str] = None,
        transaction_type: Optional[str] = None
    ) -> List[Transaction]:
        """Get all transactions with optional filtering"""
        query = db.query(Transaction)

        if ticker:
            query = query.filter(Transaction.ticker == ticker.upper())

        if transaction_type:
            query = query.filter(Transaction.transaction_type == transaction_type.upper())

        return query.order_by(Transaction.transaction_date.desc()).offset(skip).limit(limit).all()

    @staticmethod
    def update_transaction(
        db: Session,
        transaction_id: int,
        transaction_update: TransactionUpdate
    ) -> Optional[Transaction]:
        """Update an existing transaction with validation and audit trail"""
        from services.validation_service import TransactionValidator, ValidationError
        from services.audit_service import AuditService

        # Get original transaction
        db_transaction = db.query(Transaction).filter(
            Transaction.id == transaction_id
        ).first()

        if not db_transaction:
            return None

        # Store original for audit trail (create a copy of values)
        original = Transaction(
            id=db_transaction.id,
            transaction_type=db_transaction.transaction_type,
            ticker=db_transaction.ticker,
            quantity=db_transaction.quantity,
            price=db_transaction.price,
            total_amount=db_transaction.total_amount,
            transaction_date=db_transaction.transaction_date,
            notes=db_transaction.notes,
            version=db_transaction.version
        )

        # Validate the update
        validation_result = TransactionValidator.validate_transaction_update(
            db, transaction_id, transaction_update
        )

        if not validation_result['valid']:
            # Raise exception with detailed errors
            error_messages = [err['message'] for err in validation_result['errors']]
            raise ValidationError(
                message='; '.join(error_messages),
                field=validation_result['errors'][0]['field'] if validation_result['errors'] else None,
                code=validation_result['errors'][0]['code'] if validation_result['errors'] else None
            )

        # Apply updates
        update_data = transaction_update.dict(exclude_unset=True)

        # Check if currency-related fields changed (need recalculation)
        needs_currency_recalc = any(
            field in update_data
            for field in ['total_amount', 'transaction_currency', 'transaction_date']
        )

        for field, value in update_data.items():
            if field in ['transaction_type', 'ticker'] and value:
                value = value.upper()
            setattr(db_transaction, field, value)

        # AUTOMATIC SIGN CONVERSION: Apply sign convention if amount was updated
        if 'total_amount' in update_data or 'transaction_type' in update_data:
            from services.sign_conversion_service import SignConversionService
            import logging

            logger = logging.getLogger(__name__)

            corrected_amount = SignConversionService.apply_sign_convention(
                db_transaction.transaction_type,
                db_transaction.total_amount
            )

            if corrected_amount != db_transaction.total_amount:
                logger.info(
                    f"Sign conversion applied on update: {db_transaction.transaction_type} "
                    f"ID {transaction_id}: {db_transaction.total_amount} -> {corrected_amount}"
                )
                db_transaction.total_amount = corrected_amount
                needs_currency_recalc = True  # Force recalc if sign changed

        # Recalculate currency amounts if needed
        if needs_currency_recalc:
            from services.exchange_rate_service import ExchangeRateService

            currency_amounts = ExchangeRateService.get_all_currency_amounts(
                amount=db_transaction.total_amount,
                transaction_currency=db_transaction.transaction_currency,
                rate_date=db_transaction.transaction_date,
                db=db
            )

            db_transaction.amount_usd = currency_amounts['usd']
            db_transaction.amount_eur = currency_amounts['eur']
            db_transaction.amount_czk = currency_amounts['czk']

        db_transaction.updated_at = datetime.utcnow()
        db_transaction.version += 1  # Optimistic locking

        # Record audit trail
        AuditService.record_change(
            db,
            db_transaction,
            'UPDATE',
            original=original,
            reason=None  # Could be passed from API if needed
        )

        db.commit()
        db.refresh(db_transaction)

        return db_transaction

    @staticmethod
    def delete_transaction(db: Session, transaction_id: int) -> bool:
        """Delete a transaction with audit trail"""
        from services.audit_service import AuditService

        db_transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()

        if not db_transaction:
            return False

        # Record deletion in audit trail BEFORE deleting
        AuditService.record_change(db, db_transaction, 'DELETE')

        db.delete(db_transaction)
        db.commit()
        return True

    @staticmethod
    def get_transactions_by_ticker(db: Session, ticker: str) -> List[Transaction]:
        """Get all transactions for a specific ticker"""
        return db.query(Transaction).filter(
            Transaction.ticker == ticker.upper()
        ).order_by(Transaction.transaction_date.asc()).all()

    @staticmethod
    def get_unique_tickers(db: Session) -> List[str]:
        """Get list of all unique tickers that have transactions"""
        results = db.query(Transaction.ticker).filter(
            Transaction.transaction_type.in_(['BUY', 'SELL'])
        ).distinct().all()
        return [r[0] for r in results]

    @staticmethod
    def get_transaction_summary(db: Session) -> dict:
        """Get summary statistics about transactions"""
        total_transactions = db.query(Transaction).count()
        unique_tickers = len(TransactionService.get_unique_tickers(db))

        buy_count = db.query(Transaction).filter(Transaction.transaction_type == 'BUY').count()
        sell_count = db.query(Transaction).filter(Transaction.transaction_type == 'SELL').count()
        dividend_count = db.query(Transaction).filter(Transaction.transaction_type == 'DIVIDEND').count()

        return {
            "total_transactions": total_transactions,
            "unique_tickers": unique_tickers,
            "buy_count": buy_count,
            "sell_count": sell_count,
            "dividend_count": dividend_count
        }

    @staticmethod
    def refresh_currency_amounts(
        db: Session,
        transaction_ids: Optional[List[int]] = None
    ) -> Dict[str, int]:
        """
        Recalculate currency amounts for transactions
        If transaction_ids is None, refresh ALL transactions

        Args:
            db: Database session
            transaction_ids: List of transaction IDs to refresh, or None for all

        Returns:
            Dict with 'updated' and 'failed' counts, plus 'errors' list
        """
        from services.exchange_rate_service import ExchangeRateService

        updated_count = 0
        failed_count = 0
        errors = []

        # Get transactions to refresh
        if transaction_ids:
            transactions = db.query(Transaction).filter(
                Transaction.id.in_(transaction_ids)
            ).all()
        else:
            transactions = db.query(Transaction).all()

        # Get unique dates for batch fetching rates
        unique_dates = list(set(t.transaction_date for t in transactions))
        print(f"Fetching exchange rates for {len(unique_dates)} unique dates...")

        # Batch fetch all needed rates
        try:
            ExchangeRateService.batch_fetch_rates(unique_dates, db)
        except Exception as e:
            errors.append(f"Batch rate fetch error: {str(e)}")

        # Update each transaction
        for transaction in transactions:
            try:
                # Ensure transaction_currency is set (for old records)
                if not transaction.transaction_currency:
                    transaction.transaction_currency = 'USD'  # Default for old records

                # Recalculate currency amounts
                currency_amounts = ExchangeRateService.get_all_currency_amounts(
                    amount=transaction.total_amount,
                    transaction_currency=transaction.transaction_currency,
                    rate_date=transaction.transaction_date,
                    db=db
                )

                transaction.amount_usd = currency_amounts['usd']
                transaction.amount_eur = currency_amounts['eur']
                transaction.amount_czk = currency_amounts['czk']

                updated_count += 1

            except Exception as e:
                failed_count += 1
                error_msg = f"Transaction ID {transaction.id}: {str(e)}"
                errors.append(error_msg)
                print(f"Error updating transaction {transaction.id}: {e}")

        # Commit all updates
        try:
            db.commit()
            print(f"Successfully updated {updated_count} transactions")
        except Exception as e:
            db.rollback()
            errors.append(f"Commit error: {str(e)}")
            print(f"Failed to commit updates: {e}")

        return {
            'updated': updated_count,
            'failed': failed_count,
            'errors': errors
        }
