"""
Transaction Audit Service
Records and tracks all changes to transactions for compliance and debugging
Maintains complete audit trail in transaction_history table
"""
from sqlalchemy.orm import Session
from models.database import Transaction, TransactionHistory
from typing import Optional, List, Dict
from datetime import datetime
import json


class AuditService:
    """Service for recording transaction audit trail"""

    @staticmethod
    def record_change(
        db: Session,
        transaction: Transaction,
        change_type: str,  # 'CREATE', 'UPDATE', 'DELETE'
        original: Optional[Transaction] = None,
        reason: Optional[str] = None
    ) -> TransactionHistory:
        """
        Record a transaction change in audit history

        Args:
            db: Database session
            transaction: The transaction after change
            change_type: Type of change (CREATE, UPDATE, DELETE)
            original: Original transaction (for UPDATE/DELETE)
            reason: Optional reason for change

        Returns:
            TransactionHistory record
        """
        # Calculate changed fields for UPDATE
        changed_fields = None
        if change_type == 'UPDATE' and original:
            changed_fields = AuditService._calculate_changed_fields(original, transaction)

        # Create history record
        history = TransactionHistory(
            transaction_id=transaction.id,
            transaction_type=transaction.transaction_type,
            ticker=transaction.ticker,
            quantity=transaction.quantity,
            price=transaction.price,
            total_amount=transaction.total_amount,
            transaction_date=transaction.transaction_date,
            notes=transaction.notes,
            change_type=change_type,
            changed_by=None,  # Future: user identification
            changed_at=datetime.utcnow(),
            changed_fields=json.dumps(changed_fields) if changed_fields else None
        )

        db.add(history)
        db.flush()  # Get ID without committing

        return history

    @staticmethod
    def _calculate_changed_fields(original: Transaction, updated: Transaction) -> Dict:
        """
        Calculate which fields changed between original and updated transaction

        Args:
            original: Original transaction
            updated: Updated transaction

        Returns:
            Dict mapping field names to {'old': value, 'new': value}
        """
        changes = {}

        fields_to_check = [
            'transaction_type', 'ticker', 'quantity', 'price',
            'total_amount', 'transaction_date', 'notes'
        ]

        for field in fields_to_check:
            old_value = getattr(original, field)
            new_value = getattr(updated, field)

            if old_value != new_value:
                changes[field] = {
                    'old': str(old_value) if old_value is not None else None,
                    'new': str(new_value) if new_value is not None else None
                }

        return changes

    @staticmethod
    def get_transaction_history(
        db: Session,
        transaction_id: int
    ) -> List[TransactionHistory]:
        """
        Get full audit history for a specific transaction

        Args:
            db: Database session
            transaction_id: ID of transaction to get history for

        Returns:
            List of TransactionHistory records, ordered by changed_at DESC
        """
        return db.query(TransactionHistory).filter(
            TransactionHistory.transaction_id == transaction_id
        ).order_by(TransactionHistory.changed_at.desc()).all()

    @staticmethod
    def get_recent_changes(
        db: Session,
        limit: int = 50
    ) -> List[TransactionHistory]:
        """
        Get recent changes across all transactions

        Args:
            db: Database session
            limit: Maximum number of records to return

        Returns:
            List of recent TransactionHistory records
        """
        return db.query(TransactionHistory).order_by(
            TransactionHistory.changed_at.desc()
        ).limit(limit).all()

    @staticmethod
    def get_changes_by_ticker(
        db: Session,
        ticker: str,
        limit: int = 100
    ) -> List[TransactionHistory]:
        """
        Get audit history for all transactions of a specific ticker

        Args:
            db: Database session
            ticker: Stock ticker symbol
            limit: Maximum number of records to return

        Returns:
            List of TransactionHistory records for the ticker
        """
        return db.query(TransactionHistory).filter(
            TransactionHistory.ticker == ticker.upper()
        ).order_by(TransactionHistory.changed_at.desc()).limit(limit).all()

    @staticmethod
    def get_changes_by_type(
        db: Session,
        change_type: str,
        limit: int = 100
    ) -> List[TransactionHistory]:
        """
        Get audit history filtered by change type (CREATE, UPDATE, DELETE)

        Args:
            db: Database session
            change_type: Type of change to filter by
            limit: Maximum number of records to return

        Returns:
            List of TransactionHistory records
        """
        return db.query(TransactionHistory).filter(
            TransactionHistory.change_type == change_type.upper()
        ).order_by(TransactionHistory.changed_at.desc()).limit(limit).all()
