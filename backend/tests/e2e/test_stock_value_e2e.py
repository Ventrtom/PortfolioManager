#!/usr/bin/env python3
"""
Stock Value KPI E2E Test

This standalone script tests the Stock Value KPI calculation by:
1. Creating test transactions via the API
2. Setting up mock stock prices and exchange rates
3. Calculating expected Stock Value step-by-step
4. Comparing with actual API response

Run: python test_stock_value_e2e.py
Requires: Backend server running on localhost:8000
"""

import sys
import os
import requests
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# Add backend to path for database access
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# =============================================================================
# CONFIGURATION
# =============================================================================

API_BASE_URL = "http://localhost:8000/api"
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./portfolio.db")

# Test data prefix to identify test records
TEST_PREFIX = "TEST_"

# ANSI color codes for console output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

# =============================================================================
# TEST DATA DEFINITIONS
# =============================================================================

# Test stocks with their currencies
TEST_STOCKS = {
    f"{TEST_PREFIX}AAPL": {"currency": "USD", "company_name": "Test Apple Inc"},
    f"{TEST_PREFIX}SAP": {"currency": "EUR", "company_name": "Test SAP SE"},
    f"{TEST_PREFIX}CEZ": {"currency": "CZK", "company_name": "Test CEZ Group"},
}

# Test transactions
TEST_TRANSACTIONS = [
    # Initial deposit to have cash for purchases
    {
        "transaction_type": "DEPOSIT",
        "ticker": "",
        "quantity": None,
        "price": None,
        "total_amount": 200000.00,  # 200k CZK
        "transaction_currency": "CZK",
        "transaction_date": "2024-01-01",
        "notes": "E2E Test - Initial deposit",
        "skip_cash_validation": True,
        "skip_fifo_validation": True,
        "skip_price_validation": True,
        "skip_exchange_rate_conversion": True,
    },
    # AAPL purchases (USD)
    {
        "transaction_type": "BUY",
        "ticker": f"{TEST_PREFIX}AAPL",
        "quantity": 10,
        "price": 150.00,
        "total_amount": -1500.00,  # Negative for BUY (money out)
        "transaction_currency": "USD",
        "transaction_date": "2024-01-15",
        "notes": "E2E Test - Buy AAPL lot 1",
        "skip_cash_validation": True,
        "skip_fifo_validation": True,
        "skip_price_validation": True,
    },
    {
        "transaction_type": "BUY",
        "ticker": f"{TEST_PREFIX}AAPL",
        "quantity": 5,
        "price": 160.00,
        "total_amount": -800.00,
        "transaction_currency": "USD",
        "transaction_date": "2024-02-01",
        "notes": "E2E Test - Buy AAPL lot 2",
        "skip_cash_validation": True,
        "skip_fifo_validation": True,
        "skip_price_validation": True,
    },
    {
        "transaction_type": "SELL",
        "ticker": f"{TEST_PREFIX}AAPL",
        "quantity": 5,
        "price": 175.00,
        "total_amount": 875.00,  # Positive for SELL (money in)
        "transaction_currency": "USD",
        "transaction_date": "2024-02-15",
        "notes": "E2E Test - Sell AAPL (FIFO from lot 1)",
        "skip_cash_validation": True,
        "skip_fifo_validation": True,
        "skip_price_validation": True,
    },
    # SAP purchases (EUR)
    {
        "transaction_type": "BUY",
        "ticker": f"{TEST_PREFIX}SAP",
        "quantity": 5,
        "price": 160.00,
        "total_amount": -800.00,
        "transaction_currency": "EUR",
        "transaction_date": "2024-01-20",
        "notes": "E2E Test - Buy SAP",
        "skip_cash_validation": True,
        "skip_fifo_validation": True,
        "skip_price_validation": True,
    },
    # CEZ purchases (CZK)
    {
        "transaction_type": "BUY",
        "ticker": f"{TEST_PREFIX}CEZ",
        "quantity": 100,
        "price": 850.00,
        "total_amount": -85000.00,
        "transaction_currency": "CZK",
        "transaction_date": "2024-01-10",
        "notes": "E2E Test - Buy CEZ lot 1",
        "skip_cash_validation": True,
        "skip_fifo_validation": True,
        "skip_price_validation": True,
    },
    {
        "transaction_type": "SELL",
        "ticker": f"{TEST_PREFIX}CEZ",
        "quantity": 50,
        "price": 880.00,
        "total_amount": 44000.00,
        "transaction_currency": "CZK",
        "transaction_date": "2024-02-20",
        "notes": "E2E Test - Sell CEZ (FIFO)",
        "skip_cash_validation": True,
        "skip_fifo_validation": True,
        "skip_price_validation": True,
    },
]

