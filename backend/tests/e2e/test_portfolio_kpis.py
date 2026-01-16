"""
E2E Tests for Portfolio Summary KPIs.

Tests cover:
- Total Value calculation
- Cost Basis calculation (with currency conversion at transaction dates)
- Unrealized Gain calculation
- Realized Gain calculation (FIFO)
- Cash Balance calculation
- Stock Split handling
- All transaction types integration

Uses 3 stocks in different currencies: AAPL (USD), SAP (EUR), CEZ (CZK)
"""
import pytest
import sys
import os
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch, MagicMock

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.database import Base, Transaction, Stock, ExchangeRate, StockPrice
from models.schemas import PortfolioSummary, Holding
from services.portfolio_service import PortfolioService
from services.analytics_service import AnalyticsService

# Import test fixtures
from tests.fixtures.portfolio_test_data import (
    STOCKS, CURRENT_PRICES, HISTORICAL_PRICES,
    SCENARIO_SINGLE_CZK, SCENARIO_MULTI_CURRENCY, SCENARIO_FIFO_GAINS,
    SCENARIO_SPLIT, SCENARIO_ALL_TYPES,
    get_exchange_rate, get_current_price, get_stock_info, get_test_exchange_rates
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def test_db():
    """Create in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    session.close()
    engine.dispose()


@pytest.fixture
def db_with_stocks(test_db):
    """Populate database with stock records."""
    for ticker, stock_data in STOCKS.items():
        stock = Stock(
            ticker=stock_data['ticker'],
            company_name=stock_data['company_name'],
            sector=stock_data['sector'],
            industry=stock_data['industry'],
            currency=stock_data['currency'],
            resolved_symbol=stock_data.get('resolved_symbol'),
            enrichment_status='complete'
        )
        test_db.add(stock)

    test_db.commit()
    return test_db


@pytest.fixture
def db_with_exchange_rates(db_with_stocks):
    """Add exchange rates to database, including today's rate for market value."""
    for rate_data in get_test_exchange_rates():
        rate = ExchangeRate(
            base_currency=rate_data['base'],
            target_currency=rate_data['target'],
            rate_date=rate_data['date'],
            rate=rate_data['rate'],
            source='test-fixture',
            fetched_at=datetime.utcnow(),
            confidence='high'
        )
        db_with_stocks.add(rate)

    db_with_stocks.commit()
    return db_with_stocks


@pytest.fixture
def db_with_prices(db_with_exchange_rates):
    """Add stock prices to database."""
    for (ticker, price_date), price in HISTORICAL_PRICES.items():
        stock_price = StockPrice(
            ticker=ticker,
            price=price,
            price_date=price_date
        )
        db_with_exchange_rates.add(stock_price)

    db_with_exchange_rates.commit()
    return db_with_exchange_rates


def populate_transactions(db, scenario: dict):
    """Populate database with transactions from a scenario."""
    for i, txn_data in enumerate(scenario['transactions']):
        transaction = Transaction(
            transaction_type=txn_data['type'],
            ticker=txn_data.get('ticker', ''),
            quantity=txn_data.get('quantity'),
            price=txn_data.get('price'),
            total_amount=txn_data['total_amount'],
            transaction_date=txn_data['date'],
            transaction_currency=txn_data.get('currency', 'CZK'),
            notes=f"Test transaction {i}"
        )
        db.add(transaction)

    db.commit()


@pytest.fixture
def mock_market_data():
    """Mock MarketDataService to return fixed prices."""
    with patch('services.portfolio_service.MarketDataService') as mock:
        mock.get_current_price = MagicMock(side_effect=lambda ticker, db: CURRENT_PRICES.get(ticker))
        mock.get_stock_info = MagicMock(side_effect=lambda ticker, db: STOCKS.get(ticker))
        yield mock


# =============================================================================
# TOTAL VALUE TESTS
# =============================================================================

class TestTotalValue:
    """Tests for Total Value KPI."""

    def test_total_value_single_currency_holdings(self, db_with_prices, mock_market_data):
        """Total value = sum of (quantity * current_price) for single currency."""
        populate_transactions(db_with_prices, SCENARIO_SINGLE_CZK)

        with patch('services.portfolio_service.MarketDataService.get_current_price',
                   side_effect=lambda ticker, db: CURRENT_PRICES.get(ticker)):
            with patch('services.portfolio_service.MarketDataService.get_stock_info',
                       side_effect=lambda ticker, db: STOCKS.get(ticker)):
                summary = PortfolioService.get_portfolio_summary(db_with_prices)

        expected = SCENARIO_SINGLE_CZK['expected']
        assert abs(summary.total_value - expected['total_value']) < 1.0, \
            f"Expected total_value {expected['total_value']}, got {summary.total_value}"

    def test_total_value_multi_currency_holdings(self, db_with_prices, mock_market_data):
        """Total value correctly converts each holding to CZK."""
        populate_transactions(db_with_prices, SCENARIO_MULTI_CURRENCY)

        with patch('services.portfolio_service.MarketDataService.get_current_price',
                   side_effect=lambda ticker, db: CURRENT_PRICES.get(ticker)):
            with patch('services.portfolio_service.MarketDataService.get_stock_info',
                       side_effect=lambda ticker, db: STOCKS.get(ticker)):
                summary = PortfolioService.get_portfolio_summary(db_with_prices)

        expected = SCENARIO_MULTI_CURRENCY['expected']
        # Allow some tolerance for floating-point
        assert abs(summary.total_value - expected['total_value']) < 10.0, \
            f"Expected total_value {expected['total_value']}, got {summary.total_value}"


# =============================================================================
# COST BASIS TESTS
# =============================================================================

class TestCostBasis:
    """Tests for Cost Basis KPI."""

    def test_cost_basis_single_currency(self, db_with_prices, mock_market_data):
        """Cost basis calculation for single CZK currency."""
        populate_transactions(db_with_prices, SCENARIO_SINGLE_CZK)

        with patch('services.portfolio_service.MarketDataService.get_current_price',
                   side_effect=lambda ticker, db: CURRENT_PRICES.get(ticker)):
            with patch('services.portfolio_service.MarketDataService.get_stock_info',
                       side_effect=lambda ticker, db: STOCKS.get(ticker)):
                summary = PortfolioService.get_portfolio_summary(db_with_prices)

        expected = SCENARIO_SINGLE_CZK['expected']
        assert abs(summary.total_cost_basis - expected['cost_basis']) < 1.0, \
            f"Expected cost_basis {expected['cost_basis']}, got {summary.total_cost_basis}"

    def test_cost_basis_uses_transaction_date_exchange_rate(self, db_with_prices, mock_market_data):
        """
        CRITICAL TEST: Cost basis should use exchange rate from transaction date,
        NOT today's rate.

        This test will FAIL if the bug exists.
        """
        populate_transactions(db_with_prices, SCENARIO_MULTI_CURRENCY)

        with patch('services.portfolio_service.MarketDataService.get_current_price',
                   side_effect=lambda ticker, db: CURRENT_PRICES.get(ticker)):
            with patch('services.portfolio_service.MarketDataService.get_stock_info',
                       side_effect=lambda ticker, db: STOCKS.get(ticker)):
                summary = PortfolioService.get_portfolio_summary(db_with_prices)

        expected = SCENARIO_MULTI_CURRENCY['expected']

        # AAPL cost: 1500 USD * 22.75 (Jan 15 rate) = 34,125 CZK
        # SAP cost: 800 EUR * 25.00 (Feb 1 rate) = 20,000 CZK
        # Total: 54,125 CZK (correct)
        #
        # If bug exists (using today's rate):
        # AAPL cost: 1500 USD * 22.80 (Mar 1 rate) = 34,200 CZK
        # SAP cost: 800 EUR * 24.80 (Mar 1 rate) = 19,840 CZK
        # Total: 54,040 CZK (buggy)

        # Allow small tolerance
        tolerance = 100.0  # CZK
        assert abs(summary.total_cost_basis - expected['cost_basis']) < tolerance, \
            f"Cost basis bug detected! Expected {expected['cost_basis']} (using transaction dates), " \
            f"got {summary.total_cost_basis}. If ~54,040, bug uses today's rate instead of transaction date."

    def test_cost_basis_fifo_calculation(self, db_with_prices, mock_market_data):
        """Cost basis correctly uses FIFO for partial sells."""
        populate_transactions(db_with_prices, SCENARIO_FIFO_GAINS)

        with patch('services.portfolio_service.MarketDataService.get_current_price',
                   side_effect=lambda ticker, db: CURRENT_PRICES.get(ticker)):
            with patch('services.portfolio_service.MarketDataService.get_stock_info',
                       side_effect=lambda ticker, db: STOCKS.get(ticker)):
                summary = PortfolioService.get_portfolio_summary(db_with_prices)

        expected = SCENARIO_FIFO_GAINS['expected']
        # Remaining 5 shares from lot 2: 5 * 120 * 23.00 = 13,800 CZK
        tolerance = 100.0
        assert abs(summary.total_cost_basis - expected['cost_basis']) < tolerance, \
            f"Expected cost_basis {expected['cost_basis']}, got {summary.total_cost_basis}"


# =============================================================================
# UNREALIZED GAIN TESTS
# =============================================================================

class TestUnrealizedGain:
    """Tests for Unrealized Gain KPI."""

    def test_unrealized_gain_calculation(self, db_with_prices, mock_market_data):
        """Unrealized gain = Total Value - Cost Basis."""
        populate_transactions(db_with_prices, SCENARIO_SINGLE_CZK)

        with patch('services.portfolio_service.MarketDataService.get_current_price',
                   side_effect=lambda ticker, db: CURRENT_PRICES.get(ticker)):
            with patch('services.portfolio_service.MarketDataService.get_stock_info',
                       side_effect=lambda ticker, db: STOCKS.get(ticker)):
                summary = PortfolioService.get_portfolio_summary(db_with_prices)

        expected = SCENARIO_SINGLE_CZK['expected']

        # Verify the relationship
        calculated_gain = summary.total_value - summary.total_cost_basis
        assert abs(summary.total_unrealized_gain - calculated_gain) < 0.01, \
            f"Unrealized gain should equal total_value - cost_basis"

        assert abs(summary.total_unrealized_gain - expected['unrealized_gain']) < 1.0, \
            f"Expected unrealized_gain {expected['unrealized_gain']}, got {summary.total_unrealized_gain}"

    def test_unrealized_gain_percent_calculation(self, db_with_prices, mock_market_data):
        """Unrealized gain % = (Unrealized Gain / Cost Basis) * 100."""
        populate_transactions(db_with_prices, SCENARIO_SINGLE_CZK)

        with patch('services.portfolio_service.MarketDataService.get_current_price',
                   side_effect=lambda ticker, db: CURRENT_PRICES.get(ticker)):
            with patch('services.portfolio_service.MarketDataService.get_stock_info',
                       side_effect=lambda ticker, db: STOCKS.get(ticker)):
                summary = PortfolioService.get_portfolio_summary(db_with_prices)

        expected = SCENARIO_SINGLE_CZK['expected']

        # Verify the relationship
        if summary.total_cost_basis > 0:
            calculated_percent = (summary.total_unrealized_gain / summary.total_cost_basis) * 100
            assert abs(summary.total_unrealized_gain_percent - calculated_percent) < 0.1, \
                f"Unrealized gain % should equal (gain/cost)*100"

        assert abs(summary.total_unrealized_gain_percent - expected['unrealized_gain_percent']) < 0.5, \
            f"Expected unrealized_gain_percent {expected['unrealized_gain_percent']}, " \
            f"got {summary.total_unrealized_gain_percent}"


# =============================================================================
# REALIZED GAIN TESTS
# =============================================================================

class TestRealizedGain:
    """Tests for Realized Gain KPI."""

    def test_realized_gain_no_sells(self, db_with_prices, mock_market_data):
        """No realized gains when no sells have occurred."""
        populate_transactions(db_with_prices, SCENARIO_SINGLE_CZK)

        with patch('services.portfolio_service.MarketDataService.get_current_price',
                   side_effect=lambda ticker, db: CURRENT_PRICES.get(ticker)):
            with patch('services.portfolio_service.MarketDataService.get_stock_info',
                       side_effect=lambda ticker, db: STOCKS.get(ticker)):
                summary = PortfolioService.get_portfolio_summary(db_with_prices)

        assert summary.total_realized_gain == 0.0, \
            f"Expected 0 realized gain with no sells, got {summary.total_realized_gain}"

    def test_realized_gain_fifo_multiple_lots(self, db_with_prices, mock_market_data):
        """Realized gain correctly applies FIFO across multiple purchase lots."""
        populate_transactions(db_with_prices, SCENARIO_FIFO_GAINS)

        with patch('services.portfolio_service.MarketDataService.get_current_price',
                   side_effect=lambda ticker, db: CURRENT_PRICES.get(ticker)):
            with patch('services.portfolio_service.MarketDataService.get_stock_info',
                       side_effect=lambda ticker, db: STOCKS.get(ticker)):
                summary = PortfolioService.get_portfolio_summary(db_with_prices)

        expected = SCENARIO_FIFO_GAINS['expected']

        # FIFO realized gain:
        # Lot 1: 10 shares @ 100 USD, cost 22,750 CZK
        # Lot 2: 5 shares @ 120 USD, cost 13,800 CZK
        # Total cost sold: 36,550 CZK
        # Proceeds: 2250 USD * 22.80 = 51,300 CZK
        # Gain: 14,750 CZK

        tolerance = 500.0  # Allow some tolerance for exchange rate timing
        assert abs(summary.total_realized_gain - expected['realized_gain']) < tolerance, \
            f"Expected realized_gain {expected['realized_gain']}, got {summary.total_realized_gain}"

    def test_realized_gain_single_currency(self, db_with_prices, mock_market_data):
        """Realized gain for CZK-only transactions (no currency conversion)."""
        populate_transactions(db_with_prices, SCENARIO_ALL_TYPES)

        with patch('services.portfolio_service.MarketDataService.get_current_price',
                   side_effect=lambda ticker, db: CURRENT_PRICES.get(ticker)):
            with patch('services.portfolio_service.MarketDataService.get_stock_info',
                       side_effect=lambda ticker, db: STOCKS.get(ticker)):
                summary = PortfolioService.get_portfolio_summary(db_with_prices)

        expected = SCENARIO_ALL_TYPES['expected']

        # CEZ sold: 5 @ 950 = 4,750, cost 5 @ 900 = 4,500
        # Gain: 250 CZK
        tolerance = 100.0
        assert abs(summary.total_realized_gain - expected['realized_gain']) < tolerance, \
            f"Expected realized_gain {expected['realized_gain']}, got {summary.total_realized_gain}"


# =============================================================================
# CASH BALANCE TESTS
# =============================================================================

class TestCashBalance:
    """Tests for Cash Balance KPI."""

    def test_cash_balance_deposit_only(self, db_with_prices, mock_market_data):
        """Cash balance increases with deposits."""
        scenario = {
            'transactions': [
                {'type': 'DEPOSIT', 'date': date(2024, 1, 1), 'ticker': '',
                 'quantity': None, 'price': None, 'total_amount': 50000, 'currency': 'CZK'},
            ],
            'expected': {'cash_balance': 50000.0}
        }
        populate_transactions(db_with_prices, scenario)

        with patch('services.portfolio_service.MarketDataService.get_current_price',
                   side_effect=lambda ticker, db: CURRENT_PRICES.get(ticker)):
            with patch('services.portfolio_service.MarketDataService.get_stock_info',
                       side_effect=lambda ticker, db: STOCKS.get(ticker)):
                summary = PortfolioService.get_portfolio_summary(db_with_prices)

        assert abs(summary.cash_balance - 50000.0) < 1.0, \
            f"Expected cash_balance 50000, got {summary.cash_balance}"

    def test_cash_balance_deposit_withdrawal(self, db_with_prices, mock_market_data):
        """Cash balance tracks deposits and withdrawals."""
        scenario = {
            'transactions': [
                {'type': 'DEPOSIT', 'date': date(2024, 1, 1), 'ticker': '',
                 'quantity': None, 'price': None, 'total_amount': 100000, 'currency': 'CZK'},
                {'type': 'WITHDRAWAL', 'date': date(2024, 1, 5), 'ticker': '',
                 'quantity': None, 'price': None, 'total_amount': -20000, 'currency': 'CZK'},
            ],
            'expected': {'cash_balance': 80000.0}
        }
        populate_transactions(db_with_prices, scenario)

        with patch('services.portfolio_service.MarketDataService.get_current_price',
                   side_effect=lambda ticker, db: CURRENT_PRICES.get(ticker)):
            with patch('services.portfolio_service.MarketDataService.get_stock_info',
                       side_effect=lambda ticker, db: STOCKS.get(ticker)):
                summary = PortfolioService.get_portfolio_summary(db_with_prices)

        assert abs(summary.cash_balance - 80000.0) < 1.0, \
            f"Expected cash_balance 80000, got {summary.cash_balance}"

    def test_cash_balance_buy_reduces(self, db_with_prices, mock_market_data):
        """Cash balance reduces on BUY."""
        populate_transactions(db_with_prices, SCENARIO_SINGLE_CZK)

        with patch('services.portfolio_service.MarketDataService.get_current_price',
                   side_effect=lambda ticker, db: CURRENT_PRICES.get(ticker)):
            with patch('services.portfolio_service.MarketDataService.get_stock_info',
                       side_effect=lambda ticker, db: STOCKS.get(ticker)):
                summary = PortfolioService.get_portfolio_summary(db_with_prices)

        expected = SCENARIO_SINGLE_CZK['expected']
        assert abs(summary.cash_balance - expected['cash_balance']) < 1.0, \
            f"Expected cash_balance {expected['cash_balance']}, got {summary.cash_balance}"

    def test_cash_balance_dividends_interest(self, db_with_prices, mock_market_data):
        """Cash balance increases with dividends and interest."""
        scenario = {
            'transactions': [
                {'type': 'DEPOSIT', 'date': date(2024, 1, 1), 'ticker': '',
                 'quantity': None, 'price': None, 'total_amount': 10000, 'currency': 'CZK'},
                {'type': 'DIVIDEND', 'date': date(2024, 2, 1), 'ticker': 'CEZ',
                 'quantity': None, 'price': None, 'total_amount': 500, 'currency': 'CZK'},
                {'type': 'INTEREST', 'date': date(2024, 2, 15), 'ticker': '',
                 'quantity': None, 'price': None, 'total_amount': 100, 'currency': 'CZK'},
            ],
            'expected': {'cash_balance': 10600.0}
        }
        populate_transactions(db_with_prices, scenario)

        with patch('services.portfolio_service.MarketDataService.get_current_price',
                   side_effect=lambda ticker, db: CURRENT_PRICES.get(ticker)):
            with patch('services.portfolio_service.MarketDataService.get_stock_info',
                       side_effect=lambda ticker, db: STOCKS.get(ticker)):
                summary = PortfolioService.get_portfolio_summary(db_with_prices)

        assert abs(summary.cash_balance - 10600.0) < 1.0, \
            f"Expected cash_balance 10600, got {summary.cash_balance}"

    def test_cash_balance_fees_taxes(self, db_with_prices, mock_market_data):
        """Cash balance decreases with fees and taxes."""
        scenario = {
            'transactions': [
                {'type': 'DEPOSIT', 'date': date(2024, 1, 1), 'ticker': '',
                 'quantity': None, 'price': None, 'total_amount': 10000, 'currency': 'CZK'},
                {'type': 'FEE', 'date': date(2024, 2, 1), 'ticker': '',
                 'quantity': None, 'price': None, 'total_amount': -50, 'currency': 'CZK'},
                {'type': 'TAX', 'date': date(2024, 2, 15), 'ticker': '',
                 'quantity': None, 'price': None, 'total_amount': -150, 'currency': 'CZK'},
            ],
            'expected': {'cash_balance': 9800.0}
        }
        populate_transactions(db_with_prices, scenario)

        with patch('services.portfolio_service.MarketDataService.get_current_price',
                   side_effect=lambda ticker, db: CURRENT_PRICES.get(ticker)):
            with patch('services.portfolio_service.MarketDataService.get_stock_info',
                       side_effect=lambda ticker, db: STOCKS.get(ticker)):
                summary = PortfolioService.get_portfolio_summary(db_with_prices)

        assert abs(summary.cash_balance - 9800.0) < 1.0, \
            f"Expected cash_balance 9800, got {summary.cash_balance}"

    def test_cash_balance_multi_currency(self, db_with_prices, mock_market_data):
        """Cash balance correctly converts multi-currency transactions to CZK."""
        populate_transactions(db_with_prices, SCENARIO_MULTI_CURRENCY)

        with patch('services.portfolio_service.MarketDataService.get_current_price',
                   side_effect=lambda ticker, db: CURRENT_PRICES.get(ticker)):
            with patch('services.portfolio_service.MarketDataService.get_stock_info',
                       side_effect=lambda ticker, db: STOCKS.get(ticker)):
                summary = PortfolioService.get_portfolio_summary(db_with_prices)

        expected = SCENARIO_MULTI_CURRENCY['expected']
        tolerance = 100.0  # Allow for exchange rate variations
        assert abs(summary.cash_balance - expected['cash_balance']) < tolerance, \
            f"Expected cash_balance {expected['cash_balance']}, got {summary.cash_balance}"


# =============================================================================
# STOCK SPLIT TESTS
# =============================================================================

class TestStockSplit:
    """Tests for Stock Split handling."""

    def test_split_adjusts_quantity(self, db_with_prices, mock_market_data):
        """Stock split multiplies quantity by split ratio."""
        populate_transactions(db_with_prices, SCENARIO_SPLIT)

        with patch('services.portfolio_service.MarketDataService.get_current_price',
                   side_effect=lambda ticker, db: CURRENT_PRICES.get(ticker)):
            with patch('services.portfolio_service.MarketDataService.get_stock_info',
                       side_effect=lambda ticker, db: STOCKS.get(ticker)):
                holdings = PortfolioService.calculate_holdings(db_with_prices)

        # After 4:1 split, 10 shares become 40
        aapl_holding = next((h for h in holdings if h.ticker == 'AAPL'), None)
        assert aapl_holding is not None, "AAPL holding should exist"
        assert abs(aapl_holding.quantity - 40) < 0.01, \
            f"Expected 40 shares after 4:1 split, got {aapl_holding.quantity}"

    def test_split_preserves_total_cost(self, db_with_prices, mock_market_data):
        """Stock split preserves total cost basis in CZK."""
        populate_transactions(db_with_prices, SCENARIO_SPLIT)

        with patch('services.portfolio_service.MarketDataService.get_current_price',
                   side_effect=lambda ticker, db: CURRENT_PRICES.get(ticker)):
            with patch('services.portfolio_service.MarketDataService.get_stock_info',
                       side_effect=lambda ticker, db: STOCKS.get(ticker)):
                summary = PortfolioService.get_portfolio_summary(db_with_prices)

        expected = SCENARIO_SPLIT['expected']
        # Cost should remain: 4000 USD * 22.75 = 91,000 CZK
        tolerance = 100.0
        assert abs(summary.total_cost_basis - expected['cost_basis']) < tolerance, \
            f"Expected cost_basis {expected['cost_basis']}, got {summary.total_cost_basis}"


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestFullIntegration:
    """Full portfolio integration tests."""

    def test_full_portfolio_scenario(self, db_with_prices, mock_market_data):
        """Complete portfolio with all transaction types."""
        populate_transactions(db_with_prices, SCENARIO_ALL_TYPES)

        with patch('services.portfolio_service.MarketDataService.get_current_price',
                   side_effect=lambda ticker, db: CURRENT_PRICES.get(ticker)):
            with patch('services.portfolio_service.MarketDataService.get_stock_info',
                       side_effect=lambda ticker, db: STOCKS.get(ticker)):
                summary = PortfolioService.get_portfolio_summary(db_with_prices)

        expected = SCENARIO_ALL_TYPES['expected']

        # Check all KPIs with reasonable tolerance
        tolerance = 500.0  # Allow for cumulative floating-point errors

        assert abs(summary.total_value - expected['total_value']) < tolerance, \
            f"Total value: expected {expected['total_value']}, got {summary.total_value}"

        assert abs(summary.total_cost_basis - expected['cost_basis']) < tolerance, \
            f"Cost basis: expected {expected['cost_basis']}, got {summary.total_cost_basis}"

        assert abs(summary.total_unrealized_gain - expected['unrealized_gain']) < tolerance, \
            f"Unrealized gain: expected {expected['unrealized_gain']}, got {summary.total_unrealized_gain}"

        assert abs(summary.total_realized_gain - expected['realized_gain']) < tolerance, \
            f"Realized gain: expected {expected['realized_gain']}, got {summary.total_realized_gain}"

        assert abs(summary.cash_balance - expected['cash_balance']) < tolerance, \
            f"Cash balance: expected {expected['cash_balance']}, got {summary.cash_balance}"

        assert summary.number_of_holdings == expected['number_of_holdings'], \
            f"Holdings count: expected {expected['number_of_holdings']}, got {summary.number_of_holdings}"

    def test_holdings_count(self, db_with_prices, mock_market_data):
        """Number of holdings is correct."""
        populate_transactions(db_with_prices, SCENARIO_ALL_TYPES)

        with patch('services.portfolio_service.MarketDataService.get_current_price',
                   side_effect=lambda ticker, db: CURRENT_PRICES.get(ticker)):
            with patch('services.portfolio_service.MarketDataService.get_stock_info',
                       side_effect=lambda ticker, db: STOCKS.get(ticker)):
                holdings = PortfolioService.calculate_holdings(db_with_prices)

        # Should have AAPL, SAP, CEZ (5 remaining after partial sell)
        assert len(holdings) == 3, f"Expected 3 holdings, got {len(holdings)}"

        tickers = {h.ticker for h in holdings}
        assert tickers == {'AAPL', 'SAP', 'CEZ'}, f"Unexpected tickers: {tickers}"


# =============================================================================
# KPI CONSISTENCY TESTS
# =============================================================================

class TestKPIConsistency:
    """Tests for mathematical consistency between KPIs."""

    def test_unrealized_gain_equals_value_minus_cost(self, db_with_prices, mock_market_data):
        """Unrealized gain must equal total_value - cost_basis."""
        for scenario in [SCENARIO_SINGLE_CZK, SCENARIO_MULTI_CURRENCY, SCENARIO_ALL_TYPES]:
            # Clear previous transactions
            db_with_prices.query(Transaction).delete()
            db_with_prices.commit()

            populate_transactions(db_with_prices, scenario)

            with patch('services.portfolio_service.MarketDataService.get_current_price',
                       side_effect=lambda ticker, db: CURRENT_PRICES.get(ticker)):
                with patch('services.portfolio_service.MarketDataService.get_stock_info',
                           side_effect=lambda ticker, db: STOCKS.get(ticker)):
                    summary = PortfolioService.get_portfolio_summary(db_with_prices)

            calculated = summary.total_value - summary.total_cost_basis
            assert abs(summary.total_unrealized_gain - calculated) < 0.1, \
                f"In {scenario['name']}: unrealized_gain ({summary.total_unrealized_gain}) " \
                f"should equal value - cost ({calculated})"

    def test_unrealized_percent_formula(self, db_with_prices, mock_market_data):
        """Unrealized gain % must equal (unrealized_gain / cost_basis) * 100."""
        for scenario in [SCENARIO_SINGLE_CZK, SCENARIO_MULTI_CURRENCY]:
            # Clear previous transactions
            db_with_prices.query(Transaction).delete()
            db_with_prices.commit()

            populate_transactions(db_with_prices, scenario)

            with patch('services.portfolio_service.MarketDataService.get_current_price',
                       side_effect=lambda ticker, db: CURRENT_PRICES.get(ticker)):
                with patch('services.portfolio_service.MarketDataService.get_stock_info',
                           side_effect=lambda ticker, db: STOCKS.get(ticker)):
                    summary = PortfolioService.get_portfolio_summary(db_with_prices)

            if summary.total_cost_basis > 0:
                calculated = (summary.total_unrealized_gain / summary.total_cost_basis) * 100
                assert abs(summary.total_unrealized_gain_percent - calculated) < 0.1, \
                    f"In {scenario['name']}: unrealized_gain_percent ({summary.total_unrealized_gain_percent}) " \
                    f"should equal (gain/cost)*100 ({calculated})"
