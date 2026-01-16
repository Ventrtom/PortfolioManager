"""
Test fixtures for Portfolio Summary KPI E2E tests.

Contains:
- Stock definitions (3 stocks in different currencies)
- Exchange rates for deterministic testing
- Stock prices for test dates
- Transaction scenarios covering all types
"""
from datetime import date, datetime
from decimal import Decimal


# =============================================================================
# STOCK DEFINITIONS (3 stocks in USD, EUR, CZK)
# =============================================================================

STOCKS = {
    'AAPL': {
        'ticker': 'AAPL',
        'company_name': 'Apple Inc.',
        'sector': 'Technology',
        'industry': 'Consumer Electronics',
        'currency': 'USD',
        'resolved_symbol': 'AAPL'
    },
    'SAP': {
        'ticker': 'SAP',
        'company_name': 'SAP SE',
        'sector': 'Technology',
        'industry': 'Software',
        'currency': 'EUR',
        'resolved_symbol': 'SAP.DE'
    },
    'CEZ': {
        'ticker': 'CEZ',
        'company_name': 'CEZ Group',
        'sector': 'Utilities',
        'industry': 'Electric Utilities',
        'currency': 'CZK',
        'resolved_symbol': 'CEZ.PR'
    }
}


# =============================================================================
# EXCHANGE RATES
# Fixed rates for deterministic testing
# =============================================================================

def get_today():
    """Get today's date for test fixtures."""
    return date.today()


EXCHANGE_RATES = [
    # USD to CZK
    {'base': 'USD', 'target': 'CZK', 'date': date(2024, 1, 1), 'rate': 22.50},
    {'base': 'USD', 'target': 'CZK', 'date': date(2024, 1, 15), 'rate': 22.75},
    {'base': 'USD', 'target': 'CZK', 'date': date(2024, 2, 1), 'rate': 23.00},
    {'base': 'USD', 'target': 'CZK', 'date': date(2024, 3, 1), 'rate': 22.80},

    # EUR to CZK
    {'base': 'EUR', 'target': 'CZK', 'date': date(2024, 1, 1), 'rate': 24.50},
    {'base': 'EUR', 'target': 'CZK', 'date': date(2024, 1, 15), 'rate': 24.75},
    {'base': 'EUR', 'target': 'CZK', 'date': date(2024, 1, 20), 'rate': 24.80},
    {'base': 'EUR', 'target': 'CZK', 'date': date(2024, 2, 1), 'rate': 25.00},
    {'base': 'EUR', 'target': 'CZK', 'date': date(2024, 3, 1), 'rate': 24.80},

    # CZK to USD (inverse)
    {'base': 'CZK', 'target': 'USD', 'date': date(2024, 1, 1), 'rate': 0.04444},
    {'base': 'CZK', 'target': 'USD', 'date': date(2024, 1, 15), 'rate': 0.04396},
    {'base': 'CZK', 'target': 'USD', 'date': date(2024, 2, 1), 'rate': 0.04348},
    {'base': 'CZK', 'target': 'USD', 'date': date(2024, 3, 1), 'rate': 0.04386},

    # CZK to EUR (inverse)
    {'base': 'CZK', 'target': 'EUR', 'date': date(2024, 1, 1), 'rate': 0.04082},
    {'base': 'CZK', 'target': 'EUR', 'date': date(2024, 1, 15), 'rate': 0.04040},
    {'base': 'CZK', 'target': 'EUR', 'date': date(2024, 1, 20), 'rate': 0.04032},
    {'base': 'CZK', 'target': 'EUR', 'date': date(2024, 2, 1), 'rate': 0.04000},
    {'base': 'CZK', 'target': 'EUR', 'date': date(2024, 3, 1), 'rate': 0.04032},

    # USD to EUR
    {'base': 'USD', 'target': 'EUR', 'date': date(2024, 1, 1), 'rate': 0.92},
    {'base': 'USD', 'target': 'EUR', 'date': date(2024, 1, 15), 'rate': 0.92},
    {'base': 'USD', 'target': 'EUR', 'date': date(2024, 2, 1), 'rate': 0.92},
    {'base': 'USD', 'target': 'EUR', 'date': date(2024, 3, 1), 'rate': 0.92},

    # EUR to USD
    {'base': 'EUR', 'target': 'USD', 'date': date(2024, 1, 1), 'rate': 1.087},
    {'base': 'EUR', 'target': 'USD', 'date': date(2024, 1, 15), 'rate': 1.087},
    {'base': 'EUR', 'target': 'USD', 'date': date(2024, 2, 1), 'rate': 1.087},
    {'base': 'EUR', 'target': 'USD', 'date': date(2024, 3, 1), 'rate': 1.087},
]


