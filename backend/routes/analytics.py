from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from models.database import get_db
from models.schemas import (
    PerformanceDataPoint, DiversificationMetrics,
    VolatilityMetrics, DividendSummary, KPIResponse
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


@router.get("/kpis", response_model=KPIResponse)
def get_all_kpis(db: Session = Depends(get_db)):
    """Get all KPIs in a single response"""
    return AnalyticsService.get_all_kpis(db)
