"""
Analytics Service - KPI calculations and snapshot management.

Provides:
- Historical portfolio performance tracking
- Diversification metrics (HHI, concentration)
- Volatility metrics (daily/annualized, Sharpe ratio)
- Dividend summary and yield calculations
- KPI snapshots for fast loading
"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from models.database import Transaction, Stock, PortfolioSnapshot
from models.schemas import (
    PerformanceDataPoint, DiversificationMetrics,
    VolatilityMetrics, DividendSummary, KPIResponse,
    PortfolioSummary, KPIResponseWithMetadata, SnapshotMetadata, SnapshotHistoryItem,
    Holding
)
from services.portfolio_service import PortfolioService
from services.market_data_service import MarketDataService
from services.historical_price_service import HistoricalPriceService
from services.exchange_rate_service import ExchangeRateService, CurrencyNormalizer
from utils.calculations import FinancialCalculations
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Tuple
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Precision helpers for financial calculations
FINANCIAL_PRECISION = Decimal('0.00000001')


def _to_decimal(value: float) -> Decimal:
    """Convert float to Decimal with proper precision."""
    if value is None:
        return Decimal('0')
    return Decimal(str(value)).quantize(FINANCIAL_PRECISION, rounding=ROUND_HALF_UP)


def _to_float(value: Decimal) -> float:
    """Convert Decimal back to float for API compatibility."""
    return float(value)


class AnalyticsService:
    """Service for calculating portfolio analytics and KPIs"""

    # Cache for expensive calculations within a single request
    _holdings_cache: Optional[Tuple[int, List[Holding]]] = None

    @classmethod
    def _get_cached_holdings(cls, db: Session) -> List[Holding]:
        """
        Get holdings with request-level caching.
        Cache key is based on transaction count to detect changes.
        """
        txn_count = db.query(func.count(Transaction.id)).scalar() or 0

        if cls._holdings_cache and cls._holdings_cache[0] == txn_count:
            return cls._holdings_cache[1]

        holdings = PortfolioService.calculate_holdings(db)
        cls._holdings_cache = (txn_count, holdings)
        return holdings

    @classmethod
    def clear_cache(cls):
        """Clear holdings cache - call after transaction changes."""
        cls._holdings_cache = None

    @staticmethod
    def get_performance_history(
        db: Session,
        days: int = 365,
        sample_interval: int = 3
    ) -> List[PerformanceDataPoint]:
        """
        Calculate historical portfolio performance with actual historical prices.
        All values normalized to CZK base currency.

        Optimized algorithm:
        1. Pre-calculate holdings state at each transaction date
        2. Only recalculate on transaction dates, interpolate between
        3. Use batch price lookups

        Args:
            db: Database session
            days: Number of days of history (default 365)
            sample_interval: Days between data points (default 3 for balance)

        Returns:
            List of PerformanceDataPoint sorted by date
        """
        # Get all transactions sorted by date
        transactions = db.query(Transaction).order_by(
            Transaction.transaction_date.asc(),
            Transaction.id.asc()
        ).all()

        if not transactions:
            return []

        # Determine date range
        end_date = date.today()
        start_date = max(
            transactions[0].transaction_date,
            end_date - timedelta(days=days)
        )

        # Get unique tickers for price pre-population
        tickers = set(
            txn.ticker for txn in transactions
            if txn.transaction_type in ['BUY', 'SELL'] and txn.ticker
        )

        # Pre-populate historical prices
        if tickers:
            logger.info(f"Ensuring historical prices for {len(tickers)} tickers")
            HistoricalPriceService.ensure_prices_for_period(
                list(tickers), start_date, end_date, db
            )

        # Build holdings snapshots at each transaction date
        # Key optimization: Only recalculate when holdings change
        holdings_by_date: Dict[date, Dict[str, Dict]] = {}
        current_holdings: Dict[str, Dict] = defaultdict(
            lambda: {'quantity': Decimal('0'), 'cost_czk': Decimal('0')}
        )

        # Track investment (for return calculation)
        cumulative_investment = Decimal('0')

        for txn in transactions:
            txn_date = txn.transaction_date

            # Normalize transaction to CZK
            try:
                txn_normalized = CurrencyNormalizer.normalize_transaction(txn, db)
                txn_amount_czk = _to_decimal(txn_normalized['amount_czk'])
            except Exception as e:
                logger.warning(f"Failed to normalize transaction {txn.id}: {e}")
                continue

            ticker = txn.ticker or ''

            if txn.transaction_type == 'BUY' and ticker:
                qty = _to_decimal(txn.quantity or 0)
                current_holdings[ticker]['quantity'] += qty
                current_holdings[ticker]['cost_czk'] += abs(txn_amount_czk)
                cumulative_investment += abs(txn_amount_czk)

            elif txn.transaction_type == 'SELL' and ticker:
                qty = _to_decimal(txn.quantity or 0)
                current_holdings[ticker]['quantity'] -= qty
                # Note: Don't reduce cost_czk here - FIFO is complex
                # Just track quantity for market value calculation

            elif txn.transaction_type == 'SPLIT' and ticker:
                # Handle stock splits
                split_ratio = _to_decimal(txn.quantity or 1)
                if split_ratio > 0:
                    current_holdings[ticker]['quantity'] *= split_ratio

            # Save snapshot at transaction dates
            if txn_date >= start_date:
                holdings_by_date[txn_date] = {
                    k: {'quantity': v['quantity'], 'cost_czk': v['cost_czk']}
                    for k, v in current_holdings.items()
                    if v['quantity'] > 0
                }

        # Pre-fetch stock currencies
        stock_currencies: Dict[str, str] = {}
        stocks = db.query(Stock).filter(Stock.ticker.in_(tickers)).all()
        for stock in stocks:
            stock_currencies[stock.ticker] = stock.currency or 'USD'

        # Generate performance data points
        performance_data = []
        current_date = start_date
        last_holdings_snapshot = {}
        last_investment = Decimal('0')

        # Track which transaction date's holdings to use
        sorted_txn_dates = sorted(holdings_by_date.keys())
        txn_date_idx = 0

        while current_date <= end_date:
            # Update holdings snapshot if we passed a transaction date
            while (txn_date_idx < len(sorted_txn_dates) and
                   sorted_txn_dates[txn_date_idx] <= current_date):
                last_holdings_snapshot = holdings_by_date[sorted_txn_dates[txn_date_idx]]
                txn_date_idx += 1

            # Calculate portfolio value for this date
            portfolio_value_czk = Decimal('0')
            conversion_issues = []

            for ticker, data in last_holdings_snapshot.items():
                quantity = data['quantity']
                if quantity <= 0:
                    continue

                # Get historical price
                historical_price = HistoricalPriceService.get_price_for_date(
                    ticker, current_date, db
                )

                if historical_price:
                    stock_currency = stock_currencies.get(ticker, 'USD')

                    # Convert to CZK
                    price_czk = CurrencyNormalizer.to_base_currency(
                        historical_price,
                        stock_currency,
                        current_date,
                        db
                    )

                    if price_czk:
                        portfolio_value_czk += quantity * _to_decimal(price_czk)
                    else:
                        conversion_issues.append(
                            f"No CZK rate for {stock_currency} on {current_date}"
                        )
                else:
                    # Use cost basis as fallback for missing prices
                    portfolio_value_czk += data['cost_czk']

            if conversion_issues:
                logger.debug(f"Conversion issues on {current_date}: {conversion_issues[:3]}")

            # Calculate returns
            portfolio_value = _to_float(portfolio_value_czk)

            # Use cumulative investment for return calculation
            investment = _to_float(cumulative_investment) if cumulative_investment > 0 else 1
            total_return = portfolio_value - investment
            total_return_percent = (total_return / investment * 100) if investment > 0 else 0

            # Add data point at sample intervals and end date
            days_since_start = (current_date - start_date).days
            if (days_since_start % sample_interval == 0 or current_date == end_date):
                # Only include if we have meaningful data
                if portfolio_value > 0 or current_date == end_date:
                    performance_data.append(PerformanceDataPoint(
                        date=current_date,
                        portfolio_value=round(portfolio_value, 2),
                        total_return=round(total_return, 2),
                        total_return_percent=round(total_return_percent, 4)
                    ))

            current_date += timedelta(days=1)

        return performance_data

    @staticmethod
    def get_diversification_metrics(
        db: Session,
        holdings: Optional[List[Holding]] = None
    ) -> DiversificationMetrics:
        """
        Calculate diversification metrics.

        Args:
            db: Database session
            holdings: Pre-calculated holdings (optional, avoids re-computation)

        Returns:
            DiversificationMetrics with concentration and sector data
        """
        if holdings is None:
            holdings = AnalyticsService._get_cached_holdings(db)

        if not holdings:
            return DiversificationMetrics(
                number_of_holdings=0,
                largest_position_percent=0.0,
                top_5_concentration=0.0,
                herfindahl_index=0.0,
                number_of_sectors=0,
                number_of_industries=0
            )

        # Get holding values (filter out zero/negative values)
        holding_values = [h.market_value for h in holdings if h.market_value > 0]

        if not holding_values:
            return DiversificationMetrics(
                number_of_holdings=0,
                largest_position_percent=0.0,
                top_5_concentration=0.0,
                herfindahl_index=0.0,
                number_of_sectors=0,
                number_of_industries=0
            )

        # Calculate concentration metrics
        concentration = FinancialCalculations.calculate_portfolio_concentration(holding_values)

        # Count unique sectors and industries
        sectors = set(h.sector for h in holdings if h.sector and h.market_value > 0)
        industries = set(h.industry for h in holdings if h.industry and h.market_value > 0)

        return DiversificationMetrics(
            number_of_holdings=len(holding_values),
            largest_position_percent=round(concentration['largest_position_percent'], 2),
            top_5_concentration=round(concentration['top_5_concentration'], 2),
            herfindahl_index=round(concentration['herfindahl_index'], 4),
            number_of_sectors=len(sectors),
            number_of_industries=len(industries)
        )

    @staticmethod
    def get_volatility_metrics(
        db: Session,
        performance_data: Optional[List[PerformanceDataPoint]] = None
    ) -> VolatilityMetrics:
        """
        Calculate portfolio volatility metrics with frequency detection.

        Args:
            db: Database session
            performance_data: Pre-calculated performance history (optional)

        Returns:
            VolatilityMetrics with volatility and Sharpe ratio
        """
        # Get performance history if not provided
        if performance_data is None:
            performance_data = AnalyticsService.get_performance_history(db, days=365)

        if len(performance_data) < 2:
            return VolatilityMetrics(
                daily_volatility=0.0,
                annualized_volatility=0.0,
                sharpe_ratio=None,
                data_frequency='unknown',
                data_quality='insufficient',
                warnings=['Insufficient data for volatility calculation (need at least 2 data points)']
            )

        # Extract values and dates
        values = [p.portfolio_value for p in performance_data]
        dates = [p.date for p in performance_data]

        # Filter out zero values that would skew volatility
        valid_data = [(d, v) for d, v in zip(dates, values) if v > 0]

        if len(valid_data) < 2:
            return VolatilityMetrics(
                daily_volatility=0.0,
                annualized_volatility=0.0,
                sharpe_ratio=None,
                data_frequency='unknown',
                data_quality='insufficient',
                warnings=['Insufficient non-zero data points for volatility calculation']
            )

        valid_dates, valid_values = zip(*valid_data)
        valid_dates = list(valid_dates)
        valid_values = list(valid_values)

        # Calculate volatility with frequency detection
        volatility = FinancialCalculations.calculate_volatility(valid_values, valid_dates)

        # Calculate returns for Sharpe ratio
        returns = []
        for i in range(1, len(valid_values)):
            if valid_values[i - 1] > 0:
                ret = (valid_values[i] - valid_values[i - 1]) / valid_values[i - 1]
                returns.append(ret)

        # Calculate Sharpe ratio
        sharpe_info = None
        if len(returns) >= 2:
            sharpe_info = FinancialCalculations.calculate_sharpe_ratio(
                returns,
                dates=valid_dates
            )

        # Collect warnings
        warnings = []
        if volatility['data_quality'] == 'insufficient':
            warnings.append('Insufficient data for accurate volatility calculation')
        if volatility['annualized_volatility'] == 0 and len(valid_values) > 10:
            warnings.append('Portfolio volatility is zero - may indicate inactive holdings')
        if volatility['annualized_volatility'] > 1.0:
            warnings.append(
                f"Very high volatility detected: {volatility['annualized_volatility']*100:.1f}%"
            )

        return VolatilityMetrics(
            daily_volatility=round(volatility['daily_volatility'], 6),
            annualized_volatility=round(volatility['annualized_volatility'], 4),
            sharpe_ratio=round(sharpe_info['sharpe_ratio'], 4) if sharpe_info else None,
            data_frequency=volatility['frequency'],
            data_quality=volatility['data_quality'],
            warnings=warnings if warnings else None
        )

    @staticmethod
    def get_dividend_summary(db: Session) -> DividendSummary:
        """
        Calculate dividend-related metrics.
        All dividend amounts normalized to CZK.

        Args:
            db: Database session

        Returns:
            DividendSummary with totals, yield, and growth rate
        """
        # Get all dividend transactions
        dividend_txns = db.query(Transaction).filter(
            Transaction.transaction_type == 'DIVIDEND'
        ).all()

        # Normalize all dividends to CZK
        total_dividends_czk = Decimal('0')
        annual_dividends_czk = Decimal('0')
        previous_year_dividends_czk = Decimal('0')

        one_year_ago = date.today() - timedelta(days=365)
        two_years_ago = one_year_ago - timedelta(days=365)

        for txn in dividend_txns:
            try:
                normalized = CurrencyNormalizer.normalize_transaction(txn, db)
                amount_czk = _to_decimal(normalized['amount_czk'])
            except Exception as e:
                logger.warning(f"Failed to normalize dividend {txn.id}: {e}")
                # Fallback to total_amount
                amount_czk = _to_decimal(txn.total_amount)

            total_dividends_czk += amount_czk

            if txn.transaction_date >= one_year_ago:
                annual_dividends_czk += amount_czk
            elif txn.transaction_date >= two_years_ago:
                previous_year_dividends_czk += amount_czk

        # Get current portfolio value
        try:
            summary = PortfolioService.get_portfolio_summary(db)
            portfolio_value = summary.total_value
        except Exception as e:
            logger.error(f"Failed to get portfolio summary for dividend yield: {e}")
            portfolio_value = 0

        # Calculate dividend yield
        annual_income = _to_float(annual_dividends_czk)
        dividend_yield = FinancialCalculations.calculate_dividend_yield(
            annual_income,
            portfolio_value
        )

        # Calculate dividend growth rate
        dividend_growth_rate = None
        prev_year = _to_float(previous_year_dividends_czk)
        if prev_year > 0:
            dividend_growth_rate = ((annual_income - prev_year) / prev_year) * 100

        return DividendSummary(
            total_dividends=round(_to_float(total_dividends_czk), 2),
            annual_dividend_income=round(annual_income, 2),
            dividend_yield=round(dividend_yield, 4),
            dividend_growth_rate=round(dividend_growth_rate, 2) if dividend_growth_rate else None
        )

    @staticmethod
    def get_all_kpis(
        db: Session,
        target_currency: str = 'CZK',
        max_snapshot_age_hours: int = 24
    ) -> KPIResponseWithMetadata:
        """
        Get all KPIs from most recent snapshot (fast load).
        Falls back to live calculation if no snapshot exists or is too old.

        Args:
            db: Database session
            target_currency: Currency to display values in (USD, EUR, or CZK)
            max_snapshot_age_hours: Maximum age of snapshot before recalculating

        Returns:
            KPIResponseWithMetadata with all KPIs and metadata
        """
        # Try to load most recent snapshot
        latest_snapshot = db.query(PortfolioSnapshot)\
            .order_by(PortfolioSnapshot.calculated_at.desc())\
            .first()

        # Check if snapshot is fresh enough
        if latest_snapshot:
            snapshot_age = datetime.utcnow() - latest_snapshot.calculated_at
            if snapshot_age.total_seconds() > max_snapshot_age_hours * 3600:
                logger.info(
                    f"Snapshot is {snapshot_age.total_seconds() / 3600:.1f}h old, "
                    f"recalculating (max: {max_snapshot_age_hours}h)"
                )
                latest_snapshot = None

        if latest_snapshot:
            return AnalyticsService._convert_snapshot_to_response(
                latest_snapshot, target_currency, db
            )
        else:
            # No valid snapshot - calculate and save
            logger.info("No valid KPI snapshot found, calculating fresh KPIs")
            result = AnalyticsService.recalculate_and_save_kpis(db)

            # Convert to target currency if needed
            if target_currency != 'CZK':
                return AnalyticsService.get_all_kpis(db, target_currency)

            return result

    @staticmethod
    def _convert_snapshot_to_response(
        snapshot: PortfolioSnapshot,
        target_currency: str,
        db: Session
    ) -> KPIResponseWithMetadata:
        """
        Convert a snapshot to KPIResponseWithMetadata with currency conversion.

        Args:
            snapshot: PortfolioSnapshot from database
            target_currency: Target display currency
            db: Database session

        Returns:
            KPIResponseWithMetadata
        """
        conversion_rate = 1.0
        conversion_warnings = []

        if target_currency != 'CZK':
            # Get exchange rate
            rate_result = ExchangeRateService.get_exchange_rate_intelligent(
                'CZK', target_currency, date.today(), db
            )

            if rate_result:
                conversion_rate = rate_result['rate']
                if rate_result.get('needs_manual_review'):
                    conversion_warnings.append(
                        f"Exchange rate for CZK/{target_currency} may need review"
                    )
            else:
                # Try fallback to last known rate
                last_rate = ExchangeRateService.get_last_known_rate(
                    'CZK', target_currency, date.today(), db
                )

                if last_rate:
                    rate_date, conversion_rate = last_rate
                    staleness = (date.today() - rate_date).days
                    conversion_warnings.append(
                        f"Using exchange rate from {rate_date} ({staleness} days old)"
                    )
                else:
                    raise ValueError(
                        f"Cannot convert to {target_currency}: no exchange rate available"
                    )

        def convert(amount: float) -> float:
            if amount is None:
                return 0.0
            return round(amount * conversion_rate, 2)

        # Build portfolio summary
        portfolio_summary = PortfolioSummary(
            total_value=convert(snapshot.total_value),
            total_cost_basis=convert(snapshot.cost_basis),
            total_unrealized_gain=convert(snapshot.unrealized_gain),
            total_unrealized_gain_percent=snapshot.unrealized_gain_percent or 0.0,
            total_realized_gain=convert(snapshot.realized_gain),
            cash_balance=convert(snapshot.cash_balance),
            number_of_holdings=snapshot.number_of_holdings or 0,
            currency=target_currency,
            conversion_warnings=conversion_warnings if conversion_warnings else None
        )

        # Diversification (no conversion needed - percentages)
        diversification = DiversificationMetrics(
            number_of_holdings=snapshot.number_of_holdings or 0,
            largest_position_percent=snapshot.largest_position_percent or 0.0,
            top_5_concentration=snapshot.top_5_concentration or 0.0,
            herfindahl_index=snapshot.herfindahl_index or 0.0,
            number_of_sectors=snapshot.number_of_sectors or 0,
            number_of_industries=snapshot.number_of_industries or 0
        )

        # Volatility (no conversion needed - percentages/ratios)
        volatility = VolatilityMetrics(
            daily_volatility=snapshot.daily_volatility or 0.0,
            annualized_volatility=snapshot.annualized_volatility or 0.0,
            sharpe_ratio=snapshot.sharpe_ratio,
            data_frequency=snapshot.data_frequency,
            data_quality=snapshot.data_quality
        )

        # Dividends (convert amounts)
        dividends = DividendSummary(
            total_dividends=convert(snapshot.total_dividends),
            annual_dividend_income=convert(snapshot.annual_dividend_income),
            dividend_yield=snapshot.dividend_yield or 0.0,
            dividend_growth_rate=snapshot.dividend_growth_rate
        )

        # Aggregate warnings
        all_warnings = conversion_warnings.copy()
        if snapshot.warnings:
            try:
                all_warnings.extend(json.loads(snapshot.warnings))
            except json.JSONDecodeError:
                pass

        # Parse errors
        all_errors = None
        if snapshot.errors:
            try:
                all_errors = json.loads(snapshot.errors)
            except json.JSONDecodeError:
                pass

        return KPIResponseWithMetadata(
            portfolio_summary=portfolio_summary,
            diversification=diversification,
            volatility=volatility,
            dividends=dividends,
            warnings=all_warnings if all_warnings else None,
            errors=all_errors,
            metadata=SnapshotMetadata(
                calculated_at=snapshot.calculated_at,
                calculation_duration_ms=snapshot.calculation_duration_ms
            )
        )

    @staticmethod
    def recalculate_and_save_kpis(
        db: Session,
        use_cached_prices: bool = True
    ) -> KPIResponseWithMetadata:
        """
        Recalculate all KPIs and save snapshot to database.

        Args:
            db: Database session
            use_cached_prices: If True, uses cached prices from DB

        Returns:
            KPIResponseWithMetadata with fresh calculations
        """
        import time

        start_time = time.time()
        all_warnings: List[str] = []
        all_errors: List[str] = []

        # Clear cache to ensure fresh calculations
        AnalyticsService.clear_cache()

        # Calculate portfolio summary first (used by other calculations)
        try:
            portfolio_summary = PortfolioService.get_portfolio_summary(db)
            if portfolio_summary.conversion_warnings:
                all_warnings.extend(portfolio_summary.conversion_warnings)
        except Exception as e:
            logger.error(f"Portfolio summary calculation failed: {e}")
            all_errors.append(f"Portfolio summary failed: {str(e)}")
            portfolio_summary = PortfolioSummary(
                total_value=0.0,
                total_cost_basis=0.0,
                total_unrealized_gain=0.0,
                total_unrealized_gain_percent=0.0,
                total_realized_gain=0.0,
                cash_balance=0.0,
                number_of_holdings=0
            )

        # Calculate diversification metrics
        try:
            diversification = AnalyticsService.get_diversification_metrics(db)
        except Exception as e:
            logger.error(f"Diversification calculation failed: {e}")
            all_errors.append(f"Diversification calculation failed: {str(e)}")
            diversification = DiversificationMetrics(
                number_of_holdings=0,
                largest_position_percent=0.0,
                top_5_concentration=0.0,
                herfindahl_index=0.0,
                number_of_sectors=0,
                number_of_industries=0
            )

        # Calculate volatility metrics
        try:
            volatility = AnalyticsService.get_volatility_metrics(db)
            if volatility.warnings:
                all_warnings.extend(volatility.warnings)
        except Exception as e:
            logger.error(f"Volatility calculation failed: {e}")
            all_errors.append(f"Volatility calculation failed: {str(e)}")
            volatility = VolatilityMetrics(
                daily_volatility=0.0,
                annualized_volatility=0.0
            )

        # Calculate dividend summary
        try:
            dividends = AnalyticsService.get_dividend_summary(db)
        except Exception as e:
            logger.error(f"Dividend calculation failed: {e}")
            all_errors.append(f"Dividend calculation failed: {str(e)}")
            dividends = DividendSummary(
                total_dividends=0.0,
                annual_dividend_income=0.0,
                dividend_yield=0.0
            )

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)

        # Save snapshot to database
        snapshot = PortfolioSnapshot(
            calculated_at=datetime.utcnow(),
            total_value=portfolio_summary.total_value,
            cost_basis=portfolio_summary.total_cost_basis,
            unrealized_gain=portfolio_summary.total_unrealized_gain,
            unrealized_gain_percent=portfolio_summary.total_unrealized_gain_percent,
            realized_gain=portfolio_summary.total_realized_gain,
            cash_balance=portfolio_summary.cash_balance,
            number_of_holdings=diversification.number_of_holdings,
            largest_position_percent=diversification.largest_position_percent,
            top_5_concentration=diversification.top_5_concentration,
            herfindahl_index=diversification.herfindahl_index,
            number_of_sectors=diversification.number_of_sectors,
            number_of_industries=diversification.number_of_industries,
            daily_volatility=volatility.daily_volatility,
            annualized_volatility=volatility.annualized_volatility,
            sharpe_ratio=volatility.sharpe_ratio,
            data_frequency=volatility.data_frequency,
            data_quality=volatility.data_quality,
            total_dividends=dividends.total_dividends,
            annual_dividend_income=dividends.annual_dividend_income,
            dividend_yield=dividends.dividend_yield,
            dividend_growth_rate=dividends.dividend_growth_rate,
            warnings=json.dumps(all_warnings) if all_warnings else None,
            errors=json.dumps(all_errors) if all_errors else None,
            calculation_duration_ms=duration_ms
        )

        try:
            db.add(snapshot)
            db.commit()
            db.refresh(snapshot)
            logger.info(f"KPI snapshot saved (ID: {snapshot.id}, duration: {duration_ms}ms)")
        except Exception as e:
            logger.error(f"Failed to save KPI snapshot: {e}")
            db.rollback()
            # Continue without saving - return calculated values

        return KPIResponseWithMetadata(
            portfolio_summary=portfolio_summary,
            diversification=diversification,
            volatility=volatility,
            dividends=dividends,
            warnings=all_warnings if all_warnings else None,
            errors=all_errors if all_errors else None,
            metadata=SnapshotMetadata(
                calculated_at=snapshot.calculated_at if snapshot.id else datetime.utcnow(),
                calculation_duration_ms=duration_ms
            )
        )

    @staticmethod
    def get_snapshot_history(
        db: Session,
        limit: int = 100,
        offset: int = 0
    ) -> List[SnapshotHistoryItem]:
        """
        Get historical KPI snapshots for trend visualization.

        Args:
            db: Database session
            limit: Maximum number of snapshots to return (default 100)
            offset: Number of snapshots to skip (for pagination)

        Returns:
            List of SnapshotHistoryItem sorted by date descending
        """
        snapshots = db.query(PortfolioSnapshot)\
            .order_by(PortfolioSnapshot.calculated_at.desc())\
            .offset(offset)\
            .limit(limit)\
            .all()

        return [
            SnapshotHistoryItem(
                id=s.id,
                calculated_at=s.calculated_at,
                total_value=s.total_value or 0.0,
                unrealized_gain=s.unrealized_gain or 0.0,
                unrealized_gain_percent=s.unrealized_gain_percent or 0.0,
                daily_volatility=s.daily_volatility,
                annualized_volatility=s.annualized_volatility,
                sharpe_ratio=s.sharpe_ratio,
                dividend_yield=s.dividend_yield or 0.0
            )
            for s in snapshots
        ]

    @staticmethod
    def delete_old_snapshots(db: Session, keep_days: int = 90) -> int:
        """
        Delete snapshots older than specified days.

        Args:
            db: Database session
            keep_days: Number of days of snapshots to keep

        Returns:
            Number of deleted snapshots
        """
        cutoff_date = datetime.utcnow() - timedelta(days=keep_days)

        deleted = db.query(PortfolioSnapshot)\
            .filter(PortfolioSnapshot.calculated_at < cutoff_date)\
            .delete(synchronize_session=False)

        db.commit()
        logger.info(f"Deleted {deleted} old snapshots (older than {keep_days} days)")

        return deleted
