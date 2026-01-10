from sqlalchemy.orm import Session
from models.database import Transaction
from models.schemas import TransactionCreate, TransactionUpdate
from datetime import datetime
from typing import List, Optional


class TransactionService:
    """Service for managing transaction CRUD operations"""

    @staticmethod
    def create_transaction(db: Session, transaction: TransactionCreate) -> Transaction:
        """Create a new transaction with audit trail"""
        from services.audit_service import AuditService

        db_transaction = Transaction(
            transaction_type=transaction.transaction_type.upper(),
            ticker=transaction.ticker.upper(),
            quantity=transaction.quantity,
            price=transaction.price,
            total_amount=transaction.total_amount,
            transaction_date=transaction.transaction_date,
            notes=transaction.notes
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
        for field, value in update_data.items():
            if field in ['transaction_type', 'ticker'] and value:
                value = value.upper()
            setattr(db_transaction, field, value)

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
