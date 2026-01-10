from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from models.database import get_db
from models.schemas import (
    TransactionCreate, TransactionUpdate, TransactionResponse, ParsedTransaction
)
from services.transaction_service import TransactionService
from utils.parser import TransactionParser
from typing import List, Optional

router = APIRouter()


@router.post("/", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(
    transaction: TransactionCreate,
    db: Session = Depends(get_db)
):
    """Create a new transaction"""
    try:
        return TransactionService.create_transaction(db, transaction)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=List[TransactionResponse])
def get_transactions(
    skip: int = 0,
    limit: int = 1000,
    ticker: Optional[str] = None,
    transaction_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all transactions with optional filtering"""
    return TransactionService.get_all_transactions(db, skip, limit, ticker, transaction_type)


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(transaction_id: int, db: Session = Depends(get_db)):
    """Get a single transaction by ID"""
    transaction = TransactionService.get_transaction(db, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


@router.put("/{transaction_id}", response_model=TransactionResponse)
def update_transaction(
    transaction_id: int,
    transaction_update: TransactionUpdate,
    db: Session = Depends(get_db)
):
    """Update an existing transaction with validation"""
    from services.validation_service import ValidationError

    try:
        updated_transaction = TransactionService.update_transaction(
            db, transaction_id, transaction_update
        )
        if not updated_transaction:
            raise HTTPException(status_code=404, detail="Transaction not found")
        return updated_transaction

    except ValidationError as e:
        # Return structured validation error
        raise HTTPException(
            status_code=400,
            detail={
                "message": e.message,
                "field": e.field,
                "code": e.code
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(transaction_id: int, db: Session = Depends(get_db)):
    """Delete a transaction"""
    success = TransactionService.delete_transaction(db, transaction_id)
    if not success:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return None


@router.post("/parse", response_model=ParsedTransaction)
def parse_transaction(input_text: str):
    """
    Parse natural language transaction input
    Example: "BUY - ASM.US - 200 - @1.10 - 24.3.2025"
    """
    try:
        parsed_data = TransactionParser.parse_transaction(input_text)
        return ParsedTransaction(**parsed_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse: {str(e)}")


@router.get("/summary/stats")
def get_transaction_summary(db: Session = Depends(get_db)):
    """Get summary statistics about transactions"""
    return TransactionService.get_transaction_summary(db)


@router.get("/{transaction_id}/history")
def get_transaction_history(
    transaction_id: int,
    db: Session = Depends(get_db)
):
    """Get audit history for a specific transaction"""
    from services.audit_service import AuditService

    history = AuditService.get_transaction_history(db, transaction_id)
    if not history:
        raise HTTPException(status_code=404, detail="No history found for this transaction")
    return history
