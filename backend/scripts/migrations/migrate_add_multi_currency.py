"""
Migration script to add multi-currency support to transactions

This script:
1. Adds new currency columns to transactions and transaction_history tables
2. Creates the exchange_rates table
3. Backfills existing transactions with currency data
4. Fetches historical exchange rates for all transaction dates
5. Calculates and populates amount_usd, amount_eur, amount_czk for each transaction

Usage:
    python migrate_add_multi_currency.py              # Run migration
    python migrate_add_multi_currency.py --dry-run    # Preview changes without applying
"""

import os
import sys
import argparse
from datetime import datetime
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add parent directory to path to import models
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.database import Base, Transaction, ExchangeRate, TransactionHistory
from services.exchange_rate_service import ExchangeRateService


class MultiCurrencyMigration:
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.database_url = "sqlite:///./portfolio.db"
        self.engine = create_engine(self.database_url, connect_args={"check_same_thread": False})
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def log(self, message, level="INFO"):
        """Print log message with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prefix = "[DRY-RUN] " if self.dry_run else ""
        print(f"{prefix}[{timestamp}] {level}: {message}")

    def check_column_exists(self, table_name, column_name):
        """Check if a column exists in a table"""
        inspector = inspect(self.engine)
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns

    def backup_database(self):
        """Create a backup of the database"""
        if self.dry_run:
            self.log("Would create database backup: portfolio.db.backup")
            return True

        import shutil
        backup_path = "portfolio.db.backup"
        try:
            if os.path.exists("portfolio.db"):
                shutil.copy2("portfolio.db", backup_path)
                self.log(f"Database backed up to: {backup_path}")
                return True
            else:
                self.log("No database file found to backup", "WARNING")
                return True
        except Exception as e:
            self.log(f"Failed to create backup: {e}", "ERROR")
            return False

    def add_columns_to_transactions(self):
        """Add currency columns to transactions table"""
        self.log("Adding currency columns to transactions table...")

        with self.engine.connect() as conn:
            # Check if columns already exist
            if self.check_column_exists('transactions', 'transaction_currency'):
                self.log("Currency columns already exist in transactions table", "WARNING")
                return True

            if self.dry_run:
                self.log("Would add columns: transaction_currency, amount_usd, amount_eur, amount_czk")
                return True

            try:
                # SQLite doesn't support adding multiple columns at once
                conn.execute(text("ALTER TABLE transactions ADD COLUMN transaction_currency VARCHAR DEFAULT 'CZK'"))
                conn.execute(text("ALTER TABLE transactions ADD COLUMN amount_usd FLOAT"))
                conn.execute(text("ALTER TABLE transactions ADD COLUMN amount_eur FLOAT"))
                conn.execute(text("ALTER TABLE transactions ADD COLUMN amount_czk FLOAT"))
                conn.commit()
                self.log("Successfully added columns to transactions table")
                return True
            except Exception as e:
                self.log(f"Error adding columns to transactions: {e}", "ERROR")
                return False

    def add_columns_to_transaction_history(self):
        """Add currency columns to transaction_history table"""
        self.log("Adding currency columns to transaction_history table...")

        with self.engine.connect() as conn:
            # Check if columns already exist
            if self.check_column_exists('transaction_history', 'transaction_currency'):
                self.log("Currency columns already exist in transaction_history table", "WARNING")
                return True

            if self.dry_run:
                self.log("Would add columns: transaction_currency, amount_usd, amount_eur, amount_czk")
                return True

            try:
                conn.execute(text("ALTER TABLE transaction_history ADD COLUMN transaction_currency VARCHAR"))
                conn.execute(text("ALTER TABLE transaction_history ADD COLUMN amount_usd FLOAT"))
                conn.execute(text("ALTER TABLE transaction_history ADD COLUMN amount_eur FLOAT"))
                conn.execute(text("ALTER TABLE transaction_history ADD COLUMN amount_czk FLOAT"))
                conn.commit()
                self.log("Successfully added columns to transaction_history table")
                return True
            except Exception as e:
                self.log(f"Error adding columns to transaction_history: {e}", "ERROR")
                return False

    def create_exchange_rates_table(self):
        """Create the exchange_rates table"""
        self.log("Creating exchange_rates table...")

        inspector = inspect(self.engine)
        if 'exchange_rates' in inspector.get_table_names():
            self.log("exchange_rates table already exists", "WARNING")
            return True

        if self.dry_run:
            self.log("Would create exchange_rates table")
            return True

        try:
            # Create only the ExchangeRate table
            ExchangeRate.__table__.create(self.engine, checkfirst=True)
            self.log("Successfully created exchange_rates table")
            return True
        except Exception as e:
            self.log(f"Error creating exchange_rates table: {e}", "ERROR")
            return False

    def get_transaction_summary(self):
        """Get summary of existing transactions"""
        with self.engine.connect() as conn:
            try:
                # Use raw SQL to avoid ORM column mismatch issues
                result = conn.execute(text("SELECT COUNT(*) FROM transactions"))
                count = result.scalar()

                result = conn.execute(text("SELECT COUNT(DISTINCT transaction_date) FROM transactions"))
                date_count = result.scalar()

                result = conn.execute(text("SELECT DISTINCT transaction_date FROM transactions ORDER BY transaction_date"))
                dates = [row[0] for row in result]

                self.log(f"Found {count} existing transactions")
                self.log(f"Found {date_count} unique transaction dates")

                return count, date_count, dates
            except Exception as e:
                self.log(f"Error getting transaction summary: {e}", "ERROR")
                raise

    def backfill_transaction_currencies(self):
        """Set transaction_currency to USD for all existing transactions"""
        # In dry-run mode, columns don't exist yet
        if self.dry_run:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM transactions"))
                count = result.scalar()
                self.log(f"Would set transaction_currency='USD' for {count} transactions")
                return True

        # After migration, use ORM
        db = self.SessionLocal()
        try:
            transactions = db.query(Transaction).filter(
                Transaction.transaction_currency == None
            ).all()

            if not transactions:
                self.log("No transactions need currency backfill")
                return True

            self.log(f"Backfilling transaction_currency='USD' for {len(transactions)} transactions...")

            for transaction in transactions:
                transaction.transaction_currency = 'USD'

            db.commit()
            self.log(f"Successfully backfilled {len(transactions)} transactions")
            return True

        except Exception as e:
            db.rollback()
            self.log(f"Error backfilling transaction currencies: {e}", "ERROR")
            return False
        finally:
            db.close()

    def fetch_and_calculate_currency_amounts(self):
        """Fetch exchange rates and calculate currency amounts for all transactions"""
        # In dry-run mode, columns don't exist yet
        if self.dry_run:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM transactions"))
                count = result.scalar()
                result = conn.execute(text("SELECT COUNT(DISTINCT transaction_date) FROM transactions"))
                date_count = result.scalar()
                self.log(f"Would fetch rates for {date_count} dates")
                self.log(f"Would calculate currency amounts for {count} transactions")
                return True

        # After migration, use ORM
        db = self.SessionLocal()
        try:
            # Get all transactions that need currency amounts
            transactions = db.query(Transaction).filter(
                (Transaction.amount_usd == None) |
                (Transaction.amount_eur == None) |
                (Transaction.amount_czk == None)
            ).all()

            if not transactions:
                self.log("No transactions need currency amount calculation")
                return True

            self.log(f"Calculating currency amounts for {len(transactions)} transactions...")

            # Get unique dates for batch fetching
            unique_dates = list(set(t.transaction_date for t in transactions))
            self.log(f"Fetching exchange rates for {len(unique_dates)} unique dates...")

            # Batch fetch all needed rates
            try:
                success_count = ExchangeRateService.batch_fetch_rates(unique_dates, db)
                self.log(f"Successfully fetched rates for {success_count}/{len(unique_dates)} dates")
            except Exception as e:
                self.log(f"Error during batch rate fetch: {e}", "WARNING")
                self.log("Will attempt individual transaction updates with fallbacks...")

            # Calculate currency amounts for each transaction
            updated_count = 0
            failed_count = 0

            for i, transaction in enumerate(transactions, 1):
                try:
                    # Ensure transaction_currency is set
                    if not transaction.transaction_currency:
                        transaction.transaction_currency = 'USD'

                    # Calculate all currency amounts
                    currency_amounts = ExchangeRateService.get_all_currency_amounts(
                        amount=transaction.total_amount,
                        transaction_currency=transaction.transaction_currency,
                        rate_date=transaction.transaction_date,
                        db=db
                    )

                    transaction.amount_usd = currency_amounts['usd']
                    transaction.amount_eur = currency_amounts['eur']
                    transaction.amount_czk = currency_amounts['czk']

                    updated_count += 1

                    if i % 10 == 0:
                        self.log(f"Progress: {i}/{len(transactions)} transactions processed...")

                except Exception as e:
                    failed_count += 1
                    self.log(f"Error calculating amounts for transaction {transaction.id} ({transaction.transaction_date}): {e}", "WARNING")
                    continue

            # Commit all updates
            db.commit()
            self.log(f"Successfully updated {updated_count} transactions")

            if failed_count > 0:
                self.log(f"Failed to update {failed_count} transactions", "WARNING")

            return failed_count == 0

        except Exception as e:
            db.rollback()
            self.log(f"Error calculating currency amounts: {e}", "ERROR")
            return False
        finally:
            db.close()

    def verify_migration(self):
        """Verify that migration was successful"""
        self.log("Verifying migration...")
        db = self.SessionLocal()
        try:
            # Check that all transactions have currency data
            total = db.query(Transaction).count()
            with_currency = db.query(Transaction).filter(
                Transaction.transaction_currency != None,
                Transaction.amount_usd != None,
                Transaction.amount_eur != None,
                Transaction.amount_czk != None
            ).count()

            self.log(f"Transactions with complete currency data: {with_currency}/{total}")

            if with_currency == total:
                self.log("[SUCCESS] Migration verified successfully!")
                return True
            else:
                self.log(f"[WARNING] {total - with_currency} transactions missing currency data", "WARNING")
                return False

        finally:
            db.close()

    def run(self):
        """Execute the full migration"""
        self.log("=" * 60)
        self.log("Multi-Currency Migration Starting")
        self.log("=" * 60)

        if self.dry_run:
            self.log("DRY-RUN MODE: No changes will be made to the database")
            self.log("")

        # Step 1: Backup database
        if not self.backup_database():
            self.log("Migration aborted due to backup failure", "ERROR")
            return False

        # Step 2: Get transaction summary
        try:
            count, date_count, dates = self.get_transaction_summary()
        except Exception as e:
            self.log(f"Error getting transaction summary: {e}", "ERROR")
            return False

        # Step 3: Add columns to transactions table
        if not self.add_columns_to_transactions():
            self.log("Migration aborted due to schema update failure", "ERROR")
            return False

        # Step 4: Add columns to transaction_history table
        if not self.add_columns_to_transaction_history():
            self.log("Migration aborted due to schema update failure", "ERROR")
            return False

        # Step 5: Create exchange_rates table
        if not self.create_exchange_rates_table():
            self.log("Migration aborted due to table creation failure", "ERROR")
            return False

        # Step 6: Backfill transaction currencies
        if not self.backfill_transaction_currencies():
            self.log("Migration aborted due to backfill failure", "ERROR")
            return False

        # Step 7: Fetch rates and calculate currency amounts
        if not self.fetch_and_calculate_currency_amounts():
            self.log("Migration completed with warnings", "WARNING")

        # Step 8: Verify migration
        if not self.dry_run:
            if self.verify_migration():
                self.log("=" * 60)
                self.log("[SUCCESS] Migration completed successfully!")
                self.log("=" * 60)
                return True
            else:
                self.log("=" * 60)
                self.log("[WARNING] Migration completed with issues")
                self.log("=" * 60)
                return False
        else:
            self.log("=" * 60)
            self.log("DRY-RUN completed - no changes made")
            self.log("=" * 60)
            return True


def main():
    parser = argparse.ArgumentParser(description='Migrate database to support multi-currency transactions')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without applying them')
    args = parser.parse_args()

    migration = MultiCurrencyMigration(dry_run=args.dry_run)
    success = migration.run()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
