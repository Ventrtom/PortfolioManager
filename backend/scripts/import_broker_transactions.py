"""
Broker Transaction CSV Importer
Imports broker transactions from CSV format into the portfolio management system.

Usage:
    python import_broker_transactions.py transactions.csv --dry-run
    python import_broker_transactions.py transactions.csv
    python import_broker_transactions.py --rollback BATCH_ID
"""

import csv
import re
import sys
import argparse
from datetime import datetime, date
from typing import List, Dict, Tuple, Optional
from collections import defaultdict
from dataclasses import dataclass
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, '.')

from models.database import SessionLocal, Transaction
from models.schemas import TransactionCreate
from services.transaction_service import TransactionService
from services.exchange_rate_service import ExchangeRateService
from sqlalchemy import func


@dataclass
class BrokerTransaction:
    """Represents a parsed transaction from broker CSV"""
    broker_id: str
    broker_type: str
    timestamp: str
    date: date
    comment: str
    ticker: str
    amount: float


class BrokerCSVParser:
    """Parse broker CSV with European decimal format"""

    def parse(self, csv_path: str) -> List[BrokerTransaction]:
        """Parse CSV file and return structured transactions"""
        transactions = []

        try:
            with open(csv_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)

                for row in reader:
                    # Skip header row if it appears in data
                    if row['ID'] == 'ID':
                        continue

                    # Parse amount: European format "4.729,52" → 4729.52
                    amount_str = row['Amount'].replace('"', '').replace(',', '.')
                    amount = float(amount_str) if amount_str else 0.0

                    # Parse date: DD/MM/YYYY HH:MM:SS
                    date_obj = datetime.strptime(row['Time'], '%d/%m/%Y %H:%M:%S').date()

                    # Normalize ticker: remove .US suffix
                    ticker = row['Symbol'].replace('.US', '').upper() if row['Symbol'] else ''

                    transactions.append(BrokerTransaction(
                        broker_id=row['ID'],
                        broker_type=row['Type'],
                        timestamp=row['Time'],
                        date=date_obj,
                        comment=row['Comment'],
                        ticker=ticker,
                        amount=amount
                    ))

            print(f"[OK] Parsed {len(transactions)} transactions from CSV")
            return transactions

        except Exception as e:
            print(f"[ERROR] Error parsing CSV: {str(e)}")
            raise


class CommissionParser:
    """Extract quantity and price from commission comments"""

    def parse_comment(self, comment: str) -> Optional[Tuple[float, float]]:
        """
        Parse 'BUY 55 @ 3.45' → (55.0, 3.45)
        Returns (quantity, usd_price) or None if parsing fails
        """
        try:
            # Pattern: BUY <quantity> @ <price>
            match = re.search(r'BUY\s+(\d+(?:\.\d+)?)\s+@\s+(\d+(?:\.\d+)?)', comment)
            if match:
                quantity = float(match.group(1))
                usd_price = float(match.group(2))
                return (quantity, usd_price)
            return None
        except Exception as e:
            print(f"  Warning: Failed to parse commission comment '{comment}': {e}")
            return None


class SplitParser:
    """Parse stock split information from comments"""

    def parse_split(self, comment: str) -> Optional[Tuple[int, int]]:
        """
        Parse 'NBR.US split 1 for 50' → (1, 50)
        Returns (old_shares, new_shares) or None
        """
        try:
            match = re.search(r'split\s+(\d+)\s+for\s+(\d+)', comment, re.IGNORECASE)
            if match:
                old_shares = int(match.group(1))
                new_shares = int(match.group(2))
                return (old_shares, new_shares)
            return None
        except Exception as e:
            print(f"  Warning: Failed to parse split comment '{comment}': {e}")
            return None


