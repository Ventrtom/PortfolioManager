import re
from datetime import datetime
from typing import Optional, Dict
from dateutil import parser as date_parser


class TransactionParser:
    """Parser for natural language transaction inputs"""

    @staticmethod
    def parse_transaction(input_text: str) -> Dict:
        """
        Parse natural language transaction input
        Expected format: "BUY - TICKER - QUANTITY - @PRICE - DATE"
        Examples:
            "BUY - ASM.US - 200 - @1.10 - 24.3.2025"
            "SELL - AAPL - 50 - @150.25 - 01/15/2025"
            "DIVIDEND - MSFT - 100 - 1/10/2025"
            "FEE - - - 9.99 - 2025-01-01"
        """
        try:
            # Clean up the input
            input_text = input_text.strip()

            # Split by dash separator
            parts = [p.strip() for p in input_text.split('-')]

            if len(parts) < 3:
                raise ValueError("Invalid format. Expected at least: TYPE - TICKER - ... - DATE")

            # Extract transaction type
            transaction_type = parts[0].upper()
            if transaction_type not in ['BUY', 'SELL', 'DIVIDEND', 'FEE', 'TAX']:
                raise ValueError(f"Invalid transaction type: {transaction_type}")

            # Extract ticker
            ticker = parts[1].strip().upper() if parts[1].strip() else ""

            # Parse based on transaction type
            if transaction_type in ['BUY', 'SELL']:
                # Format: TYPE - TICKER - QUANTITY - @PRICE - DATE
                if len(parts) < 5:
                    raise ValueError("BUY/SELL format: TYPE - TICKER - QUANTITY - @PRICE - DATE")

                quantity_str = parts[2].strip()
                price_str = parts[3].strip().replace('@', '').strip()
                date_str = parts[4].strip()

                quantity = float(quantity_str)
                price = float(price_str)
                total_amount = quantity * price

                transaction_date = TransactionParser._parse_date(date_str)

                return {
                    "transaction_type": transaction_type,
                    "ticker": ticker,
                    "quantity": quantity,
                    "price": price,
                    "total_amount": abs(total_amount) if transaction_type == 'BUY' else -abs(total_amount),
                    "transaction_date": transaction_date,
                    "raw_input": input_text
                }

            elif transaction_type == 'DIVIDEND':
                # Format: DIVIDEND - TICKER - AMOUNT - DATE
                if len(parts) < 4:
                    raise ValueError("DIVIDEND format: DIVIDEND - TICKER - AMOUNT - DATE")

                amount_str = parts[2].strip()
                date_str = parts[3].strip()

                amount = float(amount_str)
                transaction_date = TransactionParser._parse_date(date_str)

                return {
                    "transaction_type": transaction_type,
                    "ticker": ticker,
                    "quantity": None,
                    "price": None,
                    "total_amount": abs(amount),
                    "transaction_date": transaction_date,
                    "raw_input": input_text
                }

            elif transaction_type in ['FEE', 'TAX']:
                # Format: FEE - - - AMOUNT - DATE or FEE - TICKER - AMOUNT - DATE
                if len(parts) >= 5:
                    # Has ticker
                    amount_str = parts[3].strip()
                    date_str = parts[4].strip()
                elif len(parts) >= 4:
                    # No ticker
                    ticker = ""
                    amount_str = parts[2].strip()
                    date_str = parts[3].strip()
                else:
                    raise ValueError("FEE/TAX format: FEE - AMOUNT - DATE or FEE - TICKER - AMOUNT - DATE")

                amount = float(amount_str)
                transaction_date = TransactionParser._parse_date(date_str)

                return {
                    "transaction_type": transaction_type,
                    "ticker": ticker if ticker else "CASH",
                    "quantity": None,
                    "price": None,
                    "total_amount": -abs(amount),  # Fees are negative
                    "transaction_date": transaction_date,
                    "raw_input": input_text
                }

        except Exception as e:
            raise ValueError(f"Failed to parse transaction: {str(e)}")

    @staticmethod
    def _parse_date(date_str: str) -> datetime.date:
        """
        Parse various date formats
        Supports: DD.MM.YYYY, MM/DD/YYYY, YYYY-MM-DD, etc.
        """
        try:
            # Try common formats first
            for fmt in ['%d.%m.%Y', '%m/%d/%Y', '%Y-%m-%d', '%d-%m-%Y', '%m-%d-%Y']:
                try:
                    return datetime.strptime(date_str, fmt).date()
                except ValueError:
                    continue

            # Use dateutil parser as fallback
            parsed_date = date_parser.parse(date_str, dayfirst=False)
            return parsed_date.date()

        except Exception as e:
            raise ValueError(f"Could not parse date: {date_str}")

    @staticmethod
    def validate_parsed_data(data: Dict) -> bool:
        """Validate parsed transaction data"""
        required_fields = ['transaction_type', 'ticker', 'total_amount', 'transaction_date']

        for field in required_fields:
            if field not in data:
                return False

        if data['transaction_type'] in ['BUY', 'SELL']:
            if not data.get('quantity') or not data.get('price'):
                return False

        return True

    @staticmethod
    def format_for_display(data: Dict) -> str:
        """Format parsed data back to readable string"""
        transaction_type = data['transaction_type']
        ticker = data['ticker']
        date_str = data['transaction_date'].strftime('%m/%d/%Y')

        if transaction_type in ['BUY', 'SELL']:
            quantity = data['quantity']
            price = data['price']
            return f"{transaction_type} {quantity} shares of {ticker} @ ${price:.2f} on {date_str}"
        elif transaction_type == 'DIVIDEND':
            amount = data['total_amount']
            return f"DIVIDEND of ${amount:.2f} from {ticker} on {date_str}"
        elif transaction_type in ['FEE', 'TAX']:
            amount = abs(data['total_amount'])
            return f"{transaction_type} of ${amount:.2f} on {date_str}"

        return str(data)
