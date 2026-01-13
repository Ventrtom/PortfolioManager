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


@router.get("/flagged", response_model=List[StockResponse])
def get_flagged_stocks(db: Session = Depends(get_db)):
    """
    Get all stocks with skip_price_fetch=True
    Returns list of flagged stocks with reason and failure count
    """
    from models.database import Stock

    flagged = db.query(Stock).filter(Stock.skip_price_fetch == True).all()

    # Convert to StockResponse format
    result = []
    for stock in flagged:
        result.append(StockResponse(
            ticker=stock.ticker,
            company_name=stock.company_name,
            sector=stock.sector,
            industry=stock.industry,
            currency=stock.currency,
            market_cap=stock.market_cap,
            volume=stock.volume,
            enrichment_status=stock.enrichment_status,
            enrichment_error=stock.enrichment_error,
            is_manually_edited=stock.is_manually_edited,
            alternative_symbols=[],
            last_updated=stock.last_updated.isoformat() if stock.last_updated else None,
            skip_price_fetch=stock.skip_price_fetch,
            skip_price_reason=stock.skip_price_reason,
            skip_price_since=stock.skip_price_since,
            consecutive_failures=stock.consecutive_failures,
            holdings_quantity=0,
            holdings_value=0,
            cost_basis=0,
            unrealized_gain=0
        ))

    return result


@router.patch("/{ticker}/skip-price")
def update_skip_price_flag(
    ticker: str,
    skip: bool,
    reason: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Manually toggle skip_price_fetch flag for a ticker
    If skip=True, requires reason
    If skip=False, clears flag and resets consecutive_failures counter
    """
    from models.database import Stock

    stock = db.query(Stock).filter(Stock.ticker == ticker).first()

    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    if skip:
        if not reason:
            raise HTTPException(status_code=400, detail="Reason required when setting skip flag")

        stock.skip_price_fetch = True
        stock.skip_price_reason = reason
        stock.skip_price_since = datetime.utcnow()
    else:
        # Clear the flag
        stock.skip_price_fetch = False
        stock.skip_price_reason = None
        stock.skip_price_since = None
        stock.consecutive_failures = 0

    db.commit()

    return {
        "message": f"Skip price flag {'enabled' if skip else 'disabled'} for {ticker}",
        "ticker": ticker,
        "skip_price_fetch": stock.skip_price_fetch,
        "skip_price_reason": stock.skip_price_reason,
        "skip_price_since": stock.skip_price_since.isoformat() if stock.skip_price_since else None
    }