class ExchangeRateConverter:
    """Convert USD prices to CZK using historical rates"""

    def __init__(self, db):
        self.db = db
        self.rate_cache = {}

    def convert_usd_to_czk(self, usd_price: float, transaction_date: date) -> float:
        """Convert USD price to CZK using historical rate"""
        # Check cache first
        cache_key = transaction_date.isoformat()
        if cache_key in self.rate_cache:
            return usd_price * self.rate_cache[cache_key]

        # Fetch rate from service
        try:
            rate = ExchangeRateService.get_exchange_rate(
                base_currency='USD',
                target_currency='CZK',
                rate_date=transaction_date,
                db=self.db
            )

            if rate:
                self.rate_cache[cache_key] = rate
                return usd_price * rate
            else:
                print(f"  Warning: No exchange rate for {transaction_date}, using fallback")
                # Use approximate rate as fallback
                return usd_price * 25.0

        except Exception as e:
            print(f"  Warning: Exchange rate fetch failed: {e}, using fallback")
            return usd_price * 25.0

    def preload_rates(self, dates: List[date]):
        """Batch fetch all exchange rates for given dates"""
        print(f"Pre-loading exchange rates for {len(set(dates))} unique dates...")
        try:
            for txn_date in set(dates):
                # This will fetch and cache the rate
                ExchangeRateService.get_exchange_rate(
                    base_currency='USD',
                    target_currency='CZK',
                    rate_date=txn_date,
                    db=self.db
                )
            print("[OK] Exchange rates pre-loaded successfully")
        except Exception as e:
            print(f"  Warning: Some exchange rates could not be loaded: {e}")


class FIFOQuantityCalculator:
    """Calculate SELL quantities using FIFO from existing holdings"""

    def __init__(self, db):
        self.db = db

    def calculate_sell_quantity(self, ticker: str, sell_date: date, proceeds_czk: float) -> float:
        """
        Calculate quantity sold using FIFO from existing BUY transactions
        """
        # Get all BUY transactions for this ticker before the sell date
        buys = self.db.query(Transaction).filter(
            Transaction.ticker == ticker,
            Transaction.transaction_type == 'BUY',
            Transaction.transaction_date <= sell_date
        ).order_by(Transaction.transaction_date.asc()).all()

        # Get all prior SELL transactions
        prior_sells = self.db.query(Transaction).filter(
            Transaction.ticker == ticker,
            Transaction.transaction_type == 'SELL',
            Transaction.transaction_date < sell_date
        ).order_by(Transaction.transaction_date.asc()).all()

        # Calculate available shares using FIFO
        total_bought = sum(buy.quantity or 0 for buy in buys)
        total_sold = sum(sell.quantity or 0 for sell in prior_sells)
        available = total_bought - total_sold

        # If we have historical purchases, estimate quantity from average cost
        if buys:
            total_cost = sum((buy.quantity or 0) * (buy.price or 0) for buy in buys)
            total_qty = sum(buy.quantity or 0 for buy in buys)
            if total_qty > 0:
                avg_cost = total_cost / total_qty
                if avg_cost > 0:
                    estimated_qty = proceeds_czk / avg_cost
                    # Return the minimum to avoid over-selling
                    return min(available, estimated_qty)

        # Fallback: estimate from current available shares
        if available > 0:
            return available

        return 0.0


class MultiRowOrderHandler:
    """Handle multi-row purchase orders with proportional quantity split"""

    def split_quantity_proportionally(
        self,
        stock_purchase_rows: List[BrokerTransaction],
        total_quantity: float
    ) -> List[float]:
        """
        Split quantity across rows by amount proportion.

        Example: 100 shares across 7 rows with amounts [787.2, 787.2, ..., 157.44]
        Returns proportional quantities
        """
        total_amount = sum(abs(row.amount) for row in stock_purchase_rows)

        if total_amount == 0:
            # Equal split as fallback
            qty_per_row = total_quantity / len(stock_purchase_rows)
            return [qty_per_row] * len(stock_purchase_rows)

        quantities = []
        for row in stock_purchase_rows:
            proportion = abs(row.amount) / total_amount
            row_quantity = total_quantity * proportion
            quantities.append(row_quantity)

        return quantities