# Mock current prices (what the "market" price is today)
MOCK_CURRENT_PRICES = {
    f"{TEST_PREFIX}AAPL": 180.00,  # USD
    f"{TEST_PREFIX}SAP": 170.00,   # EUR
    f"{TEST_PREFIX}CEZ": 900.00,   # CZK
}

# Mock exchange rates for today
MOCK_EXCHANGE_RATES_TODAY = {
    ("USD", "CZK"): 22.80,
    ("EUR", "CZK"): 24.80,
    ("CZK", "CZK"): 1.00,
    # Inverse rates
    ("CZK", "USD"): 1/22.80,
    ("CZK", "EUR"): 1/24.80,
    ("USD", "EUR"): 24.80/22.80,
    ("EUR", "USD"): 22.80/24.80,
}

# Exchange rates for transaction dates (for cost basis calculation)
MOCK_EXCHANGE_RATES_HISTORICAL = {
    ("USD", "CZK", date(2024, 1, 1)): 22.50,
    ("USD", "CZK", date(2024, 1, 15)): 22.75,
    ("USD", "CZK", date(2024, 2, 1)): 23.00,
    ("USD", "CZK", date(2024, 2, 15)): 22.90,
    ("EUR", "CZK", date(2024, 1, 1)): 24.50,
    ("EUR", "CZK", date(2024, 1, 20)): 25.00,
    ("CZK", "CZK", date(2024, 1, 1)): 1.00,
    ("CZK", "CZK", date(2024, 1, 10)): 1.00,
    ("CZK", "CZK", date(2024, 2, 20)): 1.00,
}

# =============================================================================
# HELPER CLASSES
# =============================================================================

@dataclass
class HoldingCalc:
    """Calculated holding for verification"""
    ticker: str
    quantity: float
    currency: str
    current_price: float
    market_value_native: float
    exchange_rate: float
    market_value_czk: float


# =============================================================================
# CONSOLE OUTPUT FUNCTIONS
# =============================================================================

def print_header(text: str):
    """Print a major section header"""
    print()
    print(f"{Colors.BOLD}{'=' * 80}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text:^80}{Colors.ENDC}")
    print(f"{Colors.BOLD}{'=' * 80}{Colors.ENDC}")
    print()


def print_subheader(text: str):
    """Print a subsection header"""
    print()
    print(f"{Colors.BOLD}{Colors.BLUE}[{text}]{Colors.ENDC}")
    print("-" * 60)


def print_step(step_num: int, text: str):
    """Print a step header"""
    print()
    print(f"{Colors.BOLD}{Colors.YELLOW}[STEP {step_num}] {text}{Colors.ENDC}")
    print()


def print_success(text: str):
    """Print success message"""
    print(f"{Colors.GREEN}[OK] {text}{Colors.ENDC}")


def print_error(text: str):
    """Print error message"""
    print(f"{Colors.RED}[FAIL] {text}{Colors.ENDC}")


def print_warning(text: str):
    """Print warning message"""
    print(f"{Colors.YELLOW}[WARN] {text}{Colors.ENDC}")


def print_info(text: str):
    """Print info message"""
    print(f"{Colors.CYAN}[INFO] {text}{Colors.ENDC}")


def print_table(headers: List[str], rows: List[List[str]], column_widths: Optional[List[int]] = None):
    """Print a formatted table using ASCII characters for Windows compatibility"""
    if not column_widths:
        column_widths = [max(len(str(row[i])) for row in [headers] + rows) + 2 for i in range(len(headers))]

    # Header (using ASCII characters)
    header_row = "|".join(f" {h:^{w-2}} " for h, w in zip(headers, column_widths))
    separator = "+".join("-" * w for w in column_widths)
    top_border = "+".join("-" * w for w in column_widths)
    bottom_border = "+".join("-" * w for w in column_widths)

    print(f"+{top_border}+")
    print(f"|{header_row}|")
    print(f"+{separator}+")

    for row in rows:
        row_str = "|".join(f" {str(cell):^{w-2}} " for cell, w in zip(row, column_widths))
        print(f"|{row_str}|")

    print(f"+{bottom_border}+")


