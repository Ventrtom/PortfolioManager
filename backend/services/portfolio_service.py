from sqlalchemy.orm import Session
from models.database import Transaction
from models.schemas import Holding, PortfolioSummary, IndustryAllocation, SectorAllocation
from services.market_data_service import MarketDataService
from utils.calculations import FinancialCalculations
from typing import List, Dict
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PortfolioService:
    """Service for portfolio calculations and management"""

    @staticmethod
    def calculate_holdings(db: Session) -> List[Holding]:
        """
        Calculate current holdings from transaction history
        Returns list of current positions with P&L
        """
        # Get all BUY and SELL transactions
        transactions = db.query(Transaction).filter(
            Transaction.transaction_type.in_(['BUY', 'SELL'])
        ).order_by(Transaction.transaction_date.asc(), Transaction.id.asc()).all()

        # Group by ticker and calculate positions
        holdings_dict = defaultdict(lambda: {
            'purchases': [],
            'total_quantity': 0,
            'total_cost': 0
        })

        for txn in transactions:
            ticker = txn.ticker

            if txn.transaction_type == 'BUY':
                # Add to purchases list for FIFO tracking
                holdings_dict[ticker]['purchases'].append({
                    'quantity': txn.quantity,
                    'price': txn.price,
                    'date': txn.transaction_date
                })
                holdings_dict[ticker]['total_quantity'] += txn.quantity
                holdings_dict[ticker]['total_cost'] += txn.quantity * txn.price

            elif txn.transaction_type == 'SELL':
                # Remove from purchases using FIFO
                quantity_to_sell = txn.quantity
                cost_basis, remaining_purchases = FinancialCalculations.calculate_fifo_cost_basis(
                    holdings_dict[ticker]['purchases'],
                    quantity_to_sell
                )

                holdings_dict[ticker]['purchases'] = remaining_purchases
                holdings_dict[ticker]['total_quantity'] -= quantity_to_sell
                holdings_dict[ticker]['total_cost'] -= cost_basis

        # Build holdings list with current prices
        holdings = []
        for ticker, data in holdings_dict.items():
            # IMPORTANT: Skip fully sold positions BEFORE fetching price
            # This prevents infinite API retries for tickers that no longer have holdings
            if data['total_quantity'] <= 0:
                logger.debug(f"Skipping {ticker} - no current holdings (quantity: {data['total_quantity']})")
                continue

            # Get current price only for active holdings
            current_price = MarketDataService.get_current_price(ticker, db)
            if not current_price:
                logger.warning(f"Could not fetch price for {ticker}, skipping from holdings")
                continue

            # Get stock info
            stock_info = MarketDataService.get_stock_info(ticker, db)

            # Calculate metrics
            quantity = data['total_quantity']
            cost_basis = data['total_cost']
            average_cost = cost_basis / quantity if quantity > 0 else 0
            market_value = quantity * current_price
            unrealized_gain = market_value - cost_basis
            unrealized_gain_percent = (unrealized_gain / cost_basis * 100) if cost_basis > 0 else 0

            holding = Holding(
                ticker=ticker,
                company_name=stock_info.get('company_name', ticker),
                quantity=quantity,
                average_cost=average_cost,
                current_price=current_price,
                market_value=market_value,
                cost_basis=cost_basis,
                unrealized_gain=unrealized_gain,
                unrealized_gain_percent=unrealized_gain_percent,
                sector=stock_info.get('sector'),
                industry=stock_info.get('industry')
            )
            holdings.append(holding)

        return holdings

    @staticmethod
    def get_portfolio_summary(db: Session) -> PortfolioSummary:
        """
        Calculate portfolio summary statistics
        """
        holdings = PortfolioService.calculate_holdings(db)

        # Calculate totals
        total_value = sum(h.market_value for h in holdings)
        total_cost_basis = sum(h.cost_basis for h in holdings)
        total_unrealized_gain = sum(h.unrealized_gain for h in holdings)
        total_unrealized_gain_percent = (
            (total_unrealized_gain / total_cost_basis * 100) if total_cost_basis > 0 else 0
        )

        # Calculate realized gains from SELL transactions
        sell_transactions = db.query(Transaction).filter(
            Transaction.transaction_type == 'SELL'
        ).all()

        total_realized_gain = 0
        # This is simplified - in real scenario, we'd need to match sells with buys
        # For now, just sum up the differences
        for sell in sell_transactions:
            if sell.price and sell.quantity:
                # We'd need to look up the cost basis for the sold shares
                # For simplicity, we'll calculate this later with more detailed tracking
                pass

        # Calculate cash balance from fees, dividends, etc.
        cash_transactions = db.query(Transaction).filter(
            Transaction.transaction_type.in_(['DIVIDEND', 'FEE', 'TAX'])
        ).all()

        cash_balance = sum(t.total_amount for t in cash_transactions)

        return PortfolioSummary(
            total_value=total_value,
            total_cost_basis=total_cost_basis,
            total_unrealized_gain=total_unrealized_gain,
            total_unrealized_gain_percent=total_unrealized_gain_percent,
            total_realized_gain=total_realized_gain,
            cash_balance=cash_balance,
            number_of_holdings=len(holdings)
        )

    @staticmethod
    def get_industry_allocation(db: Session) -> List[IndustryAllocation]:
        """
        Calculate portfolio allocation by industry
        """
        holdings = PortfolioService.calculate_holdings(db)
        total_value = sum(h.market_value for h in holdings)

        if total_value == 0:
            return []

        # Group by industry
        industry_dict = defaultdict(lambda: {'value': 0, 'count': 0})

        for holding in holdings:
            industry = holding.industry or 'Unknown'
            industry_dict[industry]['value'] += holding.market_value
            industry_dict[industry]['count'] += 1

        # Build allocation list
        allocations = []
        for industry, data in industry_dict.items():
            percentage = (data['value'] / total_value) * 100
            allocations.append(IndustryAllocation(
                industry=industry,
                value=data['value'],
                percentage=percentage,
                count=data['count']
            ))

        # Sort by value descending
        allocations.sort(key=lambda x: x.value, reverse=True)

        return allocations

    @staticmethod
    def get_sector_allocation(db: Session) -> List[SectorAllocation]:
        """
        Calculate portfolio allocation by sector
        """
        holdings = PortfolioService.calculate_holdings(db)
        total_value = sum(h.market_value for h in holdings)

        if total_value == 0:
            return []

        # Group by sector
        sector_dict = defaultdict(lambda: {'value': 0, 'count': 0})

        for holding in holdings:
            sector = holding.sector or 'Unknown'
            sector_dict[sector]['value'] += holding.market_value
            sector_dict[sector]['count'] += 1

        # Build allocation list
        allocations = []
        for sector, data in sector_dict.items():
            percentage = (data['value'] / total_value) * 100
            allocations.append(SectorAllocation(
                sector=sector,
                value=data['value'],
                percentage=percentage,
                count=data['count']
            ))

        # Sort by value descending
        allocations.sort(key=lambda x: x.value, reverse=True)

        return allocations

    @staticmethod
    def refresh_portfolio_prices(db: Session) -> Dict[str, float]:
        """
        Refresh current prices for all holdings
        Returns dict of {ticker: price}
        """
        holdings = PortfolioService.calculate_holdings(db)
        tickers = [h.ticker for h in holdings]

        return MarketDataService.refresh_all_prices(tickers, db)