def get_test_exchange_rates():
    """
    Get exchange rates including today's date for market value conversion.
    Uses the Mar 1 rates as "current" rates (22.80 USD/CZK, 24.80 EUR/CZK).
    """
    rates = EXCHANGE_RATES.copy()
    today = get_today()

    # Add today's rates (same as Mar 1 rates - the "current" rates)
    rates.extend([
        {'base': 'USD', 'target': 'CZK', 'date': today, 'rate': 22.80},
        {'base': 'EUR', 'target': 'CZK', 'date': today, 'rate': 24.80},
        {'base': 'CZK', 'target': 'USD', 'date': today, 'rate': 0.04386},
        {'base': 'CZK', 'target': 'EUR', 'date': today, 'rate': 0.04032},
        {'base': 'USD', 'target': 'EUR', 'date': today, 'rate': 0.92},
        {'base': 'EUR', 'target': 'USD', 'date': today, 'rate': 1.087},
    ])

    return rates


# =============================================================================
# STOCK PRICES
# Current prices for test date (2024-03-01)
# =============================================================================

CURRENT_PRICES = {
    'AAPL': 180.00,  # USD
    'SAP': 170.00,   # EUR
    'CEZ': 950.00,   # CZK
}

# Historical prices for testing
HISTORICAL_PRICES = {
    ('AAPL', date(2024, 1, 15)): 150.00,
    ('AAPL', date(2024, 2, 1)): 160.00,
    ('AAPL', date(2024, 3, 1)): 180.00,
    ('SAP', date(2024, 1, 20)): 160.00,
    ('SAP', date(2024, 2, 1)): 165.00,
    ('SAP', date(2024, 3, 1)): 170.00,
    ('CEZ', date(2024, 1, 25)): 900.00,
    ('CEZ', date(2024, 2, 15)): 920.00,
    ('CEZ', date(2024, 3, 1)): 950.00,
}


# =============================================================================
# TRANSACTION SCENARIOS
# =============================================================================

# Scenario 1: Single CZK stock - no currency conversion
SCENARIO_SINGLE_CZK = {
    'name': 'Single CZK Stock',
    'description': 'Test basic calculations without currency conversion',
    'transactions': [
        {
            'type': 'DEPOSIT',
            'date': date(2024, 1, 1),
            'ticker': '',
            'quantity': None,
            'price': None,
            'total_amount': 100000,
            'currency': 'CZK'
        },
        {
            'type': 'BUY',
            'date': date(2024, 1, 25),
            'ticker': 'CEZ',
            'quantity': 10,
            'price': 900,
            'total_amount': -9000,  # Negative: money out
            'currency': 'CZK'
        },
    ],
    'expected': {
        # Holdings: 10 shares @ 950 CZK = 9,500 CZK
        'total_value': 9500.00,
        # Cost: 10 * 900 = 9,000 CZK
        'cost_basis': 9000.00,
        # Unrealized: 9,500 - 9,000 = 500 CZK
        'unrealized_gain': 500.00,
        'unrealized_gain_percent': 5.56,  # 500/9000 * 100
        'realized_gain': 0.00,
        # Cash: 100,000 - 9,000 = 91,000 CZK
        'cash_balance': 91000.00,
        'number_of_holdings': 1
    }
}


# Scenario 2: Multi-currency portfolio
SCENARIO_MULTI_CURRENCY = {
    'name': 'Multi-Currency Portfolio',
    'description': 'Test currency conversion using transaction-date rates',
    'transactions': [
        {
            'type': 'DEPOSIT',
            'date': date(2024, 1, 1),
            'ticker': '',
            'quantity': None,
            'price': None,
            'total_amount': 100000,
            'currency': 'CZK'
        },
        {
            'type': 'BUY',
            'date': date(2024, 1, 15),
            'ticker': 'AAPL',
            'quantity': 10,
            'price': 150,
            'total_amount': -1500,  # USD
            'currency': 'USD'
        },
        {
            'type': 'BUY',
            'date': date(2024, 2, 1),
            'ticker': 'SAP',
            'quantity': 5,
            'price': 160,
            'total_amount': -800,  # EUR
            'currency': 'EUR'
        },
    ],
    'expected': {
        # AAPL: 10 * 180 USD * 22.80 = 41,040 CZK
        # SAP: 5 * 170 EUR * 24.80 = 21,080 CZK
        'total_value': 62120.00,
        # AAPL cost: 1500 USD * 22.75 (Jan 15) = 34,125 CZK
        # SAP cost: 800 EUR * 25.00 (Feb 1) = 20,000 CZK
        'cost_basis': 54125.00,
        'unrealized_gain': 7995.00,  # 62,120 - 54,125
        'unrealized_gain_percent': 14.77,
        'realized_gain': 0.00,
        # Cash: 100,000 - 34,125 - 20,000 = 45,875 CZK
        'cash_balance': 45875.00,
        'number_of_holdings': 2
    }
}