# =============================================================================
# API FUNCTIONS
# =============================================================================

def check_server_running() -> bool:
    """Check if the backend server is running"""
    try:
        response = requests.get(f"{API_BASE_URL}/transactions", timeout=5)
        return response.status_code in [200, 401, 403]
    except requests.exceptions.ConnectionError:
        return False


def get_all_transactions() -> List[Dict]:
    """Get all transactions from API"""
    response = requests.get(f"{API_BASE_URL}/transactions")
    response.raise_for_status()
    return response.json()


def create_transaction(transaction: Dict) -> Dict:
    """Create a transaction via API"""
    response = requests.post(f"{API_BASE_URL}/transactions", json=transaction)
    if response.status_code not in [200, 201]:
        print_error(f"Failed to create transaction: {response.text}")
        raise Exception(f"API error: {response.status_code}")
    return response.json()


def delete_transaction(transaction_id: int) -> bool:
    """Delete a transaction via API"""
    response = requests.delete(f"{API_BASE_URL}/transactions/{transaction_id}")
    return response.status_code == 204


def update_stock(ticker: str, updates: Dict) -> Dict:
    """Update stock via API"""
    response = requests.put(f"{API_BASE_URL}/stocks/{ticker}", json=updates)
    if response.status_code not in [200, 201]:
        print_warning(f"Failed to update stock {ticker}: {response.text}")
        return {}
    return response.json()


def get_kpis(currency: str = "CZK") -> Dict:
    """Get KPIs from API"""
    response = requests.get(f"{API_BASE_URL}/analytics/kpis", params={"currency": currency})
    response.raise_for_status()
    return response.json()


def recalculate_kpis() -> Dict:
    """Force KPI recalculation"""
    response = requests.post(f"{API_BASE_URL}/analytics/kpis/recalculate")
    response.raise_for_status()
    return response.json()


# =============================================================================
# DATABASE FUNCTIONS
# =============================================================================

def get_database_session():
    """Get a database session for direct manipulation"""
    # Import here to avoid issues if running without DB
    from models.database import Base, StockPrice, ExchangeRate, Stock

    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    return Session(), StockPrice, ExchangeRate, Stock


def insert_mock_prices(session, StockPrice) -> int:
    """Insert mock stock prices for today"""
    today = date.today()
    count = 0

    for ticker, price in MOCK_CURRENT_PRICES.items():
        # Check if price exists for today
        existing = session.query(StockPrice).filter(
            StockPrice.ticker == ticker,
            StockPrice.price_date == today
        ).first()

        if existing:
            existing.price = price
        else:
            price_record = StockPrice(
                ticker=ticker,
                price=price,
                price_date=today
            )
            session.add(price_record)
        count += 1

    session.commit()
    return count


def insert_mock_exchange_rates(session, ExchangeRate) -> int:
    """Insert mock exchange rates for today and historical dates"""
    count = 0
    today = date.today()
    now = datetime.utcnow()

    # Insert today's rates
    for (base, target), rate in MOCK_EXCHANGE_RATES_TODAY.items():
        existing = session.query(ExchangeRate).filter(
            ExchangeRate.base_currency == base,
            ExchangeRate.target_currency == target,
            ExchangeRate.rate_date == today
        ).first()

        if existing:
            existing.rate = rate
        else:
            rate_record = ExchangeRate(
                base_currency=base,
                target_currency=target,
                rate=rate,
                rate_date=today,
                source='e2e-test',
                fetched_at=now,
                confidence='high'
            )
            session.add(rate_record)
        count += 1

    # Insert historical rates for transaction dates
    for (base, target, rate_date), rate in MOCK_EXCHANGE_RATES_HISTORICAL.items():
        existing = session.query(ExchangeRate).filter(
            ExchangeRate.base_currency == base,
            ExchangeRate.target_currency == target,
            ExchangeRate.rate_date == rate_date
        ).first()

        if existing:
            existing.rate = rate
        else:
            rate_record = ExchangeRate(
                base_currency=base,
                target_currency=target,
                rate=rate,
                rate_date=rate_date,
                source='e2e-test-historical',
                fetched_at=now,
                confidence='high'
            )
            session.add(rate_record)
        count += 1

    session.commit()
    return count


