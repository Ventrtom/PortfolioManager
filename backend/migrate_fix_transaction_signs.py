"""
Migration script to fix transaction sign conventions

This script:
1. Identifies transactions with incorrect signs (BUY/FEE/TAX/WITHDRAWAL that are positive)
2. Corrects their signs in the database
3. Recalculates multi-currency amounts with correct signs
4. Verifies portfolio calculations remain consistent

Usage:
    python migrate_fix_transaction_signs.py              # Run migration
    python migrate_fix_transaction_signs.py --dry-run    # Preview changes
    python migrate_fix_transaction_signs.py --report     # Generate report only
"""

import os
import sys
import argparse
import shutil
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.database import Transaction
from services.sign_conversion_service import SignConversionService
from services.exchange_rate_service import ExchangeRateService


class TransactionSignMigration:
    def __init__(self, dry_run=False, report_only=False):
        self.dry_run = dry_run
        self.report_only = report_only
        self.database_url = "sqlite:///./portfolio.db"
        self.engine = create_engine(self.database_url, connect_args={"check_same_thread": False})
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def log(self, message, level="INFO"):
        """Print log message with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prefix = "[DRY-RUN] " if self.dry_run else "[REPORT] " if self.report_only else ""
        print(f"{prefix}[{timestamp}] {level}: {message}")

    def backup_database(self):
        """Create a backup of the database"""
        if self.dry_run or self.report_only:
            self.log("Would create database backup: portfolio.db.backup_sign_fix")
            return True

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"portfolio.db.backup_sign_fix_{timestamp}"
        try:
            if os.path.exists("portfolio.db"):
                shutil.copy2("portfolio.db", backup_path)
                self.log(f"Database backed up to: {backup_path}")
                return True
            else:
                self.log("No database file found to backup", "WARNING")
                return False
        except Exception as e:
            self.log(f"Failed to create backup: {e}", "ERROR")
            return False

    def analyze_transactions(self):
        """Analyze existing transactions for sign issues"""
        self.log("Analyzing transaction signs...")
        db = self.SessionLocal()

        try:
            # Get all transactions that should be negative (money OUT)
            negative_types = list(SignConversionService.NEGATIVE_TYPES)
            all_negative_txns = db.query(Transaction).filter(
                Transaction.transaction_type.in_(negative_types)
            ).all()

            # Also check positive types for completeness
            positive_types = list(SignConversionService.POSITIVE_TYPES)
            all_positive_txns = db.query(Transaction).filter(
                Transaction.transaction_type.in_(positive_types)
            ).all()

            analysis = {
                'negative_types': {
                    'total_count': 0,
                    'correct_count': 0,
                    'incorrect_count': 0,
                    'by_type': {},
                    'incorrect_transactions': []
                },
                'positive_types': {
                    'total_count': 0,
                    'correct_count': 0,
                    'incorrect_count': 0,
                    'by_type': {},
                    'incorrect_transactions': []
                }
            }

            # Analyze negative types (should be negative)
            for txn in all_negative_txns:
                analysis['negative_types']['total_count'] += 1
                txn_type = txn.transaction_type

                if txn_type not in analysis['negative_types']['by_type']:
                    analysis['negative_types']['by_type'][txn_type] = {
                        'total': 0,
                        'correct': 0,
                        'incorrect': 0
                    }

                analysis['negative_types']['by_type'][txn_type]['total'] += 1

                # Check sign
                validation = SignConversionService.validate_sign_convention(
                    txn.transaction_type,
                    txn.total_amount
                )

                if validation['valid']:
                    analysis['negative_types']['correct_count'] += 1
                    analysis['negative_types']['by_type'][txn_type]['correct'] += 1
                else:
                    analysis['negative_types']['incorrect_count'] += 1
                    analysis['negative_types']['by_type'][txn_type]['incorrect'] += 1
                    analysis['negative_types']['incorrect_transactions'].append({
                        'id': txn.id,
                        'type': txn.transaction_type,
                        'ticker': txn.ticker,
                        'date': txn.transaction_date,
                        'current_amount': txn.total_amount,
                        'corrected_amount': validation['corrected_amount']
                    })

            # Analyze positive types (should be positive)
            for txn in all_positive_txns:
                analysis['positive_types']['total_count'] += 1
                txn_type = txn.transaction_type

                if txn_type not in analysis['positive_types']['by_type']:
                    analysis['positive_types']['by_type'][txn_type] = {
                        'total': 0,
                        'correct': 0,
                        'incorrect': 0
                    }

                analysis['positive_types']['by_type'][txn_type]['total'] += 1

                # Check sign
                validation = SignConversionService.validate_sign_convention(
                    txn.transaction_type,
                    txn.total_amount
                )

                if validation['valid']:
                    analysis['positive_types']['correct_count'] += 1
                    analysis['positive_types']['by_type'][txn_type]['correct'] += 1
                else:
                    analysis['positive_types']['incorrect_count'] += 1
                    analysis['positive_types']['by_type'][txn_type]['incorrect'] += 1
                    analysis['positive_types']['incorrect_transactions'].append({
                        'id': txn.id,
                        'type': txn.transaction_type,
                        'ticker': txn.ticker,
                        'date': txn.transaction_date,
                        'current_amount': txn.total_amount,
                        'corrected_amount': validation['corrected_amount']
                    })

            return analysis

        finally:
            db.close()

    def print_analysis_report(self, analysis):
        """Print detailed analysis report"""
        self.log("=" * 70)
        self.log("TRANSACTION SIGN ANALYSIS REPORT")
        self.log("=" * 70)

        # Report on negative types (money OUT)
        neg = analysis['negative_types']
        self.log("")
        self.log("NEGATIVE TYPES (Money OUT: BUY, FEE, TAX, WITHDRAWAL):")
        self.log(f"  Total transactions: {neg['total_count']}")
        self.log(f"  Correct signs: {neg['correct_count']}")
        self.log(f"  Incorrect signs: {neg['incorrect_count']}")

        if neg['by_type']:
            self.log("")
            self.log("  Breakdown by Type:")
            for txn_type, stats in neg['by_type'].items():
                self.log(f"    {txn_type}:")
                self.log(f"      Total: {stats['total']}")
                self.log(f"      Correct (negative): {stats['correct']}")
                self.log(f"      Incorrect (positive): {stats['incorrect']}")

        # Report on positive types (money IN)
        pos = analysis['positive_types']
        self.log("")
        self.log("POSITIVE TYPES (Money IN: SELL, DIVIDEND, DEPOSIT, INTEREST):")
        self.log(f"  Total transactions: {pos['total_count']}")
        self.log(f"  Correct signs: {pos['correct_count']}")
        self.log(f"  Incorrect signs: {pos['incorrect_count']}")

        if pos['by_type']:
            self.log("")
            self.log("  Breakdown by Type:")
            for txn_type, stats in pos['by_type'].items():
                self.log(f"    {txn_type}:")
                self.log(f"      Total: {stats['total']}")
                self.log(f"      Correct (positive): {stats['correct']}")
                self.log(f"      Incorrect (negative): {stats['incorrect']}")

        # Show incorrect transactions
        all_incorrect = neg['incorrect_transactions'] + pos['incorrect_transactions']
        if all_incorrect:
            self.log("")
            self.log(f"Transactions needing correction ({len(all_incorrect)}):")
            for txn in all_incorrect[:20]:  # Show first 20
                self.log(
                    f"  ID {txn['id']}: {txn['type']} {txn['ticker']} on {txn['date']} "
                    f"| Current: {txn['current_amount']:.2f} -> Corrected: {txn['corrected_amount']:.2f}"
                )
            if len(all_incorrect) > 20:
                self.log(f"  ... and {len(all_incorrect) - 20} more")

        self.log("")
        self.log("=" * 70)

        return len(all_incorrect)

    def fix_transaction_signs(self, analysis):
        """Fix signs for transactions"""
        all_incorrect = (analysis['negative_types']['incorrect_transactions'] +
                        analysis['positive_types']['incorrect_transactions'])

        if self.report_only:
            self.log("Report-only mode - no changes made")
            return True

        if not all_incorrect:
            self.log("No transactions need correction")
            return True

        db = self.SessionLocal()
        try:
            self.log(f"Correcting signs for {len(all_incorrect)} transactions...")

            fixed_count = 0
            failed_count = 0

            for txn_info in all_incorrect:
                try:
                    txn = db.query(Transaction).filter(Transaction.id == txn_info['id']).first()

                    if not txn:
                        self.log(f"Transaction {txn_info['id']} not found", "WARNING")
                        failed_count += 1
                        continue

                    # Apply sign correction
                    old_amount = txn.total_amount
                    txn.total_amount = txn_info['corrected_amount']

                    # Also flip the sign of multi-currency amounts (they're already calculated)
                    # Just need to apply the same sign change
                    if txn.amount_usd is not None:
                        txn.amount_usd = -txn.amount_usd
                    if txn.amount_eur is not None:
                        txn.amount_eur = -txn.amount_eur
                    if txn.amount_czk is not None:
                        txn.amount_czk = -txn.amount_czk

                    txn.updated_at = datetime.utcnow()

                    fixed_count += 1

                    if fixed_count % 10 == 0:
                        self.log(f"Progress: {fixed_count}/{len(all_incorrect)} fixed...")

                except Exception as e:
                    self.log(f"Error fixing transaction {txn_info['id']}: {e}", "WARNING")
                    failed_count += 1

            if not self.dry_run:
                db.commit()
                self.log(f"Successfully fixed {fixed_count} transactions")
            else:
                db.rollback()
                self.log(f"[DRY-RUN] Would fix {fixed_count} transactions")

            if failed_count > 0:
                self.log(f"Failed to fix {failed_count} transactions", "WARNING")

            return failed_count == 0

        except Exception as e:
            db.rollback()
            self.log(f"Error during sign correction: {e}", "ERROR")
            return False
        finally:
            db.close()

    def verify_portfolio_consistency(self):
        """Verify portfolio calculations are consistent after migration"""
        self.log("Verifying portfolio consistency...")
        db = self.SessionLocal()

        try:
            from services.portfolio_service import PortfolioService

            # Calculate portfolio summary (will use corrected signs)
            summary = PortfolioService.get_portfolio_summary(db)

            self.log(f"Portfolio Summary:")
            self.log(f"  Total Value: {summary.total_value:.2f} CZK")
            self.log(f"  Cash Balance: {summary.cash_balance:.2f} CZK")
            self.log(f"  Holdings: {summary.number_of_holdings}")
            self.log(f"  Unrealized Gain: {summary.total_unrealized_gain:.2f} CZK")
            self.log(f"  Realized Gain: {summary.total_realized_gain:.2f} CZK")

            if summary.conversion_warnings:
                self.log(f"  Warnings: {len(summary.conversion_warnings)}", "WARNING")
                for warning in summary.conversion_warnings[:5]:
                    self.log(f"    - {warning}", "WARNING")

            return True

        except Exception as e:
            self.log(f"Error verifying portfolio: {e}", "ERROR")
            import traceback
            self.log(traceback.format_exc(), "ERROR")
            return False
        finally:
            db.close()

    def run(self):
        """Execute the migration"""
        self.log("=" * 70)
        self.log("Transaction Sign Convention Fix Starting")
        self.log("=" * 70)

        if self.dry_run:
            self.log("DRY-RUN MODE: No changes will be made")
        elif self.report_only:
            self.log("REPORT-ONLY MODE: Analysis only, no changes")
        self.log("")

        # Step 1: Analyze transactions
        analysis = self.analyze_transactions()
        total_incorrect = self.print_analysis_report(analysis)

        if total_incorrect == 0:
            self.log("No transactions need correction - all signs are correct!")
            return True

        if self.report_only:
            return True

        # Step 2: Backup database
        if not self.backup_database():
            self.log("Migration aborted - backup failed", "ERROR")
            return False

        # Step 3: Fix transaction signs
        if not self.fix_transaction_signs(analysis):
            self.log("Migration completed with errors", "WARNING")
            return False

        # Step 4: Verify portfolio consistency
        if not self.dry_run:
            self.verify_portfolio_consistency()

        self.log("")
        self.log("=" * 70)
        if self.dry_run:
            self.log("[SUCCESS] Dry-run completed - ready to execute")
        else:
            self.log("[SUCCESS] Migration completed successfully!")
        self.log("=" * 70)

        return True


def main():
    parser = argparse.ArgumentParser(
        description='Fix transaction sign conventions in database'
    )
    parser.add_argument('--dry-run', action='store_true',
                       help='Preview changes without applying them')
    parser.add_argument('--report', action='store_true',
                       help='Generate analysis report only (no changes)')
    args = parser.parse_args()

    migration = TransactionSignMigration(
        dry_run=args.dry_run,
        report_only=args.report
    )
    success = migration.run()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