# Scenario 3: FIFO Realized Gains
SCENARIO_FIFO_GAINS = {
    'name': 'FIFO Realized Gains',
    'description': 'Test FIFO cost basis matching for sells',
    'transactions': [
        {
            'type': 'DEPOSIT',
            'date': date(2024, 1, 1),
            'ticker': '',
            'quantity': None,
            'price': None,
            'total_amount': 100000,
            'currency': 'CZK'
        },
        # First lot: 10 shares @ 100 USD on Jan 15 (rate 22.75)
        {
            'type': 'BUY',
            'date': date(2024, 1, 15),
            'ticker': 'AAPL',
            'quantity': 10,
            'price': 100,
            'total_amount': -1000,
            'currency': 'USD'
        },
        # Second lot: 10 shares @ 120 USD on Feb 1 (rate 23.00)
        {
            'type': 'BUY',
            'date': date(2024, 2, 1),
            'ticker': 'AAPL',
            'quantity': 10,
            'price': 120,
            'total_amount': -1200,
            'currency': 'USD'
        },
        # Sell 15 shares @ 150 USD on Mar 1 (rate 22.80)
        # FIFO: 10 from lot1 + 5 from lot2
        {
            'type': 'SELL',
            'date': date(2024, 3, 1),
            'ticker': 'AAPL',
            'quantity': 15,
            'price': 150,
            'total_amount': 2250,
            'currency': 'USD'
        },
    ],
    'expected': {
        # Remaining: 5 shares @ 180 USD * 22.80 = 20,520 CZK
        'total_value': 20520.00,
        # Remaining cost: 5 shares from lot2 = 5 * 120 * 23.00 = 13,800 CZK
        'cost_basis': 13800.00,
        'unrealized_gain': 6720.00,  # 20,520 - 13,800
        'unrealized_gain_percent': 48.70,
        # Realized gain calculation:
        # Lot 1 cost: 10 * 100 * 22.75 = 22,750 CZK
        # Lot 2 partial cost: 5 * 120 * 23.00 = 13,800 CZK
        # Total sold cost: 22,750 + 13,800 = 36,550 CZK
        # Proceeds: 2250 USD * 22.80 = 51,300 CZK
        # Realized gain: 51,300 - 36,550 = 14,750 CZK
        'realized_gain': 14750.00,
        # Cash: 100,000 - 22,750 - 27,600 + 51,300 = 100,950 CZK
        'cash_balance': 100950.00,
        'number_of_holdings': 1
    }
}


# Scenario 4: Stock Split
SCENARIO_SPLIT = {
    'name': 'Stock Split',
    'description': 'Test stock split handling',
    'transactions': [
        {
            'type': 'DEPOSIT',
            'date': date(2024, 1, 1),
            'ticker': '',
            'quantity': None,
            'price': None,
            'total_amount': 100000,
            'currency': 'CZK'
        },
        # Buy 10 shares @ 400 USD
        {
            'type': 'BUY',
            'date': date(2024, 1, 15),
            'ticker': 'AAPL',
            'quantity': 10,
            'price': 400,
            'total_amount': -4000,
            'currency': 'USD'
        },
        # 4:1 split (quantity becomes 40, price becomes 100)
        {
            'type': 'SPLIT',
            'date': date(2024, 2, 1),
            'ticker': 'AAPL',
            'quantity': 4,  # Split ratio
            'price': None,
            'total_amount': 0,
            'currency': 'USD'
        },
    ],
    'expected': {
        # Holdings: 40 shares @ 180 USD * 22.80 = 327,360 CZK
        'total_value': 327360.00,
        # Cost: 4000 USD * 22.75 = 91,000 CZK (unchanged by split)
        'cost_basis': 91000.00,
        'unrealized_gain': 236360.00,
        'unrealized_gain_percent': 259.74,
        'realized_gain': 0.00,
        # Cash: 100,000 - 91,000 = 9,000 CZK
        'cash_balance': 9000.00,
        'number_of_holdings': 1
    }
}