def cleanup_test_data(session, Stock, StockPrice, ExchangeRate):
    """Clean up all test data from database"""
    # Delete test stock prices
    session.query(StockPrice).filter(
        StockPrice.ticker.like(f"{TEST_PREFIX}%")
    ).delete(synchronize_session=False)

    # Delete test stocks
    session.query(Stock).filter(
        Stock.ticker.like(f"{TEST_PREFIX}%")
    ).delete(synchronize_session=False)

    # Delete test exchange rates
    session.query(ExchangeRate).filter(
        ExchangeRate.source.in_(['e2e-test', 'e2e-test-historical'])
    ).delete(synchronize_session=False)

    session.commit()


# =============================================================================
# CALCULATION FUNCTIONS
# =============================================================================

def calculate_expected_holdings() -> List[HoldingCalc]:
    """
    Calculate expected holdings based on test transactions using FIFO method.
    Returns list of HoldingCalc with expected values.
    """
    holdings: Dict[str, Dict] = {}

    # Sort transactions by date
    sorted_txns = sorted(
        [t for t in TEST_TRANSACTIONS if t["transaction_type"] in ["BUY", "SELL"]],
        key=lambda x: x["transaction_date"]
    )

    for txn in sorted_txns:
        ticker = txn["ticker"]
        txn_type = txn["transaction_type"]
        qty = txn["quantity"]
        price = txn["price"]

        if ticker not in holdings:
            holdings[ticker] = {
                "purchases": [],  # List of (qty, price) tuples
                "total_quantity": 0,
            }

        if txn_type == "BUY":
            holdings[ticker]["purchases"].append((qty, price))
            holdings[ticker]["total_quantity"] += qty

        elif txn_type == "SELL":
            # FIFO: remove from oldest purchases first
            remaining_to_sell = qty
            new_purchases = []

            for lot_qty, lot_price in holdings[ticker]["purchases"]:
                if remaining_to_sell <= 0:
                    new_purchases.append((lot_qty, lot_price))
                elif lot_qty <= remaining_to_sell:
                    remaining_to_sell -= lot_qty
                else:
                    new_purchases.append((lot_qty - remaining_to_sell, lot_price))
                    remaining_to_sell = 0

            holdings[ticker]["purchases"] = new_purchases
            holdings[ticker]["total_quantity"] -= qty

    # Build result with current prices and exchange rates
    result = []
    today = date.today()

    for ticker, data in holdings.items():
        if data["total_quantity"] <= 0:
            continue

        currency = TEST_STOCKS[ticker]["currency"]
        current_price = MOCK_CURRENT_PRICES[ticker]
        quantity = data["total_quantity"]
        market_value_native = quantity * current_price

        # Get exchange rate for today
        rate_key = (currency, "CZK")
        exchange_rate = MOCK_EXCHANGE_RATES_TODAY.get(rate_key, 1.0)

        market_value_czk = market_value_native * exchange_rate

        result.append(HoldingCalc(
            ticker=ticker,
            quantity=quantity,
            currency=currency,
            current_price=current_price,
            market_value_native=market_value_native,
            exchange_rate=exchange_rate,
            market_value_czk=market_value_czk
        ))

    return result


def calculate_expected_stock_value(holdings: List[HoldingCalc]) -> float:
    """Calculate expected total stock value in CZK"""
    return sum(h.market_value_czk for h in holdings)


# =============================================================================
# TEST EXECUTION
# =============================================================================

