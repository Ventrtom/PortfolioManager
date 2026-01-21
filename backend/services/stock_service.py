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
                'resolved_symbol': stock.resolved_symbol,
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
                'unrealized_gain': holding_data['unrealized_gain'],
                # Price fetch skip flags
                'skip_price_fetch': stock.skip_price_fetch,
                'skip_price_reason': stock.skip_price_reason,
                'skip_price_since': stock.skip_price_since.isoformat() if stock.skip_price_since else None,
                'consecutive_failures': stock.consecutive_failures
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
    def get_all_stocks_lightweight(
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
        Get all stocks WITHOUT live price calculations - instant load.
        Uses cached holdings data from database instead of recalculating.
        """
        # First, get all holdings data in ONE query using stored prices
        from models.database import StockPrice
        from datetime import date

        # Get holdings summary by calculating from transactions ONCE
        holdings_map = StockService._get_holdings_summary(db)

        # Query stocks with filters
        query = db.query(Stock)

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

        stocks = query.order_by(Stock.ticker).offset(skip).limit(limit).all()

        # Build result
        result = []
        for stock in stocks:
            # Get holdings from pre-calculated map
            holding_data = holdings_map.get(stock.ticker, {
                'quantity': 0,
                'market_value': 0,
                'cost_basis': 0,
                'unrealized_gain': 0
            })

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
                'resolved_symbol': stock.resolved_symbol,
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
                # Portfolio context from pre-calculated holdings (native currency)
                'holdings_quantity': holding_data['quantity'],
                'holdings_value': holding_data['market_value'],
                'cost_basis': holding_data['cost_basis'],
                'unrealized_gain': holding_data['unrealized_gain'],
                'current_price': holding_data.get('current_price'),
                'average_cost': holding_data.get('average_cost'),
                # Portfolio context in CZK
                'current_price_czk': holding_data.get('current_price_czk'),
                'holdings_value_czk': holding_data.get('holdings_value_czk', 0),
                'cost_basis_czk': holding_data.get('cost_basis_czk', 0),
                'unrealized_gain_czk': holding_data.get('unrealized_gain_czk', 0),
                'average_cost_czk': holding_data.get('average_cost_czk'),
                # Price fetch skip flags
                'skip_price_fetch': stock.skip_price_fetch,
                'skip_price_reason': stock.skip_price_reason,
                'skip_price_since': stock.skip_price_since.isoformat() if stock.skip_price_since else None,
                'consecutive_failures': stock.consecutive_failures
            })

        return result

    @staticmethod
    def _get_holdings_summary(db: Session) -> Dict[str, Dict]:
        """
        Calculate holdings summary for all tickers ONCE using cached prices.
        Returns dict of {ticker: {quantity, market_value, cost_basis, unrealized_gain, ...}}

        Includes both native currency values and CZK-converted values for display.
        """
        from models.database import StockPrice
        from datetime import date
        from decimal import Decimal
        from services.exchange_rate_service import CurrencyNormalizer

        today = date.today()

        # Get all BUY/SELL/SPLIT transactions
        transactions = db.query(Transaction).filter(
            Transaction.transaction_type.in_(['BUY', 'SELL', 'SPLIT'])
        ).order_by(Transaction.transaction_date.asc(), Transaction.id.asc()).all()

        if not transactions:
            return {}

        # Calculate holdings per ticker
        # Track both native currency cost and CZK cost (at transaction dates)
        holdings_dict: Dict[str, Dict] = {}

        for txn in transactions:
            ticker = txn.ticker

            if ticker not in holdings_dict:
                holdings_dict[ticker] = {
                    'quantity': Decimal('0'),
                    'cost_basis': Decimal('0'),  # Native currency
                    'cost_basis_czk': Decimal('0'),  # CZK at transaction dates
                    'purchases': []
                }

            if txn.transaction_type == 'BUY':
                if txn.quantity and txn.quantity > 0 and txn.price and txn.price > 0:
                    quantity = Decimal(str(txn.quantity))
                    price = Decimal(str(txn.price))
                    cost = quantity * price

                    # Get CZK cost at transaction date
                    # BUY amounts are stored negative (money out), so use absolute value
                    cost_czk = abs(txn.amount_czk) if txn.amount_czk else float(cost)

                    holdings_dict[ticker]['purchases'].append({
                        'quantity': float(quantity),
                        'price': float(price),
                        'cost_czk': cost_czk
                    })
                    holdings_dict[ticker]['quantity'] += quantity
                    holdings_dict[ticker]['cost_basis'] += cost
                    holdings_dict[ticker]['cost_basis_czk'] += Decimal(str(cost_czk))

            elif txn.transaction_type == 'SELL':
                if txn.quantity and txn.quantity > 0:
                    quantity_to_sell = Decimal(str(txn.quantity))

                    # FIFO: remove from purchases
                    remaining = float(quantity_to_sell)
                    cost_removed = Decimal('0')
                    cost_czk_removed = Decimal('0')
                    new_purchases = []

                    for purchase in holdings_dict[ticker]['purchases']:
                        if remaining <= 0:
                            new_purchases.append(purchase)
                            continue

                        if purchase['quantity'] <= remaining:
                            remaining -= purchase['quantity']
                            cost_removed += Decimal(str(purchase['quantity'])) * Decimal(str(purchase['price']))
                            cost_czk_removed += Decimal(str(purchase.get('cost_czk', purchase['quantity'] * purchase['price'])))
                        else:
                            fraction = remaining / purchase['quantity']
                            cost_removed += Decimal(str(remaining)) * Decimal(str(purchase['price']))
                            cost_czk_removed += Decimal(str(purchase.get('cost_czk', purchase['quantity'] * purchase['price']))) * Decimal(str(fraction))
                            purchase['quantity'] -= remaining
                            purchase['cost_czk'] = purchase.get('cost_czk', 0) * (1 - fraction)
                            remaining = 0
                            new_purchases.append(purchase)

                    holdings_dict[ticker]['purchases'] = new_purchases
                    holdings_dict[ticker]['quantity'] -= quantity_to_sell
                    holdings_dict[ticker]['cost_basis'] -= cost_removed
                    holdings_dict[ticker]['cost_basis_czk'] -= cost_czk_removed

            elif txn.transaction_type == 'SPLIT':
                if txn.quantity and txn.quantity != 0:
                    split_ratio = Decimal(str(txn.quantity))
                    for purchase in holdings_dict[ticker]['purchases']:
                        purchase['quantity'] = float(Decimal(str(purchase['quantity'])) * split_ratio)
                        purchase['price'] = float(Decimal(str(purchase['price'])) / split_ratio)
                        # cost_czk stays the same - we paid the same CZK amount
                    holdings_dict[ticker]['quantity'] *= split_ratio

        # Get latest cached prices for active holdings
        active_tickers = [t for t, d in holdings_dict.items() if float(d['quantity']) > 0.0001]

        # Get most recent price for each ticker from StockPrice table
        price_map: Dict[str, float] = {}
        if active_tickers:
            # Get the latest price date for each ticker
            subquery = db.query(
                StockPrice.ticker,
                func.max(StockPrice.price_date).label('max_date')
            ).filter(
                StockPrice.ticker.in_(active_tickers)
            ).group_by(StockPrice.ticker).subquery()

            # Join to get the actual prices
            prices = db.query(StockPrice).join(
                subquery,
                (StockPrice.ticker == subquery.c.ticker) &
                (StockPrice.price_date == subquery.c.max_date)
            ).all()

            for p in prices:
                price_map[p.ticker] = p.price

        # Get stock currencies for conversion
        stock_currencies: Dict[str, str] = {}
        if active_tickers:
            stocks = db.query(Stock).filter(Stock.ticker.in_(active_tickers)).all()
            stock_currencies = {s.ticker: (s.currency or 'USD') for s in stocks}

        # Build result with market values
        result: Dict[str, Dict] = {}
        for ticker, data in holdings_dict.items():
            quantity = float(data['quantity'])

            if quantity < 0.0001:
                continue

            cost_basis = float(data['cost_basis'])
            cost_basis_czk = float(data['cost_basis_czk'])
            stock_currency = stock_currencies.get(ticker, 'USD')

            # Use cached price or fall back to average cost
            current_price = price_map.get(ticker)
            if current_price is None:
                # Fallback: use average purchase price
                current_price = cost_basis / quantity if quantity > 0 else 0

            market_value = quantity * current_price
            unrealized_gain = market_value - cost_basis

            # Calculate average cost per share (native currency)
            average_cost = cost_basis / quantity if quantity > 0 else 0

            # Convert current price to CZK using today's rate
            current_price_czk = CurrencyNormalizer.to_base_currency(
                current_price, stock_currency, today, db
            )
            if current_price_czk is None:
                current_price_czk = current_price  # Fallback to native price

            # Calculate CZK market value using today's rate
            market_value_czk = quantity * current_price_czk

            # Calculate unrealized gain in CZK
            unrealized_gain_czk = market_value_czk - cost_basis_czk

            # Calculate average cost in CZK
            average_cost_czk = cost_basis_czk / quantity if quantity > 0 else 0

            result[ticker] = {
                # Native currency values
                'quantity': round(quantity, 8),
                'market_value': round(market_value, 2),
                'cost_basis': round(cost_basis, 2),
                'unrealized_gain': round(unrealized_gain, 2),
                'current_price': round(current_price, 4) if current_price else None,
                'average_cost': round(average_cost, 4) if average_cost else None,
                # CZK values
                'current_price_czk': round(current_price_czk, 4) if current_price_czk else None,
                'holdings_value_czk': round(market_value_czk, 2),
                'cost_basis_czk': round(cost_basis_czk, 2),
                'unrealized_gain_czk': round(unrealized_gain_czk, 2),
                'average_cost_czk': round(average_cost_czk, 4) if average_cost_czk else None
            }

        return result

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
