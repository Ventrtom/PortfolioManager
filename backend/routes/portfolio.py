from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from models.database import get_db
from models.schemas import (
    Holding, PortfolioSummary, IndustryAllocation, SectorAllocation
)
from services.portfolio_service import PortfolioService
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/summary", response_model=PortfolioSummary)
def get_portfolio_summary(db: Session = Depends(get_db)):
    """Get overall portfolio summary with key metrics"""
    try:
        return PortfolioService.get_portfolio_summary(db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"message": str(e), "code": "INVALID_REQUEST"})
    except Exception as e:
        logger.error(f"Error getting portfolio summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"message": "Failed to fetch portfolio summary", "code": "SERVER_ERROR"})


@router.get("/holdings", response_model=List[Holding])
def get_holdings(db: Session = Depends(get_db)):
    """Get current portfolio holdings with P&L"""
    try:
        return PortfolioService.calculate_holdings(db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"message": str(e), "code": "INVALID_REQUEST"})
    except Exception as e:
        logger.error(f"Error calculating holdings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"message": "Failed to calculate holdings", "code": "SERVER_ERROR"})


@router.get("/allocation/industry", response_model=List[IndustryAllocation])
def get_industry_allocation(db: Session = Depends(get_db)):
    """Get portfolio allocation by industry"""
    try:
        return PortfolioService.get_industry_allocation(db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"message": str(e), "code": "INVALID_REQUEST"})
    except Exception as e:
        logger.error(f"Error getting industry allocation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"message": "Failed to get industry allocation", "code": "SERVER_ERROR"})


@router.get("/allocation/sector", response_model=List[SectorAllocation])
def get_sector_allocation(db: Session = Depends(get_db)):
    """Get portfolio allocation by sector"""
    try:
        return PortfolioService.get_sector_allocation(db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"message": str(e), "code": "INVALID_REQUEST"})
    except Exception as e:
        logger.error(f"Error getting sector allocation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"message": "Failed to get sector allocation", "code": "SERVER_ERROR"})


@router.post("/refresh-prices")
def refresh_prices(db: Session = Depends(get_db)) -> Dict[str, float]:
    """Refresh current prices for all holdings"""
    try:
        return PortfolioService.refresh_portfolio_prices(db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"message": str(e), "code": "INVALID_REQUEST"})
    except Exception as e:
        logger.error(f"Error refreshing prices: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"message": "Failed to refresh prices", "code": "SERVER_ERROR"})
