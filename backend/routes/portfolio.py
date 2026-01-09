from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from models.database import get_db
from models.schemas import (
    Holding, PortfolioSummary, IndustryAllocation, SectorAllocation
)
from services.portfolio_service import PortfolioService
from typing import List, Dict

router = APIRouter()


@router.get("/summary", response_model=PortfolioSummary)
def get_portfolio_summary(db: Session = Depends(get_db)):
    """Get overall portfolio summary with key metrics"""
    return PortfolioService.get_portfolio_summary(db)


@router.get("/holdings", response_model=List[Holding])
def get_holdings(db: Session = Depends(get_db)):
    """Get current portfolio holdings with P&L"""
    return PortfolioService.calculate_holdings(db)


@router.get("/allocation/industry", response_model=List[IndustryAllocation])
def get_industry_allocation(db: Session = Depends(get_db)):
    """Get portfolio allocation by industry"""
    return PortfolioService.get_industry_allocation(db)


@router.get("/allocation/sector", response_model=List[SectorAllocation])
def get_sector_allocation(db: Session = Depends(get_db)):
    """Get portfolio allocation by sector"""
    return PortfolioService.get_sector_allocation(db)


@router.post("/refresh-prices")
def refresh_prices(db: Session = Depends(get_db)) -> Dict[str, float]:
    """Refresh current prices for all holdings"""
    return PortfolioService.refresh_portfolio_prices(db)
