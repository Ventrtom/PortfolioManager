"""
Script to clear all data from the portfolio database

This script will:
1. Create a backup of the current database
2. Delete all transactions
3. Delete all audit logs
4. Delete all KPI snapshots
5. Verify the database is empty

Usage:
    python clear_all_data.py              # Clear all data (with backup)
    python clear_all_data.py --no-backup  # Clear without backup (dangerous!)
"""

import os
import sys
import argparse
import shutil
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.database import Transaction


class DataClearer:
    def __init__(self, create_backup=True):
        self.create_backup = create_backup
        self.database_url = "sqlite:///./portfolio.db"
        self.engine = create_engine(self.database_url, connect_args={"check_same_thread": False})
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def log(self, message, level="INFO"):
        """Print log message with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")

    def backup_database(self):
        """Create a backup of the database"""
        if not self.create_backup:
            self.log("Skipping backup as requested (--no-backup)", "WARNING")
            return True

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"portfolio.db.backup_before_clear_{timestamp}"
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

    def get_counts_before(self):
        """Get counts of all records before deletion"""
        db = self.SessionLocal()
        try:
            counts = {}

            # Count transactions
            counts['transactions'] = db.query(Transaction).count()

            # Count audit logs
            try:
                result = db.execute(text("SELECT COUNT(*) FROM audit_log"))
                counts['audit_logs'] = result.scalar()
            except:
                counts['audit_logs'] = 0

            # Count KPI snapshots
            try:
                result = db.execute(text("SELECT COUNT(*) FROM kpi_snapshots"))
                counts['kpi_snapshots'] = result.scalar()
            except:
                counts['kpi_snapshots'] = 0

            return counts
        finally:
            db.close()

    def clear_all_data(self):
        """Delete all data from the database"""
        db = self.SessionLocal()
        try:
            self.log("Starting data deletion...")

            # Delete all transactions
            transaction_count = db.query(Transaction).count()
            db.query(Transaction).delete()
            self.log(f"Deleted {transaction_count} transactions")

            # Delete all audit logs (if table exists)
            try:
                result = db.execute(text("DELETE FROM audit_log"))
                audit_count = result.rowcount
                self.log(f"Deleted {audit_count} audit log entries")
            except Exception as e:
                self.log(f"No audit_log table or already empty", "INFO")

            # Delete all KPI snapshots (if table exists)
            try:
                result = db.execute(text("DELETE FROM kpi_snapshots"))
                kpi_count = result.rowcount
                self.log(f"Deleted {kpi_count} KPI snapshots")
            except Exception as e:
                self.log(f"No kpi_snapshots table or already empty", "INFO")

            db.commit()
            self.log("All data deleted successfully")
            return True

        except Exception as e:
            db.rollback()
            self.log(f"Error during data deletion: {e}", "ERROR")
            return False
        finally:
            db.close()

    def verify_empty(self):
        """Verify database is empty"""
        db = self.SessionLocal()
        try:
            counts = {}

            # Check transactions
            counts['transactions'] = db.query(Transaction).count()

            # Check audit logs
            try:
                result = db.execute(text("SELECT COUNT(*) FROM audit_log"))
                counts['audit_logs'] = result.scalar()
            except:
                counts['audit_logs'] = 0

            # Check KPI snapshots
            try:
                result = db.execute(text("SELECT COUNT(*) FROM kpi_snapshots"))
                counts['kpi_snapshots'] = result.scalar()
            except:
                counts['kpi_snapshots'] = 0

            total = sum(counts.values())

            if total == 0:
                self.log("Database is empty - verified")
                return True
            else:
                self.log(f"Database still has data: {counts}", "WARNING")
                return False

        finally:
            db.close()

    def run(self):
        """Execute the data clearing process"""
        self.log("=" * 70)
        self.log("DATABASE CLEAR - START")
        self.log("=" * 70)
        self.log("")

        # Step 1: Show current counts
        self.log("Current database contents:")
        counts_before = self.get_counts_before()
        for table, count in counts_before.items():
            self.log(f"  {table}: {count}")

        total_records = sum(counts_before.values())
        if total_records == 0:
            self.log("")
            self.log("Database is already empty - nothing to clear")
            return True

        self.log("")
        self.log(f"Total records to delete: {total_records}")
        self.log("")

        # Step 2: Create backup
        if not self.backup_database():
            if self.create_backup:
                self.log("Aborting - backup failed", "ERROR")
                return False

        self.log("")

        # Step 3: Ask for confirmation
        print("=" * 70)
        print("WARNING: This will DELETE ALL DATA from the database!")
        print("=" * 70)
        if self.create_backup:
            print("A backup has been created, but this action cannot be undone easily.")
        else:
            print("NO BACKUP will be created! This is PERMANENT!")
        print("")
        response = input("Type 'DELETE ALL DATA' to confirm: ")

        if response != "DELETE ALL DATA":
            self.log("Operation cancelled by user")
            return False

        self.log("")

        # Step 4: Clear data
        if not self.clear_all_data():
            self.log("Data clearing failed", "ERROR")
            return False

        self.log("")

        # Step 5: Verify empty
        if not self.verify_empty():
            self.log("Verification failed - database may not be completely empty", "WARNING")
            return False

        self.log("")
        self.log("=" * 70)
        self.log("DATABASE CLEARED SUCCESSFULLY")
        self.log("=" * 70)
        self.log("")
        self.log("Your portfolio is now empty and ready for fresh data.")

        return True


def main():
    parser = argparse.ArgumentParser(
        description='Clear all data from the portfolio database'
    )
    parser.add_argument('--no-backup', action='store_true',
                       help='Skip database backup (DANGEROUS - not recommended)')
    args = parser.parse_args()

    clearer = DataClearer(create_backup=not args.no_backup)
    success = clearer.run()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
