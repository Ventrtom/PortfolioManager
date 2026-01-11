"""
Stock Service - CRUD operations for stocks
"""
import json
import logging
from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from models.database import Stock, Transaction
from datetime import datetime

logger = logging.getLogger(__name__)

class StockService:
    """Service for stock management operations"""

    @staticmethod
    def create_stock(ticker: str, db: Session) -> Stock:
        """
        Create a new stock record (manual creation)
        Only ticker required - enrichment happens separately
        """
        ticker = ticker.upper().strip()

        # Check if exists
        existing = db.query(Stock).filter(Stock.ticker == ticker).first()
        if existing:
            logger.info(f"Stock {ticker} already exists")
            return existing

        # Create new stock
        stock = Stock(
            ticker=ticker,
            enrichment_status='pending',
            enrichment_attempts=0,
            is_manually_edited=False,
            created_at=datetime.utcnow()
        )

        db.add(stock)
        db.commit()
        db.refresh(stock)

        logger.info(f"Created new stock: {ticker}")
        return stock

    @staticmethod
    def get_all_stocks(
        db: Session,
        search: Optional[str] = None,
        sector: Optional[str] = None,
        industry: Optional[str] = None,
        status: Optional[str] = None,
        has_holdings: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Dict]:
        """
        Get all stocks with filtering and portfolio context
        Returns list with holdings data embedded
        """
        query = db.query(Stock)

        # Apply filters
        if search:
            search_term = f"%{search.upper()}%"
            query = query.filter(
                or_(
                    Stock.ticker.like(search_term),
                    Stock.company_name.like(f"%{search}%")
                )
            )

        if sector:
            query = query.filter(Stock.sector == sector)

        if industry:
            query = query.filter(Stock.industry == industry)

        if status:
            query = query.filter(Stock.enrichment_status == status)

        # Get stocks
        stocks = query.order_by(Stock.ticker).offset(skip).limit(limit).all()

        # Add portfolio context
        result = []
        for stock in stocks:
            # Calculate holdings for this ticker
            holding_data = StockService._calculate_holding(stock.ticker, db)

            # Filter by has_holdings if specified
            if has_holdings is not None:
                if has_holdings and holding_data['quantity'] == 0:
                    continue
                if not has_holdings and holding_data['quantity'] > 0:
                    continue

            # Parse alternative symbols
            alt_symbols = []
            if stock.alternative_symbols:
                try:
                    alt_symbols = json.loads(stock.alternative_symbols)
                except:
                    pass

            result.append({
                'ticker': stock.ticker,
                'company_name': stock.company_name,
                'sector': stock.sector,
                'industry': stock.industry,
                'currency': stock.currency,
                'market_cap': stock.market_cap,
                'volume': stock.volume,
                'enrichment_status': stock.enrichment_status,
                'enrichment_error': stock.enrichment_error,
                'is_manually_edited': stock.is_manually_edited,
                'alternative_symbols': alt_symbols,
                'last_updated': stock.last_updated.isoformat() if stock.last_updated else None,
                # Portfolio context
                'holdings_quantity': holding_data['quantity'],
                'holdings_value': holding_data['market_value'],
                'cost_basis': holding_data['cost_basis'],
                'unrealized_gain': holding_data['unrealized_gain']
            })

        return result

    @staticmethod
    def _calculate_holding(ticker: str, db: Session) -> Dict:
        """Calculate current holdings for a ticker"""
        from services.portfolio_service import PortfolioService

        # Get all holdings
        holdings = PortfolioService.calculate_holdings(db)

        # Find this ticker
        for holding in holdings:
            if holding.ticker == ticker:
                return {
                    'quantity': holding.quantity,
                    'market_value': holding.market_value,
                    'cost_basis': holding.cost_basis,
                    'unrealized_gain': holding.unrealized_gain
                }

        return {
            'quantity': 0,
            'market_value': 0,
            'cost_basis': 0,
            'unrealized_gain': 0
        }

    @staticmethod
    def update_stock(
        ticker: str,
        updates: Dict,
        db: Session
    ) -> Optional[Stock]:
        """
        Update stock (manual edit)
        Sets is_manually_edited = True and status = 'manual'
        """
        stock = db.query(Stock).filter(Stock.ticker == ticker).first()

        if not stock:
            return None

        # Apply manual updates
        if 'company_name' in updates:
            stock.company_name = updates['company_name']
        if 'sector' in updates:
            stock.sector = updates['sector']
        if 'industry' in updates:
            stock.industry = updates['industry']
        if 'market_cap' in updates:
            stock.market_cap = updates['market_cap']
        if 'currency' in updates:
            stock.currency = updates['currency']

        # Mark as manually edited
        stock.is_manually_edited = True
        stock.enrichment_status = 'manual'
        stock.enrichment_error = None
        stock.last_updated = datetime.utcnow()

        db.commit()
        db.refresh(stock)

        logger.info(f"Manually updated stock: {ticker}")
        return stock

    @staticmethod
    def delete_stock(ticker: str, db: Session) -> bool:
        """Delete stock (only if no transactions exist)"""
        # Check for transactions
        txn_count = db.query(Transaction).filter(Transaction.ticker == ticker).count()

        if txn_count > 0:
            raise ValueError(f"Cannot delete {ticker} - {txn_count} transactions exist")

        stock = db.query(Stock).filter(Stock.ticker == ticker).first()

        if not stock:
            return False

        db.delete(stock)
        db.commit()

        logger.info(f"Deleted stock: {ticker}")
        return True

    @staticmethod
    def get_unique_sectors(db: Session) -> List[str]:
        """Get list of all sectors"""
        results = db.query(Stock.sector).filter(Stock.sector.isnot(None)).distinct().all()
        return sorted([r[0] for r in results])

    @staticmethod
    def get_unique_industries(db: Session) -> List[str]:
        """Get list of all industries"""
        results = db.query(Stock.industry).filter(Stock.industry.isnot(None)).distinct().all()
        return sorted([r[0] for r in results])
