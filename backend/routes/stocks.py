"""
Stock Management Routes
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from models.database import get_db
from models.schemas import StockResponse, StockCreate, StockUpdate
from services.stock_service import StockService
from services.enrichment_service import EnrichmentService
from typing import List, Optional

router = APIRouter()


@router.get("/", response_model=List[StockResponse])
def get_stocks(
    search: Optional[str] = None,
    sector: Optional[str] = None,
    industry: Optional[str] = None,
    status: Optional[str] = None,
    has_holdings: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get all stocks with filtering"""
    return StockService.get_all_stocks(
        db, search, sector, industry, status, has_holdings, skip, limit
    )


@router.post("/", response_model=StockResponse, status_code=201)
def create_stock(
    stock: StockCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Create new stock manually
    Enrichment happens in background
    """
    # Create stock
    new_stock = StockService.create_stock(stock.ticker, db)

    # Trigger enrichment in background
    background_tasks.add_task(
        EnrichmentService.enrich_stock,
        stock.ticker,
        db
    )

    # Return the stock record (will be pending status)
    stocks = StockService.get_all_stocks(db, search=stock.ticker, limit=1)
    return stocks[0] if stocks else new_stock


@router.get("/{ticker}", response_model=StockResponse)
def get_stock(ticker: str, db: Session = Depends(get_db)):
    """Get single stock by ticker"""
    stocks = StockService.get_all_stocks(db, search=ticker, limit=1)

    if not stocks:
        raise HTTPException(status_code=404, detail="Stock not found")

    return stocks[0]


@router.put("/{ticker}", response_model=StockResponse)
def update_stock(
    ticker: str,
    updates: StockUpdate,
    db: Session = Depends(get_db)
):
    """
    Update stock manually (for flagged/failed stocks)
    Sets status to 'manual'
    """
    updated = StockService.update_stock(
        ticker,
        updates.dict(exclude_unset=True),
        db
    )

    if not updated:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Return full stock record with portfolio context
    stocks = StockService.get_all_stocks(db, search=ticker, limit=1)
    return stocks[0] if stocks else updated


@router.delete("/{ticker}", status_code=204)
def delete_stock(ticker: str, db: Session = Depends(get_db)):
    """Delete stock (only if no transactions exist)"""
    try:
        success = StockService.delete_stock(ticker, db)

        if not success:
            raise HTTPException(status_code=404, detail="Stock not found")

        return None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{ticker}/enrich")
def trigger_enrichment(
    ticker: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Manually trigger enrichment for a stock"""
    from models.database import Stock

    stock = db.query(Stock).filter(Stock.ticker == ticker).first()

    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Trigger enrichment
    background_tasks.add_task(
        EnrichmentService.enrich_stock,
        ticker,
        db
    )

    return {"message": f"Enrichment triggered for {ticker}"}


@router.get("/filters/sectors")
def get_sectors(db: Session = Depends(get_db)):
    """Get list of all sectors"""
    return StockService.get_unique_sectors(db)


@router.get("/filters/industries")
def get_industries(db: Session = Depends(get_db)):
    """Get list of all industries"""
    return StockService.get_unique_industries(db)