class BrokerTransactionImporter:
    """Main orchestrator for broker transaction import"""

    # Type mapping from broker to system
    BROKER_TO_SYSTEM_TYPE = {
        'deposit': 'DEPOSIT',
        'withdrawal': 'WITHDRAWAL',
        'Stock purchase': 'BUY',
        'Stock sale': None,  # Merged with close trade
        'close trade': None,  # Merged with Stock sale
        'commission': 'FEE',
        'DIVIDENT': 'DIVIDEND',
        'Withholding Tax': 'TAX',
        'Sec Fee': 'FEE',
        'Free-funds Interest': 'INTEREST',
        'Free-funds Interest Tax': 'TAX',
        'fractional shares': 'SPLIT'
    }

    # Priority for chronological sorting
    TYPE_PRIORITY = {
        'DEPOSIT': 1,
        'BUY': 2,
        'DIVIDEND': 3,
        'INTEREST': 3,
        'SELL': 4,
        'FEE': 5,
        'TAX': 5,
        'WITHDRAWAL': 6,
        'SPLIT': 7
    }

    def __init__(self, csv_path: str, dry_run: bool = False):
        self.csv_path = csv_path
        self.dry_run = dry_run
        self.db = SessionLocal()
        self.batch_id = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Helper classes
        self.parser = BrokerCSVParser()
        self.commission_parser = CommissionParser()
        self.split_parser = SplitParser()
        self.rate_converter = ExchangeRateConverter(self.db)
        self.fifo_calculator = FIFOQuantityCalculator(self.db)
        self.multi_row_handler = MultiRowOrderHandler()

        # Statistics
        self.stats = {
            'parsed': 0,
            'imported': 0,
            'skipped': 0,
            'errors': 0,
            'by_type': defaultdict(int)
        }
        self.errors = []

    def run(self):
        """Execute the import process"""
        try:
            print("=" * 70)
            print("BROKER TRANSACTION IMPORT")
            print("=" * 70)
            print(f"CSV File: {self.csv_path}")
            print(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE IMPORT'}")
            print(f"Batch ID: {self.batch_id}")
            print()

            # Step 1: Parse CSV
            print("Step 1: Parsing CSV...")
            broker_transactions = self.parser.parse(self.csv_path)
            self.stats['parsed'] = len(broker_transactions)

            # Step 2: Pre-load exchange rates (skipped - fetched on-demand)
            print("\nStep 2: Exchange rates will be fetched on-demand during transformation")

            # Step 3: Group and transform transactions
            print("\nStep 3: Transforming transactions...")
            system_transactions = self.transform_transactions(broker_transactions)

            # Step 4: Sort chronologically
            print(f"\nStep 4: Sorting {len(system_transactions)} transactions...")
            system_transactions.sort(key=lambda t: (
                t['transaction_date'],
                self.TYPE_PRIORITY.get(t['transaction_type'], 99)
            ))

            # Step 5: Import transactions
            if not self.dry_run:
                print("\nStep 5: Importing transactions...")
                self.import_transactions(system_transactions)
            else:
                print("\nStep 5: DRY RUN - No import performed")
                for txn in system_transactions[:10]:  # Show first 10
                    qty = txn.get('quantity') or 0
                    price = txn.get('price') or 0
                    print(f"  {txn['transaction_date']} {txn['transaction_type']:10} "
                          f"{txn['ticker']:8} {qty:8.2f} @ "
                          f"{price:8.2f} = {txn['total_amount']:10.2f} CZK")
                if len(system_transactions) > 10:
                    print(f"  ... and {len(system_transactions) - 10} more")

            # Step 6: Print summary
            self.print_summary()

            return True

        except Exception as e:
            print(f"\n[ERROR] Import failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            self.db.close()

    def transform_transactions(self, broker_transactions: List[BrokerTransaction]) -> List[Dict]:
        """Transform broker transactions to system format"""
        system_transactions = []

        # Group transactions by type for processing
        by_type = defaultdict(list)
        for txn in broker_transactions:
            by_type[txn.broker_type].append(txn)

        # Process deposits and withdrawals (simple mapping)
        for txn in by_type['deposit'] + by_type['withdrawal']:
            system_type = self.BROKER_TO_SYSTEM_TYPE[txn.broker_type]
            system_transactions.append({
                'transaction_type': system_type,
                'ticker': '',
                'quantity': None,
                'price': None,
                'total_amount': abs(txn.amount) if system_type == 'DEPOSIT' else txn.amount,
                'transaction_date': txn.date,
                'transaction_currency': 'CZK',
                'notes': txn.comment,
                'broker_transaction_id': txn.broker_id,
                'import_source': 'broker_csv_import',
                'import_batch_id': self.batch_id,
                'skip_cash_validation': True,
                'skip_exchange_rate_conversion': True,
                'skip_fifo_validation': True
            })

        # Process BUY transactions (Stock purchase + commission)
        system_transactions.extend(self.process_buy_transactions(
            by_type['Stock purchase'],
            by_type['commission']
        ))

        # Process SELL transactions (Stock sale + close trade merger)
        system_transactions.extend(self.process_sell_transactions(
            by_type['Stock sale'],
            by_type['close trade']
        ))

        # Process dividends, taxes, fees (simple mapping)
        for txn in (by_type['DIVIDENT'] + by_type['Withholding Tax'] +
                    by_type['Sec Fee'] + by_type['Free-funds Interest'] +
                    by_type['Free-funds Interest Tax']):
            system_type = self.BROKER_TO_SYSTEM_TYPE[txn.broker_type]

            # Handle amount sign based on transaction type
            if system_type in ['DIVIDEND', 'INTEREST']:
                # Dividends and interest should always be positive (money coming in)
                amount = abs(txn.amount)
            elif system_type == 'TAX':
                # TAX should always be negative (money leaving), but tax refunds come as positive
                # If amount is positive, it's a refund - make it negative for consistency
                amount = -abs(txn.amount)
            else:
                # FEE and others - keep original sign
                amount = txn.amount

            system_transactions.append({
                'transaction_type': system_type,
                'ticker': txn.ticker if txn.ticker else '',
                'quantity': None,
                'price': None,
                'total_amount': amount,
                'transaction_date': txn.date,
                'transaction_currency': 'CZK',
                'notes': txn.comment,
                'broker_transaction_id': txn.broker_id,
                'import_source': 'broker_csv_import',
                'import_batch_id': self.batch_id,
                'skip_cash_validation': True,
                'skip_exchange_rate_conversion': True
            })

        # Process stock splits
        system_transactions.extend(self.process_split_transactions(by_type['fractional shares']))

        return system_transactions

    def process_buy_transactions(
        self,
        stock_purchases: List[BrokerTransaction],
        commissions: List[BrokerTransaction]
    ) -> List[Dict]:
        """Process BUY transactions with quantity/price extraction"""
        buy_transactions = []

        # Group stock purchases by (ticker, timestamp)
        purchases_by_key = defaultdict(list)
        for purchase in stock_purchases:
            key = (purchase.ticker, purchase.timestamp)
            purchases_by_key[key].append(purchase)

        # Find matching commission for each group
        for (ticker, timestamp), purchase_rows in purchases_by_key.items():
            # Find commission with same ticker and timestamp
            matching_commission = None
            for comm in commissions:
                if comm.ticker == ticker and comm.timestamp == timestamp:
                    matching_commission = comm
                    break

            if not matching_commission:
                print(f"  Warning: No commission found for {ticker} at {timestamp}")
                continue

            # Parse quantity and USD price from commission
            parsed = self.commission_parser.parse_comment(matching_commission.comment)
            if not parsed:
                print(f"  Warning: Could not parse commission: {matching_commission.comment}")
                continue

            total_quantity, usd_price = parsed

            # Convert USD price to CZK
            czk_price = self.rate_converter.convert_usd_to_czk(usd_price, purchase_rows[0].date)

            # Split quantity proportionally across rows
            quantities = self.multi_row_handler.split_quantity_proportionally(
                purchase_rows, total_quantity
            )

            # Create BUY transaction for each row
            for purchase_row, quantity in zip(purchase_rows, quantities):
                buy_transactions.append({
                    'transaction_type': 'BUY',
                    'ticker': ticker,
                    'quantity': quantity,
                    'price': czk_price,
                    'total_amount': abs(purchase_row.amount),
                    'transaction_date': purchase_row.date,
                    'transaction_currency': 'CZK',
                    'notes': f"Imported from broker. {purchase_row.comment}",
                    'broker_transaction_id': purchase_row.broker_id,
                    'import_source': 'broker_csv_import',
                    'import_batch_id': self.batch_id,
                    'skip_cash_validation': True,
                'skip_exchange_rate_conversion': True,
                    'skip_price_validation': True
                })

            # Create FEE transaction for commission (separate per user request)
            buy_transactions.append({
                'transaction_type': 'FEE',
                'ticker': ticker,
                'quantity': None,
                'price': None,
                'total_amount': matching_commission.amount,  # Already negative
                'transaction_date': matching_commission.date,
                'transaction_currency': 'CZK',
                'notes': f"Trading commission. {matching_commission.comment}",
                'broker_transaction_id': matching_commission.broker_id,
                'import_source': 'broker_csv_import',
                'import_batch_id': self.batch_id,
                'skip_cash_validation': True,
                'skip_exchange_rate_conversion': True
            })

        return buy_transactions

    def process_sell_transactions(
        self,
        stock_sales: List[BrokerTransaction],
        close_trades: List[BrokerTransaction]
    ) -> List[Dict]:
        """Process SELL transactions by merging Stock sale + close trade"""
        sell_transactions = []

        # Group by (ticker, timestamp)
        sales_by_key = defaultdict(lambda: {'stock_sale': [], 'close_trade': []})

        for sale in stock_sales:
            key = (sale.ticker, sale.timestamp)
            sales_by_key[key]['stock_sale'].append(sale)

        for trade in close_trades:
            key = (trade.ticker, trade.timestamp)
            sales_by_key[key]['close_trade'].append(trade)

        # Merge each group
        for (ticker, timestamp), data in sales_by_key.items():
            if not data['stock_sale'] or not data['close_trade']:
                print(f"  Warning: Incomplete SELL pair for {ticker} at {timestamp}")
                continue

            # Sum amounts (both stock sale and P&L)
            stock_sale_amount = sum(sale.amount for sale in data['stock_sale'])
            close_trade_amount = sum(trade.amount for trade in data['close_trade'])
            total_proceeds = stock_sale_amount + close_trade_amount

            # Calculate quantity using FIFO
            sell_date = data['stock_sale'][0].date
            quantity = self.fifo_calculator.calculate_sell_quantity(ticker, sell_date, abs(total_proceeds))

            if quantity <= 0:
                print(f"  Warning: Could not calculate quantity for SELL {ticker} at {sell_date}")
                quantity = 1.0  # Fallback to avoid division by zero

            # Calculate price per share
            price = abs(total_proceeds) / quantity if quantity > 0 else 0

            sell_transactions.append({
                'transaction_type': 'SELL',
                'ticker': ticker,
                'quantity': quantity,
                'price': price,
                'total_amount': abs(total_proceeds),
                'transaction_date': sell_date,
                'transaction_currency': 'CZK',
                'notes': f"Merged sale. P&L: {close_trade_amount:.2f} CZK. {data['stock_sale'][0].comment}",
                'broker_transaction_id': data['stock_sale'][0].broker_id,
                'import_source': 'broker_csv_import',
                'import_batch_id': self.batch_id,
                'skip_cash_validation': True,
                'skip_exchange_rate_conversion': True,
                'skip_fifo_validation': True
            })

        return sell_transactions

    def process_split_transactions(self, splits: List[BrokerTransaction]) -> List[Dict]:
        """Process stock split transactions"""
        split_transactions = []

        for split in splits:
            parsed = self.split_parser.parse_split(split.comment)
            if not parsed:
                print(f"  Warning: Could not parse split: {split.comment}")
                continue

            old_shares, new_shares = parsed
            split_ratio = new_shares / old_shares

            split_transactions.append({
                'transaction_type': 'SPLIT',
                'ticker': split.ticker,
                'quantity': split.amount,  # Cash adjustment for fractional shares
                'price': 0,
                'total_amount': split.amount,
                'transaction_date': split.date,
                'transaction_currency': 'CZK',
                'notes': f"Stock split {old_shares}:{new_shares} (ratio {split_ratio}). {split.comment}",
                'broker_transaction_id': split.broker_id,
                'import_source': 'broker_csv_import',
                'import_batch_id': self.batch_id,
                'skip_cash_validation': True,
                'skip_exchange_rate_conversion': True
            })

        return split_transactions

    def import_transactions(self, transactions: List[Dict]):
        """Import transactions into database"""
        for i, txn_data in enumerate(transactions, 1):
            try:
                # Create transaction
                txn_create = TransactionCreate(**txn_data)
                result = TransactionService.create_transaction(self.db, txn_create)

                self.stats['imported'] += 1
                self.stats['by_type'][txn_data['transaction_type']] += 1

                if i % 50 == 0:
                    print(f"  Imported {i}/{len(transactions)} transactions...")

            except Exception as e:
                self.stats['errors'] += 1
                error_msg = f"Failed to import {txn_data['transaction_type']} on {txn_data['transaction_date']}: {str(e)}"
                self.errors.append(error_msg)
                print(f"  [ERROR] {error_msg}")

    def print_summary(self):
        """Print import summary"""
        print("\n" + "=" * 70)
        print("IMPORT SUMMARY")
        print("=" * 70)
        print(f"Parsed from CSV:  {self.stats['parsed']}")
        print(f"Imported:         {self.stats['imported']}")
        print(f"Errors:           {self.stats['errors']}")
        print()
        print("By Type:")
        for txn_type, count in sorted(self.stats['by_type'].items()):
            print(f"  {txn_type:12} {count:4}")

        if self.errors:
            print(f"\n{len(self.errors)} Errors:")
            for error in self.errors[:10]:
                print(f"  - {error}")
            if len(self.errors) > 10:
                print(f"  ... and {len(self.errors) - 10} more")

        print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description='Import broker transactions from CSV')
    parser.add_argument('csv_file', nargs='?', help='Path to CSV file')
    parser.add_argument('--dry-run', action='store_true', help='Dry run without importing')
    parser.add_argument('--rollback', help='Rollback import by batch ID')

    args = parser.parse_args()

    if args.rollback:
        # Rollback functionality
        db = SessionLocal()
        try:
            deleted = db.query(Transaction).filter(
                Transaction.import_batch_id == args.rollback
            ).delete()
            db.commit()
            print(f"[OK] Rolled back {deleted} transactions from batch {args.rollback}")
        except Exception as e:
            db.rollback()
            print(f"[ERROR] Rollback failed: {e}")
        finally:
            db.close()
        return

    if not args.csv_file:
        parser.print_help()
        return

    # Run import
    importer = BrokerTransactionImporter(args.csv_file, dry_run=args.dry_run)
    success = importer.run()

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
