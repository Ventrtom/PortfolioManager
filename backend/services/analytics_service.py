from sqlalchemy.orm import Session
from models.database import Transaction
from models.schemas import (
    PerformanceDataPoint, DiversificationMetrics,
    VolatilityMetrics, DividendSummary, KPIResponse
)
from services.portfolio_service import PortfolioService
from services.market_data_service import MarketDataService
from utils.calculations import FinancialCalculations
from datetime import date, timedelta
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
        Calculate historical portfolio performance
        Returns time series of portfolio value and returns
        """
        # Get all transactions
        transactions = db.query(Transaction).order_by(Transaction.transaction_date.asc()).all()

        if not transactions:
            return []

        # Find date range
        start_date = transactions[0].transaction_date
        end_date = date.today()

        # Calculate portfolio value for each day
        performance_data = []
        current_date = start_date
        initial_investment = 0

        while current_date <= end_date:
            # Calculate holdings as of this date
            holdings_by_ticker = defaultdict(lambda: {'quantity': 0, 'cost': 0})

            for txn in transactions:
                if txn.transaction_date > current_date:
                    break

                if txn.transaction_type == 'BUY':
                    holdings_by_ticker[txn.ticker]['quantity'] += txn.quantity
                    holdings_by_ticker[txn.ticker]['cost'] += txn.quantity * txn.price
                    initial_investment += txn.quantity * txn.price
                elif txn.transaction_type == 'SELL':
                    holdings_by_ticker[txn.ticker]['quantity'] -= txn.quantity

            # Calculate portfolio value for this date
            portfolio_value = 0
            for ticker, data in holdings_by_ticker.items():
                if data['quantity'] > 0:
                    # Get historical price for this date (simplified - use current price)
                    price = MarketDataService.get_current_price(ticker, db)
                    if price:
                        portfolio_value += data['quantity'] * price

            # Calculate returns
            total_return = portfolio_value - initial_investment
            total_return_percent = (total_return / initial_investment * 100) if initial_investment > 0 else 0

            # Add data point (sample every 7 days to reduce data points)
            if (current_date - start_date).days % 7 == 0 or current_date == end_date:
                performance_data.append(PerformanceDataPoint(
                    date=current_date,
                    portfolio_value=portfolio_value,
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
        Calculate portfolio volatility metrics
        """
        # Get performance history
        performance = AnalyticsService.get_performance_history(db, days=365)

        if len(performance) < 2:
            return VolatilityMetrics(
                daily_volatility=0,
                annualized_volatility=0,
                sharpe_ratio=None
            )

        # Extract portfolio values
        values = [p.portfolio_value for p in performance]

        # Calculate volatility
        volatility = FinancialCalculations.calculate_volatility(values)

        # Calculate returns for Sharpe ratio
        returns = []
        for i in range(1, len(values)):
            if values[i - 1] > 0:
                ret = (values[i] - values[i - 1]) / values[i - 1]
                returns.append(ret)

        sharpe_ratio = FinancialCalculations.calculate_sharpe_ratio(returns) if returns else None

        return VolatilityMetrics(
            daily_volatility=volatility['daily_volatility'],
            annualized_volatility=volatility['annualized_volatility'],
            sharpe_ratio=sharpe_ratio
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
    def get_all_kpis(db: Session) -> KPIResponse:
        """
        Get all KPIs in a single response
        """
        portfolio_summary = PortfolioService.get_portfolio_summary(db)
        diversification = AnalyticsService.get_diversification_metrics(db)
        volatility = AnalyticsService.get_volatility_metrics(db)
        dividends = AnalyticsService.get_dividend_summary(db)

        return KPIResponse(
            portfolio_summary=portfolio_summary,
            diversification=diversification,
            volatility=volatility,
            dividends=dividends
        )