# Scenario 5: All Transaction Types
SCENARIO_ALL_TYPES = {
    'name': 'All Transaction Types',
    'description': 'Comprehensive test with all transaction types',
    'transactions': [
        # Initial deposit
        {
            'type': 'DEPOSIT',
            'date': date(2024, 1, 1),
            'ticker': '',
            'quantity': None,
            'price': None,
            'total_amount': 100000,
            'currency': 'CZK'
        },
        # Withdrawal
        {
            'type': 'WITHDRAWAL',
            'date': date(2024, 1, 5),
            'ticker': '',
            'quantity': None,
            'price': None,
            'total_amount': -5000,
            'currency': 'CZK'
        },
        # Buy USD stock
        {
            'type': 'BUY',
            'date': date(2024, 1, 15),
            'ticker': 'AAPL',
            'quantity': 10,
            'price': 150,
            'total_amount': -1500,
            'currency': 'USD'
        },
        # Buy EUR stock
        {
            'type': 'BUY',
            'date': date(2024, 1, 20),
            'ticker': 'SAP',
            'quantity': 5,
            'price': 160,
            'total_amount': -800,
            'currency': 'EUR'
        },
        # Buy CZK stock
        {
            'type': 'BUY',
            'date': date(2024, 1, 25),
            'ticker': 'CEZ',
            'quantity': 10,
            'price': 900,
            'total_amount': -9000,
            'currency': 'CZK'
        },
        # AAPL dividend (USD)
        {
            'type': 'DIVIDEND',
            'date': date(2024, 2, 1),
            'ticker': 'AAPL',
            'quantity': None,
            'price': None,
            'total_amount': 15,  # USD
            'currency': 'USD'
        },
        # CEZ dividend (CZK)
        {
            'type': 'DIVIDEND',
            'date': date(2024, 2, 15),
            'ticker': 'CEZ',
            'quantity': None,
            'price': None,
            'total_amount': 500,
            'currency': 'CZK'
        },
        # Trading fee
        {
            'type': 'FEE',
            'date': date(2024, 2, 1),
            'ticker': '',
            'quantity': None,
            'price': None,
            'total_amount': -50,
            'currency': 'CZK'
        },
        # Tax payment
        {
            'type': 'TAX',
            'date': date(2024, 2, 15),
            'ticker': '',
            'quantity': None,
            'price': None,
            'total_amount': -100,
            'currency': 'CZK'
        },
        # Interest income
        {
            'type': 'INTEREST',
            'date': date(2024, 2, 28),
            'ticker': '',
            'quantity': None,
            'price': None,
            'total_amount': 25,
            'currency': 'CZK'
        },
        # Sell partial CEZ position
        {
            'type': 'SELL',
            'date': date(2024, 3, 1),
            'ticker': 'CEZ',
            'quantity': 5,
            'price': 950,
            'total_amount': 4750,
            'currency': 'CZK'
        },
    ],
    'expected': {
        # Holdings:
        # AAPL: 10 * 180 * 22.80 = 41,040 CZK
        # SAP: 5 * 170 * 24.80 = 21,080 CZK
        # CEZ: 5 * 950 = 4,750 CZK
        'total_value': 66870.00,
        # Cost basis:
        # AAPL: 1500 * 22.75 = 34,125 CZK
        # SAP: 800 * 24.80 = 19,840 CZK
        # CEZ: 5 * 900 = 4,500 CZK (remaining after sell)
        'cost_basis': 58465.00,
        'unrealized_gain': 8405.00,
        'unrealized_gain_percent': 14.37,
        # Realized gain: CEZ sold 5 @ 950 = 4,750, cost 5 @ 900 = 4,500
        # Gain: 4,750 - 4,500 = 250 CZK
        'realized_gain': 250.00,
        # Cash balance calculation:
        # +100,000 (deposit)
        # -5,000 (withdrawal)
        # -34,125 (AAPL buy: 1500 * 22.75)
        # -19,840 (SAP buy: 800 * 24.80)
        # -9,000 (CEZ buy)
        # +345 (AAPL div: 15 * 23.00)
        # +500 (CEZ div)
        # -50 (fee)
        # -100 (tax)
        # +25 (interest)
        # +4,750 (CEZ sell)
        'cash_balance': 37505.00,
        'number_of_holdings': 3
    }
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_exchange_rate(base: str, target: str, rate_date: date) -> float:
    """Get exchange rate from fixtures."""
    if base == target:
        return 1.0

    for rate in EXCHANGE_RATES:
        if rate['base'] == base and rate['target'] == target and rate['date'] == rate_date:
            return rate['rate']

    # Try to find closest earlier rate
    closest_rate = None
    closest_date = None
    for rate in EXCHANGE_RATES:
        if rate['base'] == base and rate['target'] == target and rate['date'] <= rate_date:
            if closest_date is None or rate['date'] > closest_date:
                closest_date = rate['date']
                closest_rate = rate['rate']

    return closest_rate


def get_current_price(ticker: str) -> float:
    """Get current price from fixtures."""
    return CURRENT_PRICES.get(ticker)


def get_stock_info(ticker: str) -> dict:
    """Get stock info from fixtures."""
    return STOCKS.get(ticker, {})
