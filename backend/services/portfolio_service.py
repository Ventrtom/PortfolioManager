from sqlalchemy.orm import Session
from models.database import Transaction, Stock
from models.schemas import Holding, PortfolioSummary, IndustryAllocation, SectorAllocation
from services.market_data_service import MarketDataService
from services.exchange_rate_service import CurrencyNormalizer
from utils.calculations import FinancialCalculations, RealizedGainsCalculator
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Precision constant for financial calculations (8 decimal places)
FINANCIAL_PRECISION = Decimal('0.00000001')


def _to_decimal(value: float) -> Decimal:
    """Convert float to Decimal with proper precision for financial calculations."""
    return Decimal(str(value)).quantize(FINANCIAL_PRECISION, rounding=ROUND_HALF_UP)


def _to_float(value: Decimal) -> float:
    """Convert Decimal back to float for API compatibility."""
    return float(value)


def _is_zero(value: float, tolerance: float = 1e-8) -> bool:
    """Check if a float value is effectively zero within tolerance."""
    return abs(value) < tolerance


class PortfolioService:
    """Service for portfolio calculations and management"""

    @staticmethod
    def calculate_holdings(db: Session) -> List[Holding]:
        """
        Calculate current holdings from transaction history using FIFO method.

        Returns list of current positions with P&L.
        Handles stock splits, validates data integrity, and uses precise decimal math.
        """
        # Get all relevant transactions (BUY, SELL, SPLIT)
        transactions = db.query(Transaction).filter(
            Transaction.transaction_type.in_(['BUY', 'SELL', 'SPLIT'])
        ).order_by(Transaction.transaction_date.asc(), Transaction.id.asc()).all()

        if not transactions:
            logger.info("No transactions found - returning empty holdings")
            return []

        # Group by ticker and calculate positions using Decimal for precision
        # Track both native currency cost and CZK cost (normalized at transaction date)
        holdings_dict: Dict[str, Dict] = defaultdict(lambda: {
            'purchases': [],
            'total_quantity': Decimal('0'),
            'total_cost': Decimal('0'),  # Native currency cost
            'total_cost_czk': Decimal('0'),  # CZK cost at transaction dates
            'warnings': []
        })

        for txn in transactions:
            ticker = txn.ticker

            # Validate transaction data
            if txn.transaction_type in ['BUY', 'SELL'] and (txn.quantity is None or txn.quantity <= 0):
                logger.warning(f"Invalid quantity for transaction {txn.id}: {txn.quantity}")
                holdings_dict[ticker]['warnings'].append(
                    f"Transaction {txn.id} has invalid quantity: {txn.quantity}"
                )
                continue

            if txn.transaction_type == 'BUY' and (txn.price is None or txn.price <= 0):
                logger.warning(f"Invalid price for BUY transaction {txn.id}: {txn.price}")
                holdings_dict[ticker]['warnings'].append(
                    f"BUY transaction {txn.id} has invalid price: {txn.price}"
                )
                continue

            if txn.transaction_type == 'BUY':
                # Add to purchases list for FIFO tracking
                quantity = _to_decimal(txn.quantity)
                price = _to_decimal(txn.price)
                native_cost = quantity * price

                # Normalize cost to CZK at transaction date
                # This is the CRITICAL fix: use transaction date rate, not today's rate
                try:
                    txn_normalized = CurrencyNormalizer.normalize_transaction(txn, db)
                    # BUY amounts are stored as negative (money out), so take absolute value
                    cost_czk = _to_decimal(abs(txn_normalized['amount_czk']))
                    if txn_normalized['conversion_warning']:
                        holdings_dict[ticker]['warnings'].append(txn_normalized['conversion_warning'])
                except Exception as e:
                    # Fallback: use native cost (will be converted later if needed)
                    logger.warning(f"Failed to normalize BUY transaction {txn.id} to CZK: {e}")
                    cost_czk = native_cost  # Will be converted in get_portfolio_summary
                    holdings_dict[ticker]['warnings'].append(
                        f"Transaction {txn.id}: could not normalize to CZK at transaction date"
                    )

                holdings_dict[ticker]['purchases'].append({
                    'quantity': float(quantity),  # FIFO calculator expects float
                    'price': float(price),
                    'cost_czk': float(cost_czk),  # CZK cost at transaction date
                    'date': txn.transaction_date,
                    'transaction_id': txn.id
                })
                holdings_dict[ticker]['total_quantity'] += quantity
                holdings_dict[ticker]['total_cost'] += native_cost
                holdings_dict[ticker]['total_cost_czk'] += cost_czk

            elif txn.transaction_type == 'SELL':
                quantity_to_sell = _to_decimal(txn.quantity)
                current_quantity = holdings_dict[ticker]['total_quantity']

                # Validate: cannot sell more than we own
                if quantity_to_sell > current_quantity + Decimal('0.0001'):  # Small tolerance
                    logger.error(
                        f"SELL transaction {txn.id} for {ticker}: "
                        f"selling {quantity_to_sell} but only have {current_quantity}"
                    )
                    holdings_dict[ticker]['warnings'].append(
                        f"Overselling detected: SELL {quantity_to_sell} but holdings={current_quantity}"
                    )
                    # Adjust to sell only what we have
                    quantity_to_sell = current_quantity

                if quantity_to_sell > 0:
                    # Remove from purchases using FIFO
                    # Use the CZK-aware FIFO function to get CZK cost basis
                    cost_basis_czk, remaining_purchases = FinancialCalculations.calculate_fifo_cost_basis_czk(
                        holdings_dict[ticker]['purchases'],
                        float(quantity_to_sell)
                    )

                    # Also calculate native currency cost basis for backwards compatibility
                    cost_basis, _ = FinancialCalculations.calculate_fifo_cost_basis(
                        holdings_dict[ticker]['purchases'],
                        float(quantity_to_sell)
                    )

                    holdings_dict[ticker]['purchases'] = remaining_purchases
                    holdings_dict[ticker]['total_quantity'] -= quantity_to_sell
                    holdings_dict[ticker]['total_cost'] -= _to_decimal(cost_basis)
                    holdings_dict[ticker]['total_cost_czk'] -= _to_decimal(cost_basis_czk)

            elif txn.transaction_type == 'SPLIT':
                # Handle stock split: adjust quantity and average cost
                # Split ratio is stored in quantity field (e.g., 4.0 for 4:1 split)
                if txn.quantity and txn.quantity != 0:
                    split_ratio = _to_decimal(txn.quantity)

                    # Adjust all purchase lots
                    for purchase in holdings_dict[ticker]['purchases']:
                        purchase['quantity'] = float(_to_decimal(purchase['quantity']) * split_ratio)
                        purchase['price'] = float(_to_decimal(purchase['price']) / split_ratio)
                        # cost_czk stays the same - we paid the same CZK amount

                    # Adjust totals (cost basis stays same, quantity changes)
                    holdings_dict[ticker]['total_quantity'] *= split_ratio
                    # total_cost and total_cost_czk stay the same - we paid the same amount

                    logger.info(f"Applied {split_ratio}:1 split for {ticker}")

        # Pre-fetch all stock info in one query for efficiency
        active_tickers = [
            ticker for ticker, data in holdings_dict.items()
            if not _is_zero(float(data['total_quantity']))
        ]

        stock_info_cache: Dict[str, Dict] = {}
        if active_tickers:
            stocks = db.query(Stock).filter(Stock.ticker.in_(active_tickers)).all()
            for stock in stocks:
                stock_info_cache[stock.ticker] = {
                    'company_name': stock.company_name or stock.ticker,
                    'sector': stock.sector,
                    'industry': stock.industry,
                    'currency': stock.currency or 'USD'
                }

        # Build holdings list with current prices
        holdings = []
        for ticker, data in holdings_dict.items():
            quantity = float(data['total_quantity'])

            # Skip fully sold positions (using tolerance for floating-point comparison)
            if _is_zero(quantity):
                logger.debug(f"Skipping {ticker} - fully sold (quantity: {quantity})")
                continue

            # Warn about negative holdings (data integrity issue)
            if quantity < 0:
                logger.error(f"Negative holdings for {ticker}: {quantity} - data integrity issue!")
                continue

            # Get current price for active holdings with fallback strategy
            current_price = MarketDataService.get_current_price(ticker, db)
            price_warning = None

            if not current_price:
                # Fallback 1: Try to get the last known price from database (up to 365 days back)
                from services.historical_price_service import HistoricalPriceService
                last_known = HistoricalPriceService.get_last_known_price(
                    ticker, date.today() + timedelta(days=1), db, max_days_back=365
                )

                if last_known:
                    price_date, current_price = last_known
                    days_stale = (date.today() - price_date).days
                    price_warning = f"Using last known price from {price_date} ({days_stale} days ago)"
                    logger.warning(f"{ticker}: {price_warning}")
                else:
                    # Fallback 2: Use average purchase price
                    average_cost = float(data['total_cost']) / float(data['total_quantity']) if data['total_quantity'] > 0 else 0
                    if average_cost > 0:
                        current_price = average_cost
                        price_warning = "Using purchase price (no market price available)"
                        logger.warning(f"{ticker}: {price_warning}")
                    else:
                        logger.warning(f"Could not determine any price for {ticker}, skipping from holdings")
                        continue

            # Use cached stock info or fetch
            if ticker in stock_info_cache:
                stock_info = stock_info_cache[ticker]
            else:
                stock_info = MarketDataService.get_stock_info(ticker, db)
                if stock_info is None:
                    stock_info = {
                        'company_name': ticker,
                        'sector': None,
                        'industry': None
                    }

            # Calculate metrics with precision
            cost_basis = float(data['total_cost'])  # Native currency
            cost_basis_czk = float(data['total_cost_czk'])  # CZK at transaction dates
            average_cost = cost_basis / quantity if quantity > 0 else 0
            market_value = quantity * current_price
            unrealized_gain = market_value - cost_basis

            # Safe division for percentage
            if cost_basis > 0:
                unrealized_gain_percent = (unrealized_gain / cost_basis) * 100
            elif cost_basis == 0 and market_value > 0:
                unrealized_gain_percent = 100.0  # 100% gain if cost was 0
            else:
                unrealized_gain_percent = 0

            holding = Holding(
                ticker=ticker,
                company_name=stock_info.get('company_name', ticker),
                quantity=round(quantity, 8),  # Round for display
                average_cost=round(average_cost, 4),
                current_price=round(current_price, 4),
                market_value=round(market_value, 2),
                cost_basis=round(cost_basis, 2),
                cost_basis_czk=round(cost_basis_czk, 2),  # CZK cost at transaction dates
                unrealized_gain=round(unrealized_gain, 2),
                unrealized_gain_percent=round(unrealized_gain_percent, 2),
                sector=stock_info.get('sector'),
                industry=stock_info.get('industry')
            )
            holdings.append(holding)

            # Log warnings for this holding
            if data['warnings']:
                for warning in data['warnings']:
                    logger.warning(f"{ticker}: {warning}")

        # Sort by market value descending for consistent ordering
        holdings.sort(key=lambda h: h.market_value, reverse=True)

        logger.info(f"Calculated {len(holdings)} holdings from {len(transactions)} transactions")
        return holdings

    @staticmethod
    def get_portfolio_summary(db: Session) -> PortfolioSummary:
        """
        Calculate portfolio summary with currency normalization and realized gains.
        All values in CZK base currency.

        Uses semantic sign convention for cash flow:
        - Inflows (DEPOSIT, SELL, DIVIDEND, INTEREST): positive amounts
        - Outflows (WITHDRAWAL, BUY, FEE, TAX): negative amounts
        """
        holdings = PortfolioService.calculate_holdings(db)
        all_warnings: List[str] = []
        today = date.today()

        # Pre-fetch all stock currencies in one query for efficiency
        tickers = [h.ticker for h in holdings]
        stock_currencies: Dict[str, str] = {}
        if tickers:
            stocks = db.query(Stock).filter(Stock.ticker.in_(tickers)).all()
            stock_currencies = {s.ticker: (s.currency or 'USD') for s in stocks}

        # Normalize all holdings to CZK
        total_value_czk = Decimal('0')
        total_cost_basis_czk = Decimal('0')

        for holding in holdings:
            stock_currency = stock_currencies.get(holding.ticker, 'USD')

            # Convert market value to CZK using TODAY's exchange rate
            # (current value should use current rates)
            market_value_czk = CurrencyNormalizer.to_base_currency(
                holding.market_value,
                stock_currency,
                today,
                db
            )

            # Use pre-calculated cost_basis_czk from calculate_holdings()
            # This is the FIX: cost basis was already normalized to CZK at each
            # transaction's date, not today's date
            if holding.cost_basis_czk is not None:
                cost_basis_czk = holding.cost_basis_czk
            else:
                # Fallback for backwards compatibility: convert using today's rate
                # (This should rarely happen after the fix is applied)
                cost_basis_czk = CurrencyNormalizer.to_base_currency(
                    holding.cost_basis,
                    stock_currency,
                    today,
                    db
                )
                if cost_basis_czk is not None:
                    all_warnings.append(
                        f"{holding.ticker}: cost_basis_czk not pre-calculated, "
                        f"using today's rate (may be inaccurate)"
                    )

            if market_value_czk is None:
                all_warnings.append(
                    f"Failed to convert market value for {holding.ticker} "
                    f"({stock_currency} to CZK) - using 0"
                )
                market_value_czk = 0

            if cost_basis_czk is None:
                all_warnings.append(
                    f"Failed to convert cost basis for {holding.ticker} "
                    f"({stock_currency} to CZK) - using 0"
                )
                cost_basis_czk = 0

            total_value_czk += _to_decimal(market_value_czk)
            total_cost_basis_czk += _to_decimal(cost_basis_czk)

        # Calculate unrealized gain
        total_unrealized_gain_czk = total_value_czk - total_cost_basis_czk
        if total_cost_basis_czk > 0:
            total_unrealized_gain_percent = float(
                (total_unrealized_gain_czk / total_cost_basis_czk) * Decimal('100')
            )
        else:
            total_unrealized_gain_percent = 0.0

        # Calculate realized gains using FIFO
        total_realized_gain_czk = Decimal('0')
        try:
            total_realized_gain_czk = _to_decimal(
                RealizedGainsCalculator.calculate_total_realized_gains(db)
            )
        except KeyError as e:
            logger.error(f"Failed to calculate realized gains - missing field: {e}")
            all_warnings.append(f"Realized gains calculation failed: missing required field {str(e)}")
        except ValueError as e:
            logger.error(f"Failed to calculate realized gains - invalid data: {e}")
            all_warnings.append(f"Realized gains calculation failed: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to calculate realized gains: {e}", exc_info=True)
            all_warnings.append(f"Realized gains calculation failed: {str(e)}")

        # Calculate cash balance using unified method
        cash_balance_czk, cash_warnings = PortfolioService._calculate_cash_balance_internal(db, None)
        all_warnings.extend(cash_warnings)

        return PortfolioSummary(
            total_value=round(float(total_value_czk), 2),
            total_cost_basis=round(float(total_cost_basis_czk), 2),
            total_unrealized_gain=round(float(total_unrealized_gain_czk), 2),
            total_unrealized_gain_percent=round(total_unrealized_gain_percent, 2),
            total_realized_gain=round(float(total_realized_gain_czk), 2),
            cash_balance=round(cash_balance_czk, 2),
            number_of_holdings=len(holdings),
            currency='CZK',
            conversion_warnings=all_warnings if all_warnings else None
        )

    @staticmethod
    def _calculate_cash_balance_internal(
        db: Session,
        target_date: Optional[date]
    ) -> Tuple[float, List[str]]:
        """
        Internal method to calculate cash balance with consistent logic.

        Uses semantic sign convention - all transaction amounts already have
        correct signs based on their type:
        - Inflows (DEPOSIT, SELL, DIVIDEND, INTEREST): positive total_amount
        - Outflows (WITHDRAWAL, BUY, FEE, TAX): negative total_amount

        Args:
            db: Database session
            target_date: Calculate balance up to this date (None = all time)

        Returns:
            Tuple of (cash_balance_czk, list_of_warnings)
        """
        # All transaction types that affect cash
        cash_affecting_types = [
            'DEPOSIT', 'WITHDRAWAL', 'BUY', 'SELL', 'DIVIDEND', 'FEE', 'TAX', 'INTEREST'
        ]

        query = db.query(Transaction).filter(
            Transaction.transaction_type.in_(cash_affecting_types)
        )

        if target_date is not None:
            query = query.filter(Transaction.transaction_date <= target_date)

        cash_transactions = query.order_by(
            Transaction.transaction_date.asc(),
            Transaction.id.asc()
        ).all()

        cash_balance_czk = Decimal('0')
        warnings: List[str] = []

        for txn in cash_transactions:
            try:
                normalized = CurrencyNormalizer.normalize_transaction(txn, db)

                # With semantic sign convention, amounts already have correct sign:
                # - DEPOSIT, SELL, DIVIDEND, INTEREST: positive (adds to balance)
                # - WITHDRAWAL, BUY, FEE, TAX: negative (reduces balance)
                cash_balance_czk += _to_decimal(normalized['amount_czk'])

                if normalized['conversion_warning']:
                    warnings.append(normalized['conversion_warning'])

            except ValueError as e:
                # Conversion failed completely
                logger.error(f"Failed to normalize transaction {txn.id}: {e}")
                warnings.append(f"Transaction {txn.id} excluded from cash balance: {str(e)}")
            except Exception as e:
                logger.warning(f"Unexpected error normalizing transaction {txn.id}: {e}")
                warnings.append(f"Failed to process transaction {txn.id}")

        return float(cash_balance_czk), warnings

    @staticmethod
    def get_industry_allocation(
        db: Session,
        holdings: Optional[List[Holding]] = None
    ) -> List[IndustryAllocation]:
        """
        Calculate portfolio allocation by industry.

        Args:
            db: Database session
            holdings: Pre-calculated holdings (optional, avoids recalculation)

        Returns:
            List of industry allocations sorted by value descending
        """
        if holdings is None:
            holdings = PortfolioService.calculate_holdings(db)

        if not holdings:
            return []

        total_value = sum(h.market_value for h in holdings)

        if total_value <= 0:
            logger.warning("Total portfolio value is zero or negative")
            return []

        # Group by industry using Decimal for precision
        industry_dict: Dict[str, Dict] = defaultdict(
            lambda: {'value': Decimal('0'), 'count': 0}
        )

        for holding in holdings:
            industry = holding.industry or 'Unknown'
            industry_dict[industry]['value'] += _to_decimal(holding.market_value)
            industry_dict[industry]['count'] += 1

        # Build allocation list
        allocations = []
        total_value_decimal = _to_decimal(total_value)

        for industry, data in industry_dict.items():
            percentage = float((data['value'] / total_value_decimal) * Decimal('100'))
            allocations.append(IndustryAllocation(
                industry=industry,
                value=round(float(data['value']), 2),
                percentage=round(percentage, 2),
                count=data['count']
            ))

        # Sort by value descending
        allocations.sort(key=lambda x: x.value, reverse=True)

        return allocations

    @staticmethod
    def get_sector_allocation(
        db: Session,
        holdings: Optional[List[Holding]] = None
    ) -> List[SectorAllocation]:
        """
        Calculate portfolio allocation by sector.

        Args:
            db: Database session
            holdings: Pre-calculated holdings (optional, avoids recalculation)

        Returns:
            List of sector allocations sorted by value descending
        """
        if holdings is None:
            holdings = PortfolioService.calculate_holdings(db)

        if not holdings:
            return []

        total_value = sum(h.market_value for h in holdings)

        if total_value <= 0:
            logger.warning("Total portfolio value is zero or negative")
            return []

        # Group by sector using Decimal for precision
        sector_dict: Dict[str, Dict] = defaultdict(
            lambda: {'value': Decimal('0'), 'count': 0}
        )

        for holding in holdings:
            sector = holding.sector or 'Unknown'
            sector_dict[sector]['value'] += _to_decimal(holding.market_value)
            sector_dict[sector]['count'] += 1

        # Build allocation list
        allocations = []
        total_value_decimal = _to_decimal(total_value)

        for sector, data in sector_dict.items():
            percentage = float((data['value'] / total_value_decimal) * Decimal('100'))
            allocations.append(SectorAllocation(
                sector=sector,
                value=round(float(data['value']), 2),
                percentage=round(percentage, 2),
                count=data['count']
            ))

        # Sort by value descending
        allocations.sort(key=lambda x: x.value, reverse=True)

        return allocations

    @staticmethod
    def get_all_allocations(db: Session) -> Dict:
        """
        Get both industry and sector allocations efficiently.
        Calculates holdings only once.

        Returns:
            {
                'holdings': List[Holding],
                'industry_allocation': List[IndustryAllocation],
                'sector_allocation': List[SectorAllocation]
            }
        """
        holdings = PortfolioService.calculate_holdings(db)

        return {
            'holdings': holdings,
            'industry_allocation': PortfolioService.get_industry_allocation(db, holdings),
            'sector_allocation': PortfolioService.get_sector_allocation(db, holdings)
        }

    @staticmethod
    def get_cash_balance_at_date(db: Session, target_date: date) -> float:
        """
        Calculate cash balance up to (and including) a specific date.
        Used for validation of BUY/WITHDRAWAL transactions.

        Uses the same unified calculation logic as get_portfolio_summary().

        Args:
            db: Database session
            target_date: Calculate balance up to this date

        Returns:
            Cash balance in CZK at the specified date
        """
        cash_balance, warnings = PortfolioService._calculate_cash_balance_internal(db, target_date)

        # Log warnings but don't fail - validation should be lenient
        for warning in warnings:
            logger.warning(f"Cash balance at {target_date}: {warning}")

        return cash_balance

    @staticmethod
    def refresh_portfolio_prices(db: Session) -> Dict[str, float]:
        """
        Refresh current prices for all holdings.

        Returns:
            Dict of {ticker: price}
        """
        holdings = PortfolioService.calculate_holdings(db)
        tickers = [h.ticker for h in holdings]

        if hasattr(MarketDataService, 'refresh_all_prices'):
            return MarketDataService.refresh_all_prices(tickers, db)

        # Fallback if refresh_all_prices doesn't exist
        result = {}
        for ticker in tickers:
            price = MarketDataService.get_current_price(ticker, db)
            if price:
                result[ticker] = price
        return result

    @staticmethod
    def validate_portfolio_integrity(db: Session) -> Dict:
        """
        Validate portfolio data integrity.

        Checks for:
        - Negative holdings (sells without buys)
        - Missing exchange rates
        - Invalid transaction data
        - Orphaned transactions (tickers without stock records)

        Returns:
            {
                'valid': bool,
                'errors': List[str],
                'warnings': List[str],
                'stats': {
                    'total_transactions': int,
                    'total_tickers': int,
                    'holdings_count': int,
                    'cash_balance_czk': float
                }
            }
        """
        errors: List[str] = []
        warnings: List[str] = []

        # Get all transactions
        all_transactions = db.query(Transaction).all()
        total_transactions = len(all_transactions)

        # Check for invalid transactions
        for txn in all_transactions:
            if txn.transaction_type in ['BUY', 'SELL']:
                if txn.quantity is None or txn.quantity <= 0:
                    errors.append(
                        f"Transaction {txn.id} ({txn.transaction_type} {txn.ticker}): "
                        f"invalid quantity {txn.quantity}"
                    )
                if txn.transaction_type == 'BUY' and (txn.price is None or txn.price <= 0):
                    errors.append(
                        f"Transaction {txn.id} (BUY {txn.ticker}): invalid price {txn.price}"
                    )

            if txn.total_amount is None:
                errors.append(f"Transaction {txn.id}: missing total_amount")

        # Get unique tickers
        tickers = set(
            txn.ticker for txn in all_transactions
            if txn.ticker and txn.transaction_type in ['BUY', 'SELL', 'DIVIDEND']
        )

        # Check for orphaned tickers (no stock record)
        for ticker in tickers:
            stock = db.query(Stock).filter(Stock.ticker == ticker).first()
            if not stock:
                warnings.append(f"Ticker {ticker} has transactions but no stock record")

        # Calculate holdings and check for issues
        holdings = PortfolioService.calculate_holdings(db)

        # Check cash balance
        try:
            cash_balance, cash_warnings = PortfolioService._calculate_cash_balance_internal(db, None)
            warnings.extend(cash_warnings)

            if cash_balance < -1:  # Allow small negative due to rounding
                warnings.append(f"Negative cash balance: {cash_balance:.2f} CZK")
        except Exception as e:
            errors.append(f"Cash balance calculation failed: {str(e)}")
            cash_balance = 0

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'stats': {
                'total_transactions': total_transactions,
                'total_tickers': len(tickers),
                'holdings_count': len(holdings),
                'cash_balance_czk': round(cash_balance, 2)
            }
        }

    @staticmethod
    def get_holdings_for_ticker(db: Session, ticker: str) -> Optional[Holding]:
        """
        Get holding information for a specific ticker.

        More efficient than calculate_holdings() when only one ticker is needed.

        Args:
            db: Database session
            ticker: Stock ticker to look up

        Returns:
            Holding object or None if not held
        """
        # Get transactions for this ticker only
        transactions = db.query(Transaction).filter(
            Transaction.ticker == ticker,
            Transaction.transaction_type.in_(['BUY', 'SELL', 'SPLIT'])
        ).order_by(Transaction.transaction_date.asc(), Transaction.id.asc()).all()

        if not transactions:
            return None

        total_quantity = Decimal('0')
        total_cost = Decimal('0')
        purchases = []

        for txn in transactions:
            if txn.transaction_type == 'BUY':
                if txn.quantity and txn.quantity > 0 and txn.price and txn.price > 0:
                    quantity = _to_decimal(txn.quantity)
                    price = _to_decimal(txn.price)

                    purchases.append({
                        'quantity': float(quantity),
                        'price': float(price),
                        'date': txn.transaction_date
                    })
                    total_quantity += quantity
                    total_cost += quantity * price

            elif txn.transaction_type == 'SELL':
                if txn.quantity and txn.quantity > 0:
                    quantity_to_sell = _to_decimal(txn.quantity)

                    if quantity_to_sell <= total_quantity:
                        cost_basis, purchases = FinancialCalculations.calculate_fifo_cost_basis(
                            purchases, float(quantity_to_sell)
                        )
                        total_quantity -= quantity_to_sell
                        total_cost -= _to_decimal(cost_basis)

            elif txn.transaction_type == 'SPLIT':
                if txn.quantity and txn.quantity != 0:
                    split_ratio = _to_decimal(txn.quantity)
                    for purchase in purchases:
                        purchase['quantity'] = float(_to_decimal(purchase['quantity']) * split_ratio)
                        purchase['price'] = float(_to_decimal(purchase['price']) / split_ratio)
                    total_quantity *= split_ratio

        quantity = float(total_quantity)

        if _is_zero(quantity) or quantity < 0:
            return None

        # Get current price with fallback strategy
        current_price = MarketDataService.get_current_price(ticker, db)

        if not current_price:
            # Fallback 1: Try last known price from database (up to 365 days back)
            from services.historical_price_service import HistoricalPriceService
            last_known = HistoricalPriceService.get_last_known_price(
                ticker, date.today() + timedelta(days=1), db, max_days_back=365
            )

            if last_known:
                _, current_price = last_known
                logger.warning(f"{ticker}: Using last known price {current_price}")
            else:
                # Fallback 2: Use average purchase price
                cost_basis_temp = float(total_cost)
                average_cost_temp = cost_basis_temp / quantity if quantity > 0 else 0
                if average_cost_temp > 0:
                    current_price = average_cost_temp
                    logger.warning(f"{ticker}: Using purchase price {current_price} (no market price available)")
                else:
                    return None

        # Get stock info
        stock = db.query(Stock).filter(Stock.ticker == ticker).first()
        stock_info = {
            'company_name': stock.company_name if stock else ticker,
            'sector': stock.sector if stock else None,
            'industry': stock.industry if stock else None
        }

        cost_basis = float(total_cost)
        average_cost = cost_basis / quantity if quantity > 0 else 0
        market_value = quantity * current_price
        unrealized_gain = market_value - cost_basis
        unrealized_gain_percent = (unrealized_gain / cost_basis * 100) if cost_basis > 0 else 0

        return Holding(
            ticker=ticker,
            company_name=stock_info['company_name'],
            quantity=round(quantity, 8),
            average_cost=round(average_cost, 4),
            current_price=round(current_price, 4),
            market_value=round(market_value, 2),
            cost_basis=round(cost_basis, 2),
            unrealized_gain=round(unrealized_gain, 2),
            unrealized_gain_percent=round(unrealized_gain_percent, 2),
            sector=stock_info['sector'],
            industry=stock_info['industry']
        )
