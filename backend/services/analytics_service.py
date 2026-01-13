from sqlalchemy.orm import Session
from models.database import Transaction, Stock
from models.schemas import (
    PerformanceDataPoint, DiversificationMetrics,
    VolatilityMetrics, DividendSummary, KPIResponse,
    PortfolioSummary, KPIResponseWithMetadata, SnapshotMetadata, SnapshotHistoryItem
)
from services.portfolio_service import PortfolioService
from services.market_data_service import MarketDataService
from services.historical_price_service import HistoricalPriceService
from services.exchange_rate_service import CurrencyNormalizer
from utils.calculations import FinancialCalculations
from datetime import date, datetime, timedelta
from typing import List
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for calculating portfolio analytics and KPIs"""

    @staticmethod
    def get_performance_history(db: Session, days: int = 365) -> List[PerformanceDataPoint]:
        """
        Calculate historical portfolio performance with actual historical prices.
        All values normalized to CZK base currency.
        """
        # Get all transactions
        transactions = db.query(Transaction).order_by(Transaction.transaction_date.asc()).all()

        if not transactions:
            return []

        # Find date range
        start_date = transactions[0].transaction_date
        end_date = date.today()

        # Get unique tickers for historical price population
        tickers = set(txn.ticker for txn in transactions if txn.transaction_type in ['BUY', 'SELL'])

        # CRITICAL FIX: Pre-populate historical prices on-demand
        logger.info(f"Ensuring historical prices for {len(tickers)} tickers from {start_date} to {end_date}")
        HistoricalPriceService.ensure_prices_for_period(list(tickers), start_date, end_date, db)

        # Calculate portfolio value for each day
        performance_data = []
        current_date = start_date
        initial_investment_czk = 0  # Track in CZK

        while current_date <= end_date:
            # Calculate holdings as of this date
            holdings_by_ticker = defaultdict(lambda: {'quantity': 0, 'cost_czk': 0})

            # Recalculate initial investment for this date
            initial_investment_czk = 0

            for txn in transactions:
                if txn.transaction_date > current_date:
                    break

                # Normalize transaction to CZK
                txn_normalized = CurrencyNormalizer.normalize_transaction(txn, db)
                txn_amount_czk = txn_normalized['amount_czk']

                if txn.transaction_type == 'BUY':
                    holdings_by_ticker[txn.ticker]['quantity'] += txn.quantity
                    holdings_by_ticker[txn.ticker]['cost_czk'] += txn_amount_czk
                    initial_investment_czk += txn_amount_czk
                elif txn.transaction_type == 'SELL':
                    holdings_by_ticker[txn.ticker]['quantity'] -= txn.quantity

            # Calculate portfolio value using HISTORICAL prices
            portfolio_value_czk = 0
            for ticker, data in holdings_by_ticker.items():
                if data['quantity'] > 0:
                    # CRITICAL FIX: Use historical price for this date
                    historical_price = HistoricalPriceService.get_price_for_date(ticker, current_date, db)

                    if historical_price:
                        # Get stock currency and normalize to CZK
                        stock = db.query(Stock).filter(Stock.ticker == ticker).first()
                        stock_currency = stock.currency if stock else 'USD'

                        # Convert historical price to CZK
                        price_czk = CurrencyNormalizer.to_base_currency(
                            historical_price,
                            stock_currency,
                            current_date,
                            db
                        )

                        if price_czk:
                            portfolio_value_czk += data['quantity'] * price_czk

            # Calculate returns
            total_return = portfolio_value_czk - initial_investment_czk
            total_return_percent = (total_return / initial_investment_czk * 100) if initial_investment_czk > 0 else 0

            # Add data point - use 3-day sampling for better volatility calculation
            # (balance between performance and data quality)
            if (current_date - start_date).days % 3 == 0 or current_date == end_date:
                # Only add data points where we have holdings (avoid zero-value periods that skew volatility)
                # However, always include the end date for completeness
                if portfolio_value_czk > 0 or current_date == end_date:
                    performance_data.append(PerformanceDataPoint(
                        date=current_date,
                        portfolio_value=portfolio_value_czk,
                        total_return=total_return,
                        total_return_percent=total_return_percent
                    ))

            current_date += timedelta(days=1)

        return performance_data

    @staticmethod
    def get_diversification_metrics(db: Session) -> DiversificationMetrics:
        """
        Calculate diversification metrics
        """
        holdings = PortfolioService.calculate_holdings(db)

        if not holdings:
            return DiversificationMetrics(
                number_of_holdings=0,
                largest_position_percent=0,
                top_5_concentration=0,
                herfindahl_index=0,
                number_of_sectors=0,
                number_of_industries=0
            )

        # Get holding values
        holding_values = [h.market_value for h in holdings]

        # Calculate concentration metrics
        concentration = FinancialCalculations.calculate_portfolio_concentration(holding_values)

        # Count unique sectors and industries
        sectors = set(h.sector for h in holdings if h.sector)
        industries = set(h.industry for h in holdings if h.industry)

        return DiversificationMetrics(
            number_of_holdings=len(holdings),
            largest_position_percent=concentration['largest_position_percent'],
            top_5_concentration=concentration['top_5_concentration'],
            herfindahl_index=concentration['herfindahl_index'],
            number_of_sectors=len(sectors),
            number_of_industries=len(industries)
        )

    @staticmethod
    def get_volatility_metrics(db: Session) -> VolatilityMetrics:
        """
        Calculate portfolio volatility metrics with frequency detection
        """
        # Get performance history
        performance = AnalyticsService.get_performance_history(db, days=365)

        if len(performance) < 2:
            return VolatilityMetrics(
                daily_volatility=0,
                annualized_volatility=0,
                sharpe_ratio=None,
                data_frequency='unknown',
                data_quality='insufficient',
                warnings=['Insufficient data for volatility calculation']
            )

        # Extract values and dates
        values = [p.portfolio_value for p in performance]
        dates = [p.date for p in performance]

        # CRITICAL FIX: Pass dates for frequency detection
        volatility = FinancialCalculations.calculate_volatility(values, dates)

        # Calculate returns
        returns = []
        for i in range(1, len(values)):
            if values[i - 1] > 0:
                ret = (values[i] - values[i - 1]) / values[i - 1]
                returns.append(ret)

        # CRITICAL FIX: Pass dates to Sharpe ratio (need n+1 dates for n returns)
        sharpe_info = FinancialCalculations.calculate_sharpe_ratio(returns, dates=dates) if returns else None

        # Collect warnings - only report truly problematic situations
        warnings = []
        if volatility['data_quality'] == 'insufficient':
            warnings.append(f"Insufficient data for volatility calculation (need at least 2 valid data points)")
        # Only warn about zero volatility if we have enough data and it's truly zero
        if volatility['annualized_volatility'] == 0 and len(values) > 10:
            warnings.append("Portfolio volatility is zero - value may be constant or holdings inactive")
        if volatility['annualized_volatility'] > 1.0:  # >100%
            warnings.append(f"Very high volatility detected: {volatility['annualized_volatility']*100:.1f}%")

        return VolatilityMetrics(
            daily_volatility=volatility['daily_volatility'],
            annualized_volatility=volatility['annualized_volatility'],
            sharpe_ratio=sharpe_info['sharpe_ratio'] if sharpe_info else None,
            data_frequency=volatility['frequency'],
            data_quality=volatility['data_quality'],
            warnings=warnings if warnings else None
        )

    @staticmethod
    def get_dividend_summary(db: Session) -> DividendSummary:
        """
        Calculate dividend-related metrics
        """
        # Get all dividend transactions
        dividend_txns = db.query(Transaction).filter(
            Transaction.transaction_type == 'DIVIDEND'
        ).all()

        total_dividends = sum(t.total_amount for t in dividend_txns)

        # Calculate annual dividend income (last 12 months)
        one_year_ago = date.today() - timedelta(days=365)
        recent_dividends = [t for t in dividend_txns if t.transaction_date >= one_year_ago]
        annual_dividend_income = sum(t.total_amount for t in recent_dividends)

        # Get current portfolio value
        summary = PortfolioService.get_portfolio_summary(db)
        portfolio_value = summary.total_value

        # Calculate dividend yield
        dividend_yield = FinancialCalculations.calculate_dividend_yield(
            annual_dividend_income,
            portfolio_value
        )

        # Calculate dividend growth rate (simplified - compare last year to previous year)
        two_years_ago = one_year_ago - timedelta(days=365)
        previous_year_dividends = [
            t for t in dividend_txns
            if two_years_ago <= t.transaction_date < one_year_ago
        ]
        previous_year_total = sum(t.total_amount for t in previous_year_dividends)

        dividend_growth_rate = None
        if previous_year_total > 0:
            dividend_growth_rate = ((annual_dividend_income - previous_year_total) / previous_year_total) * 100

        return DividendSummary(
            total_dividends=total_dividends,
            annual_dividend_income=annual_dividend_income,
            dividend_yield=dividend_yield,
            dividend_growth_rate=dividend_growth_rate
        )

    @staticmethod
    def get_all_kpis(db: Session, target_currency: str = 'CZK') -> KPIResponseWithMetadata:
        """
        Get all KPIs from most recent snapshot (fast load)
        Falls back to live calculation if no snapshot exists

        Args:
            db: Database session
            target_currency: Currency to display values in (USD, EUR, or CZK)
        """
        from models.database import PortfolioSnapshot
        from services.exchange_rate_service import ExchangeRateService
        from datetime import date
        import json

        # Try to load most recent snapshot
        latest_snapshot = db.query(PortfolioSnapshot)\
            .order_by(PortfolioSnapshot.calculated_at.desc())\
            .first()

        if latest_snapshot:
            # Snapshot is always in CZK - convert if needed
            conversion_rate = 1.0
            conversion_warnings = []

            if target_currency != 'CZK':
                # Get latest exchange rate (use today's date)
                conversion_rate = ExchangeRateService.get_exchange_rate(
                    'CZK',
                    target_currency,
                    date.today(),
                    db
                )

                if conversion_rate is None:
                    # Fallback to last known rate
                    last_rate = ExchangeRateService.get_last_known_rate(
                        'CZK',
                        target_currency,
                        date.today(),
                        db
                    )

                    if last_rate:
                        rate_date, conversion_rate = last_rate
                        staleness = (date.today() - rate_date).days
                        conversion_warnings.append(
                            f"Using exchange rate from {rate_date} ({staleness} days old) for CZK/{target_currency}"
                        )
                    else:
                        # Can't convert - raise error
                        raise Exception(
                            f"Unable to fetch exchange rate for CZK/{target_currency}. "
                            f"KPIs are calculated in CZK. Please try again later or use CZK."
                        )

            # Helper function to convert amounts
            def convert(amount: float) -> float:
                return round(amount * conversion_rate, 2)

            # Convert portfolio summary
            portfolio_summary = PortfolioSummary(
                total_value=convert(latest_snapshot.total_value),
                total_cost_basis=convert(latest_snapshot.cost_basis),
                total_unrealized_gain=convert(latest_snapshot.unrealized_gain),
                total_unrealized_gain_percent=latest_snapshot.unrealized_gain_percent,  # % stays same
                total_realized_gain=convert(latest_snapshot.realized_gain),
                cash_balance=convert(latest_snapshot.cash_balance),
                number_of_holdings=latest_snapshot.number_of_holdings,
                currency=target_currency,  # Set display currency
                conversion_warnings=conversion_warnings if conversion_warnings else (
                    json.loads(latest_snapshot.warnings) if latest_snapshot.warnings else None
                )
            )

            # Diversification - no conversion needed (counts and percentages)
            diversification = DiversificationMetrics(
                number_of_holdings=latest_snapshot.number_of_holdings,
                largest_position_percent=latest_snapshot.largest_position_percent,
                top_5_concentration=latest_snapshot.top_5_concentration,
                herfindahl_index=latest_snapshot.herfindahl_index,
                number_of_sectors=latest_snapshot.number_of_sectors,
                number_of_industries=latest_snapshot.number_of_industries
            )

            # Volatility - no conversion needed (percentages and ratios)
            volatility = VolatilityMetrics(
                daily_volatility=latest_snapshot.daily_volatility or 0.0,
                annualized_volatility=latest_snapshot.annualized_volatility or 0.0,
                sharpe_ratio=latest_snapshot.sharpe_ratio,
                data_frequency=latest_snapshot.data_frequency,
                data_quality=latest_snapshot.data_quality
            )

            # Dividends - convert amounts
            dividends = DividendSummary(
                total_dividends=convert(latest_snapshot.total_dividends),
                annual_dividend_income=convert(latest_snapshot.annual_dividend_income),
                dividend_yield=latest_snapshot.dividend_yield,  # % stays same
                dividend_growth_rate=latest_snapshot.dividend_growth_rate  # % stays same
            )

            # Aggregate warnings
            all_warnings = conversion_warnings.copy() if conversion_warnings else []
            if latest_snapshot.warnings:
                all_warnings.extend(json.loads(latest_snapshot.warnings))

            return KPIResponseWithMetadata(
                portfolio_summary=portfolio_summary,
                diversification=diversification,
                volatility=volatility,
                dividends=dividends,
                warnings=all_warnings if all_warnings else None,
                errors=json.loads(latest_snapshot.errors) if latest_snapshot.errors else None,
                metadata=SnapshotMetadata(
                    calculated_at=latest_snapshot.calculated_at,
                    calculation_duration_ms=latest_snapshot.calculation_duration_ms
                )
            )
        else:
            # No snapshot exists - calculate and save initial snapshot
            logger.warning("No KPI snapshot found, calculating initial snapshot")
            result = AnalyticsService.recalculate_and_save_kpis(db)

            # If target currency is not CZK, need to convert the fresh result
            if target_currency != 'CZK':
                return AnalyticsService.get_all_kpis(db, target_currency)

            return result

    @staticmethod
    def recalculate_and_save_kpis(db: Session, use_cached_prices: bool = True) -> KPIResponseWithMetadata:
        """
        Recalculate all KPIs and save snapshot to database

        Args:
            db: Database session
            use_cached_prices: If True, uses cached prices from DB (default)
                              If False, fetches fresh prices from market data API
        """
        from models.database import PortfolioSnapshot
        import json
        import time

        start_time = time.time()
        all_warnings = []
        all_errors = []

        # Portfolio summary
        try:
            portfolio_summary = PortfolioService.get_portfolio_summary(db)
            if portfolio_summary.conversion_warnings:
                all_warnings.extend(portfolio_summary.conversion_warnings)
        except Exception as e:
            logger.error(f"Portfolio summary calculation failed: {e}")
            all_errors.append(f"Portfolio summary calculation failed: {str(e)}")
            # Use zero values as fallback
            portfolio_summary = PortfolioSummary(
                total_value=0.0, total_cost_basis=0.0, total_unrealized_gain=0.0,
                total_unrealized_gain_percent=0.0, total_realized_gain=0.0, cash_balance=0.0,
                number_of_holdings=0
            )

        # Diversification metrics
        try:
            diversification = AnalyticsService.get_diversification_metrics(db)
        except Exception as e:
            logger.error(f"Diversification calculation failed: {e}")
            all_errors.append(f"Diversification calculation failed: {str(e)}")
            diversification = DiversificationMetrics(
                number_of_holdings=0, largest_position_percent=0.0,
                top_5_concentration=0.0, herfindahl_index=0.0,
                number_of_sectors=0, number_of_industries=0
            )

        # Volatility metrics
        try:
            volatility = AnalyticsService.get_volatility_metrics(db)
            if volatility.warnings:
                all_warnings.extend(volatility.warnings)
        except Exception as e:
            logger.error(f"Volatility calculation failed: {e}")
            all_errors.append(f"Volatility calculation failed: {str(e)}")
            volatility = VolatilityMetrics(
                daily_volatility=0.0, annualized_volatility=0.0
            )

        # Dividend summary
        try:
            dividends = AnalyticsService.get_dividend_summary(db)
        except Exception as e:
            logger.error(f"Dividend calculation failed: {e}")
            all_errors.append(f"Dividend calculation failed: {str(e)}")
            dividends = DividendSummary(
                total_dividends=0.0, annual_dividend_income=0.0,
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

        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)

        logger.info(f"KPI snapshot saved (ID: {snapshot.id}, duration: {duration_ms}ms)")

        return KPIResponseWithMetadata(
            portfolio_summary=portfolio_summary,
            diversification=diversification,
            volatility=volatility,
            dividends=dividends,
            warnings=all_warnings if all_warnings else None,
            errors=all_errors if all_errors else None,
            metadata=SnapshotMetadata(
                calculated_at=snapshot.calculated_at,
                calculation_duration_ms=duration_ms
            )
        )

    @staticmethod
    def get_snapshot_history(db: Session, limit: int = 100) -> List[SnapshotHistoryItem]:
        """
        Get historical KPI snapshots for trend visualization

        Args:
            limit: Maximum number of snapshots to return (default 100)
        """
        from models.database import PortfolioSnapshot

        snapshots = db.query(PortfolioSnapshot)\
            .order_by(PortfolioSnapshot.calculated_at.desc())\
            .limit(limit)\
            .all()

        return [
            SnapshotHistoryItem(
                id=s.id,
                calculated_at=s.calculated_at,
                total_value=s.total_value,
                unrealized_gain=s.unrealized_gain,
                unrealized_gain_percent=s.unrealized_gain_percent,
                daily_volatility=s.daily_volatility,
                annualized_volatility=s.annualized_volatility,
                sharpe_ratio=s.sharpe_ratio,
                dividend_yield=s.dividend_yield
            )
            for s in snapshots
        ]
