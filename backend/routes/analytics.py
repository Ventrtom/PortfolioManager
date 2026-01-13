from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from models.database import get_db
from models.schemas import (
    PerformanceDataPoint, DiversificationMetrics,
    VolatilityMetrics, DividendSummary, KPIResponse,
    KPIResponseWithMetadata, SnapshotHistoryItem
)
from services.analytics_service import AnalyticsService
from typing import List

router = APIRouter()


@router.get("/performance", response_model=List[PerformanceDataPoint])
def get_performance_history(days: int = 365, db: Session = Depends(get_db)):
    """Get portfolio performance history"""
    return AnalyticsService.get_performance_history(db, days)


@router.get("/diversification", response_model=DiversificationMetrics)
def get_diversification_metrics(db: Session = Depends(get_db)):
    """Get diversification metrics"""
    return AnalyticsService.get_diversification_metrics(db)


@router.get("/volatility", response_model=VolatilityMetrics)
def get_volatility_metrics(db: Session = Depends(get_db)):
    """Get volatility metrics"""
    return AnalyticsService.get_volatility_metrics(db)


@router.get("/dividends", response_model=DividendSummary)
def get_dividend_summary(db: Session = Depends(get_db)):
    """Get dividend summary"""
    return AnalyticsService.get_dividend_summary(db)


@router.get("/kpis", response_model=KPIResponseWithMetadata)
def get_all_kpis(currency: str = 'CZK', db: Session = Depends(get_db)):
    """Get all KPIs from most recent snapshot (fast load)"""
    # Validate currency
    if currency.upper() not in ['USD', 'EUR', 'CZK']:
        raise HTTPException(status_code=400, detail="Currency must be USD, EUR, or CZK")

    return AnalyticsService.get_all_kpis(db, target_currency=currency.upper())


@router.post("/kpis/recalculate", response_model=KPIResponseWithMetadata)
def recalculate_kpis(db: Session = Depends(get_db)):
    """Manually trigger KPI recalculation and save new snapshot"""
    return AnalyticsService.recalculate_and_save_kpis(db, use_cached_prices=True)


@router.get("/kpis/history", response_model=List[SnapshotHistoryItem])
def get_kpi_history(limit: int = 100, db: Session = Depends(get_db)):
    """Get historical KPI snapshots for trend visualization"""
    return AnalyticsService.get_snapshot_history(db, limit)