def run_test():
    """Main test execution function"""
    print_header("STOCK VALUE KPI E2E TEST")

    # Check server
    print_subheader("CHECKING BACKEND SERVER")
    if not check_server_running():
        print_error("Backend server is not running!")
        print_info("Start the server with: cd backend && python -m uvicorn app:app --reload")
        return False
    print_success("Backend server is running")

    # Get database session
    print_subheader("CONNECTING TO DATABASE")
    try:
        session, StockPrice, ExchangeRate, Stock = get_database_session()
        print_success("Database connection established")
    except Exception as e:
        print_error(f"Failed to connect to database: {e}")
        return False

    created_transaction_ids = []

    try:
        # Cleanup previous test data
        print_subheader("CLEANING UP PREVIOUS TEST DATA")

        # Delete test transactions via API
        all_txns = get_all_transactions()
        test_txns = [t for t in all_txns if t.get("notes", "").startswith("E2E Test")]
        for txn in test_txns:
            delete_transaction(txn["id"])
        print_info(f"Deleted {len(test_txns)} previous test transactions")

        # Clean up database records
        cleanup_test_data(session, Stock, StockPrice, ExchangeRate)
        print_success("Database cleanup complete")

        # Insert mock exchange rates
        print_subheader("INSERTING MOCK EXCHANGE RATES")
        rate_count = insert_mock_exchange_rates(session, ExchangeRate)
        print_success(f"Inserted {rate_count} exchange rates")

        print_table(
            ["From", "To", "Rate"],
            [
                ["USD", "CZK", f"{MOCK_EXCHANGE_RATES_TODAY[('USD', 'CZK')]:.4f}"],
                ["EUR", "CZK", f"{MOCK_EXCHANGE_RATES_TODAY[('EUR', 'CZK')]:.4f}"],
                ["CZK", "CZK", "1.0000"],
            ]
        )

        # Create test transactions
        print_subheader("CREATING TEST TRANSACTIONS")

        rows = []
        for i, txn in enumerate(TEST_TRANSACTIONS, 1):
            result = create_transaction(txn)
            created_transaction_ids.append(result["id"])

            rows.append([
                str(i),
                txn["transaction_type"],
                txn["ticker"] or "-",
                str(txn["quantity"] or "-"),
                f"{txn['price']:.2f}" if txn["price"] else "-",
                txn["transaction_currency"],
                txn["transaction_date"]
            ])

        print_table(
            ["#", "Type", "Ticker", "Qty", "Price", "Currency", "Date"],
            rows,
            [4, 10, 14, 8, 10, 10, 12]
        )
        print_success(f"Created {len(created_transaction_ids)} transactions")

        # Update stock currencies
        print_subheader("UPDATING STOCK CURRENCIES")
        for ticker, info in TEST_STOCKS.items():
            update_stock(ticker, {"currency": info["currency"]})
            print_info(f"{ticker}: currency set to {info['currency']}")

        # Insert mock stock prices
        print_subheader("INSERTING MOCK STOCK PRICES")
        price_count = insert_mock_prices(session, StockPrice)
        print_success(f"Inserted {price_count} stock prices")

        print_table(
            ["Ticker", "Current Price", "Currency"],
            [
                [ticker, f"{price:.2f}", TEST_STOCKS[ticker]["currency"]]
                for ticker, price in MOCK_CURRENT_PRICES.items()
            ]
        )

        # Calculate expected values
        print_step(1, "CALCULATING EXPECTED HOLDINGS (FIFO Method)")

        holdings = calculate_expected_holdings()

        print("Processing transactions:")
        print()

        # Show FIFO calculation for AAPL
        print(f"  {Colors.BOLD}{TEST_PREFIX}AAPL:{Colors.ENDC}")
        print(f"    -> BUY 10 @ $150 (2024-01-15): Total = 10 shares")
        print(f"    -> BUY 5 @ $160 (2024-02-01): Total = 15 shares")
        print(f"    -> SELL 5 @ $175 (2024-02-15): FIFO removes 5 from first lot")
        print(f"      Remaining: 5 @ $150, 5 @ $160 = {Colors.GREEN}10 shares{Colors.ENDC}")
        print()

        # Show FIFO calculation for SAP
        print(f"  {Colors.BOLD}{TEST_PREFIX}SAP:{Colors.ENDC}")
        print(f"    -> BUY 5 @ EUR 160 (2024-01-20): Total = {Colors.GREEN}5 shares{Colors.ENDC}")
        print()

        # Show FIFO calculation for CEZ
        print(f"  {Colors.BOLD}{TEST_PREFIX}CEZ:{Colors.ENDC}")
        print(f"    -> BUY 100 @ 850 CZK (2024-01-10): Total = 100 shares")
        print(f"    -> SELL 50 @ 880 CZK (2024-02-20): FIFO removes 50 shares")
        print(f"      Remaining: {Colors.GREEN}50 shares{Colors.ENDC}")
        print()

        print_table(
            ["Ticker", "Quantity", "Currency"],
            [[h.ticker, f"{h.quantity:.0f}", h.currency] for h in holdings]
        )

        print_step(2, "CURRENT STOCK PRICES")
        print_table(
            ["Ticker", "Current Price", "Currency"],
            [[h.ticker, f"{h.current_price:.2f}", h.currency] for h in holdings]
        )

        print_step(3, "MARKET VALUE (Native Currency)")
        print_table(
            ["Ticker", "Quantity", "Price", "Market Value"],
            [
                [
                    h.ticker,
                    f"{h.quantity:.0f}",
                    f"{h.current_price:.2f} {h.currency}",
                    f"{h.market_value_native:,.2f} {h.currency}"
                ]
                for h in holdings
            ]
        )

        print_step(4, "CONVERTING TO CZK")

        print(f"Exchange Rates (today = {date.today()}):")
        print(f"  USD/CZK = {MOCK_EXCHANGE_RATES_TODAY[('USD', 'CZK')]:.2f}")
        print(f"  EUR/CZK = {MOCK_EXCHANGE_RATES_TODAY[('EUR', 'CZK')]:.2f}")
        print()

        print_table(
            ["Ticker", "Market Value", "Rate", "Market Value CZK"],
            [
                [
                    h.ticker,
                    f"{h.market_value_native:,.2f} {h.currency}",
                    f"x {h.exchange_rate:.2f}",
                    f"{h.market_value_czk:,.2f} CZK"
                ]
                for h in holdings
            ]
        )

        print_step(5, "SUMMING TOTAL STOCK VALUE")

        expected_stock_value = calculate_expected_stock_value(holdings)

        sum_parts = " + ".join([f"{h.market_value_czk:,.2f}" for h in holdings])
        print(f"Total Stock Value = {sum_parts}")
        print(f"                  = {Colors.BOLD}{Colors.GREEN}{expected_stock_value:,.2f} CZK{Colors.ENDC}")

        print_header(f"EXPECTED RESULT: Stock Value = {expected_stock_value:,.2f} CZK")

        # Force recalculation
        print_subheader("FORCING KPI RECALCULATION")
        recalculate_kpis()
        print_success("KPI recalculation triggered")

        # Get actual KPIs
        print_subheader("CALLING API: GET /analytics/kpis?currency=CZK")
        kpis = get_kpis("CZK")

        actual_stock_value = kpis["portfolio_summary"]["total_value"]

        print()
        print("API Response (portfolio_summary):")
        print(f"  total_value: {actual_stock_value:,.2f}")
        print(f"  total_cost_basis: {kpis['portfolio_summary']['total_cost_basis']:,.2f}")
        print(f"  total_unrealized_gain: {kpis['portfolio_summary']['total_unrealized_gain']:,.2f}")
        print(f"  cash_balance: {kpis['portfolio_summary']['cash_balance']:,.2f}")
        print(f"  number_of_holdings: {kpis['portfolio_summary']['number_of_holdings']}")
        print()

        # Compare results
        print_subheader("VERIFICATION")

        # Calculate tolerance (0.01% or 1 CZK, whichever is larger)
        tolerance = max(expected_stock_value * 0.0001, 1.0)
        difference = abs(actual_stock_value - expected_stock_value)

        passed = difference <= tolerance
        status = f"{Colors.GREEN}PASS{Colors.ENDC}" if passed else f"{Colors.RED}FAIL{Colors.ENDC}"

        print_table(
            ["KPI", "Expected", "Actual", "Diff", "Status"],
            [[
                "Stock Value",
                f"{expected_stock_value:,.2f}",
                f"{actual_stock_value:,.2f}",
                f"{difference:,.2f}",
                "PASS" if passed else "FAIL"
            ]],
            [14, 14, 14, 10, 8]
        )

        if passed:
            print_header("TEST RESULT: PASSED")
            print_success("Stock Value KPI is calculated correctly!")
        else:
            print_header("TEST RESULT: FAILED")
            print_error(f"Stock Value mismatch!")
            print_error(f"Expected: {expected_stock_value:,.2f} CZK")
            print_error(f"Actual:   {actual_stock_value:,.2f} CZK")
            print_error(f"Difference: {difference:,.2f} CZK")

            # Debug info
            print()
            print_warning("Debug Information:")
            print(f"  - Check if stock prices were cached correctly")
            print(f"  - Check if exchange rates for today exist in database")
            print(f"  - Check if all test transactions were created")
            print(f"  - Verify FIFO calculation in holdings")

        return passed

    except Exception as e:
        print_error(f"Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Cleanup
        print_subheader("CLEANUP")

        # Delete test transactions
        for txn_id in created_transaction_ids:
            try:
                delete_transaction(txn_id)
            except:
                pass
        print_info(f"Deleted {len(created_transaction_ids)} test transactions")

        # Clean database
        try:
            cleanup_test_data(session, Stock, StockPrice, ExchangeRate)
            print_info("Database test data cleaned")
        except:
            pass

        session.close()


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    # Enable Windows color support
    if sys.platform == "win32":
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)

    success = run_test()
    sys.exit(0 if success else 1)
