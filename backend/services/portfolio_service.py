from sqlalchemy.orm import Session
from models.database import Transaction, Stock
from models.schemas import Holding, PortfolioSummary, IndustryAllocation, SectorAllocation
from services.market_data_service import MarketDataService
from services.exchange_rate_service import CurrencyNormalizer
from utils.calculations import FinancialCalculations, RealizedGainsCalculator
from typing import List, Dict
from collections import defaultdict
from datetime import date
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

            # Handle case where stock info is unavailable
            if stock_info is None:
                stock_info = {
                    'company_name': ticker,
                    'sector': None,
                    'industry': None
                }

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
        Calculate portfolio summary with currency normalization and realized gains.
        All values in CZK base currency.
        """
        holdings = PortfolioService.calculate_holdings(db)
        all_warnings = []
        today = date.today()

        # CRITICAL FIX: Normalize all holdings to CZK
        total_value_czk = 0
        total_cost_basis_czk = 0

        for holding in holdings:
            # Get stock currency
            stock = db.query(Stock).filter(Stock.ticker == holding.ticker).first()
            stock_currency = stock.currency if stock else 'USD'

            # Convert market value to CZK
            market_value_czk = CurrencyNormalizer.to_base_currency(
                holding.market_value,
                stock_currency,
                today,
                db
            )

            # Convert cost basis to CZK
            cost_basis_czk = CurrencyNormalizer.to_base_currency(
                holding.cost_basis,
                stock_currency,
                today,
                db
            )

            if market_value_czk is None:
                all_warnings.append(f"Failed to convert market value for {holding.ticker} ({stock_currency} to CZK)")
                market_value_czk = 0

            if cost_basis_czk is None:
                all_warnings.append(f"Failed to convert cost basis for {holding.ticker} ({stock_currency} to CZK)")
                cost_basis_czk = 0

            total_value_czk += market_value_czk
            total_cost_basis_czk += cost_basis_czk

        # Calculate unrealized gain
        total_unrealized_gain_czk = total_value_czk - total_cost_basis_czk
        total_unrealized_gain_percent = (
            (total_unrealized_gain_czk / total_cost_basis_czk * 100) if total_cost_basis_czk > 0 else 0
        )

        # CRITICAL FIX: Calculate realized gains using FIFO
        try:
            total_realized_gain_czk = RealizedGainsCalculator.calculate_total_realized_gains(db)
        except KeyError as e:
            logger.error(f"Failed to calculate realized gains - missing field: {e}")
            all_warnings.append(f"Realized gains calculation failed: missing required field {str(e)}")
            total_realized_gain_czk = 0
        except ValueError as e:
            logger.error(f"Failed to calculate realized gains - invalid data: {e}")
            all_warnings.append(f"Realized gains calculation failed: {str(e)}")
            total_realized_gain_czk = 0
        except Exception as e:
            logger.error(f"Failed to calculate realized gains: {e}", exc_info=True)
            all_warnings.append(f"Realized gains calculation failed: {str(e)}")
            total_realized_gain_czk = 0

        # Calculate cash balance (all transaction types affecting cash)
        cash_transactions = db.query(Transaction).filter(
            Transaction.transaction_type.in_(['DEPOSIT', 'WITHDRAWAL', 'BUY', 'SELL', 'DIVIDEND', 'FEE', 'TAX'])
        ).order_by(Transaction.transaction_date.asc(), Transaction.id.asc()).all()

        cash_balance_czk = 0
        for txn in cash_transactions:
            try:
                normalized = CurrencyNormalizer.normalize_transaction(txn, db)

                # With semantic sign convention, just add all amounts:
                # - Negative transactions (BUY, FEE, TAX, WITHDRAWAL) reduce balance
                # - Positive transactions (SELL, DIVIDEND, DEPOSIT, INTEREST) increase balance
                cash_balance_czk += normalized['amount_czk']

                if normalized['conversion_warning']:
                    all_warnings.append(normalized['conversion_warning'])
            except Exception as e:
                logger.warning(f"Failed to normalize transaction {txn.id}: {e}")
                all_warnings.append(f"Failed to normalize transaction {txn.id}")

        return PortfolioSummary(
            total_value=total_value_czk,
            total_cost_basis=total_cost_basis_czk,
            total_unrealized_gain=total_unrealized_gain_czk,
            total_unrealized_gain_percent=total_unrealized_gain_percent,
            total_realized_gain=total_realized_gain_czk,
            cash_balance=cash_balance_czk,
            number_of_holdings=len(holdings),
            currency='CZK',
            conversion_warnings=all_warnings if all_warnings else None
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
    def get_cash_balance_at_date(db: Session, target_date: date) -> float:
        """
        Calculate cash balance up to (and including) a specific date.
        Used for validation of BUY/WITHDRAWAL transactions.

        Args:
            db: Database session
            target_date: Calculate balance up to this date

        Returns:
            Cash balance in CZK at the specified date
        """
        cash_transactions = db.query(Transaction).filter(
            Transaction.transaction_type.in_(['DEPOSIT', 'WITHDRAWAL', 'BUY', 'SELL', 'DIVIDEND', 'FEE', 'TAX']),
            Transaction.transaction_date <= target_date
        ).order_by(Transaction.transaction_date.asc(), Transaction.id.asc()).all()

        cash_balance_czk = 0

        for txn in cash_transactions:
            try:
                normalized = CurrencyNormalizer.normalize_transaction(txn, db)

                if txn.transaction_type == 'DEPOSIT':
                    cash_balance_czk += normalized['amount_czk']
                elif txn.transaction_type == 'WITHDRAWAL':
                    cash_balance_czk += normalized['amount_czk']  # Already negative
                elif txn.transaction_type == 'BUY':
                    cash_balance_czk -= normalized['amount_czk']
                elif txn.transaction_type == 'SELL':
                    cash_balance_czk += normalized['amount_czk']
                elif txn.transaction_type == 'DIVIDEND':
                    cash_balance_czk += normalized['amount_czk']
                elif txn.transaction_type == 'FEE':
                    cash_balance_czk += normalized['amount_czk']
                elif txn.transaction_type == 'TAX':
                    cash_balance_czk += normalized['amount_czk']
            except Exception as e:
                logger.warning(f"Failed to normalize transaction {txn.id} in cash calculation: {e}")

        return cash_balance_czk

    @staticmethod
    def refresh_portfolio_prices(db: Session) -> Dict[str, float]:
        """
        Refresh current prices for all holdings
        Returns dict of {ticker: price}
        """
        holdings = PortfolioService.calculate_holdings(db)
        tickers = [h.ticker for h in holdings]

        return MarketDataService.refresh_all_prices(tickers, db)
