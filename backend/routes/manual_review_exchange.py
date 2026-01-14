"""
Manual Review API for Exchange Rates

Provides endpoints for reviewing and managing exchange rates that need manual verification,
typically those resolved by AI with low confidence or other issues.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime
from pydantic import BaseModel
import json

from models.database import ExchangeRate
from database import get_db

router = APIRouter()


# Request/Response Models
class ExchangeRateReviewItem(BaseModel):
    """Exchange rate item needing review"""
    base_currency: str
    target_currency: str
    rate_date: date
    rate: float
    source: str
    confidence: str
    ai_used: bool
    ai_sources: List[str]
    needs_manual_review: bool
    manual_review_reason: Optional[str]
    fetched_at: datetime

    class Config:
        from_attributes = True


class ApproveRateRequest(BaseModel):
    """Request to approve an AI-suggested rate"""
    approved: bool
    notes: Optional[str] = None


class OverrideRateRequest(BaseModel):
    """Request to override a rate with manual value"""
    new_rate: float
    reason: str


@router.get("/api/exchange-rates/manual-review", response_model=List[ExchangeRateReviewItem])
def get_rates_needing_review(db: Session = Depends(get_db)):
    """
    Get all exchange rates that need manual review.

    Returns rates that were:
    - Resolved by AI with low confidence
    - Flagged for manual review for other reasons
    """
    rates = db.query(ExchangeRate).filter(
        ExchangeRate.needs_manual_review == True
    ).order_by(
        ExchangeRate.rate_date.desc()
    ).all()

    # Convert to response model with ai_sources parsing
    result = []
    for rate in rates:
        sources = []
        if rate.ai_sources:
            try:
                sources = json.loads(rate.ai_sources)
            except:
                sources = []

        result.append(ExchangeRateReviewItem(
            base_currency=rate.base_currency,
            target_currency=rate.target_currency,
            rate_date=rate.rate_date,
            rate=rate.rate,
            source=rate.source,
            confidence=rate.confidence or 'unknown',
            ai_used=rate.ai_used or False,
            ai_sources=sources,
            needs_manual_review=rate.needs_manual_review,
            manual_review_reason=rate.manual_review_reason,
            fetched_at=rate.fetched_at
        ))

    return result


@router.get("/api/exchange-rates/manual-review/count")
def get_review_count(db: Session = Depends(get_db)):
    """Get count of exchange rates needing review"""
    count = db.query(ExchangeRate).filter(
        ExchangeRate.needs_manual_review == True
    ).count()

    return {"count": count}


@router.post("/api/exchange-rates/manual-review/{base}/{target}/{rate_date}/approve")
def approve_rate(
    base: str,
    target: str,
    rate_date: date,
    request: ApproveRateRequest,
    db: Session = Depends(get_db)
):
    """
    Approve an AI-suggested exchange rate.

    Marks the rate as no longer needing review and updates metadata.
    """
    rate = db.query(ExchangeRate).filter(
        ExchangeRate.base_currency == base.upper(),
        ExchangeRate.target_currency == target.upper(),
        ExchangeRate.rate_date == rate_date
    ).first()

    if not rate:
        raise HTTPException(
            status_code=404,
            detail=f"Exchange rate not found: {base}/{target} on {rate_date}"
        )

    if request.approved:
        # Mark as approved
        rate.needs_manual_review = False
        rate.confidence = 'high'  # Upgrade confidence after manual approval
        if request.notes:
            rate.manual_review_reason = f"APPROVED: {request.notes}"
        else:
            rate.manual_review_reason = "APPROVED by manual review"

        db.commit()

        return {
            "success": True,
            "message": f"Rate approved for {base}/{target} on {rate_date}",
            "rate": rate.rate
        }
    else:
        # Not approved - keep flagged for review
        if request.notes:
            rate.manual_review_reason = f"REJECTED: {request.notes}"

        db.commit()

        return {
            "success": False,
            "message": f"Rate rejected for {base}/{target} on {rate_date}. Please provide a correct value.",
            "rate": rate.rate
        }


@router.post("/api/exchange-rates/manual-review/{base}/{target}/{rate_date}/override")
def override_rate(
    base: str,
    target: str,
    rate_date: date,
    request: OverrideRateRequest,
    db: Session = Depends(get_db)
):
    """
    Override an exchange rate with a manually provided value.

    Replaces the existing rate and marks as manually verified.
    """
    rate = db.query(ExchangeRate).filter(
        ExchangeRate.base_currency == base.upper(),
        ExchangeRate.target_currency == target.upper(),
        ExchangeRate.rate_date == rate_date
    ).first()

    if not rate:
        raise HTTPException(
            status_code=404,
            detail=f"Exchange rate not found: {base}/{target} on {rate_date}"
        )

    # Validate new rate
    if request.new_rate <= 0:
        raise HTTPException(
            status_code=400,
            detail="Exchange rate must be positive"
        )

    # Store old rate for logging
    old_rate = rate.rate

    # Update rate
    rate.rate = request.new_rate
    rate.needs_manual_review = False
    rate.confidence = 'high'  # Manual override is high confidence
    rate.source = 'manual-override'
    rate.manual_review_reason = f"MANUAL OVERRIDE from {old_rate} to {request.new_rate}. Reason: {request.reason}"
    rate.fetched_at = datetime.utcnow()

    db.commit()

    return {
        "success": True,
        "message": f"Rate manually updated for {base}/{target} on {rate_date}",
        "old_rate": old_rate,
        "new_rate": request.new_rate,
        "reason": request.reason
    }


@router.delete("/api/exchange-rates/manual-review/{base}/{target}/{rate_date}")
def delete_rate(
    base: str,
    target: str,
    rate_date: date,
    db: Session = Depends(get_db)
):
    """
    Delete an exchange rate entry.

    Use this for rates that are incorrect and should be re-fetched.
    """
    rate = db.query(ExchangeRate).filter(
        ExchangeRate.base_currency == base.upper(),
        ExchangeRate.target_currency == target.upper(),
        ExchangeRate.rate_date == rate_date
    ).first()

    if not rate:
        raise HTTPException(
            status_code=404,
            detail=f"Exchange rate not found: {base}/{target} on {rate_date}"
        )

    db.delete(rate)
    db.commit()

    return {
        "success": True,
        "message": f"Exchange rate deleted for {base}/{target} on {rate_date}. Will be re-fetched on next use."
    }


@router.get("/api/exchange-rates/stats")
def get_exchange_rate_stats(db: Session = Depends(get_db)):
    """
    Get statistics about exchange rate sources and quality.

    Useful for monitoring which resolution tiers are being used.
    """
    from sqlalchemy import func

    # Total rates
    total_rates = db.query(func.count(ExchangeRate.base_currency)).scalar()

    # Rates by source
    rates_by_source = db.query(
        ExchangeRate.source,
        func.count(ExchangeRate.source)
    ).group_by(ExchangeRate.source).all()

    # AI usage stats
    ai_used_count = db.query(ExchangeRate).filter(
        ExchangeRate.ai_used == True
    ).count()

    # Confidence distribution
    confidence_dist = db.query(
        ExchangeRate.confidence,
        func.count(ExchangeRate.confidence)
    ).group_by(ExchangeRate.confidence).all()

    # Manual review needed
    needs_review = db.query(ExchangeRate).filter(
        ExchangeRate.needs_manual_review == True
    ).count()

    return {
        "total_rates": total_rates,
        "rates_by_source": {source: count for source, count in rates_by_source},
        "ai_used_count": ai_used_count,
        "ai_usage_percentage": (ai_used_count / total_rates * 100) if total_rates > 0 else 0,
        "confidence_distribution": {conf or 'unknown': count for conf, count in confidence_dist},
        "needs_manual_review": needs_review
    }
