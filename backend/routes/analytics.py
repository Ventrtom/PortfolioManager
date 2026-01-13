from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from models.database import get_db
import logging

logger = logging.getLogger(__name__)
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
    try:
        return AnalyticsService.get_performance_history(db, days)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"message": str(e), "code": "INVALID_REQUEST"})
    except Exception as e:
        logger.error(f"Error getting performance history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"message": "Failed to fetch performance history", "code": "SERVER_ERROR"})


@router.get("/diversification", response_model=DiversificationMetrics)
def get_diversification_metrics(db: Session = Depends(get_db)):
    """Get diversification metrics"""
    try:
        return AnalyticsService.get_diversification_metrics(db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"message": str(e), "code": "INVALID_REQUEST"})
    except Exception as e:
        logger.error(f"Error getting diversification metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"message": "Failed to fetch diversification metrics", "code": "SERVER_ERROR"})


@router.get("/volatility", response_model=VolatilityMetrics)
def get_volatility_metrics(db: Session = Depends(get_db)):
    """Get volatility metrics"""
    try:
        return AnalyticsService.get_volatility_metrics(db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"message": str(e), "code": "INVALID_REQUEST"})
    except Exception as e:
        logger.error(f"Error getting volatility metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"message": "Failed to fetch volatility metrics", "code": "SERVER_ERROR"})


@router.get("/dividends", response_model=DividendSummary)
def get_dividend_summary(db: Session = Depends(get_db)):
    """Get dividend summary"""
    try:
        return AnalyticsService.get_dividend_summary(db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"message": str(e), "code": "INVALID_REQUEST"})
    except Exception as e:
        logger.error(f"Error getting dividend summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"message": "Failed to fetch dividend summary", "code": "SERVER_ERROR"})


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
