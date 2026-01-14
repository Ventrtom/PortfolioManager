"""
Migration script to add AI tracking fields to exchange_rates table

This script adds:
- confidence (String): 'high', 'medium', 'low'
- ai_used (Boolean): Whether AI was used to resolve this rate
- ai_sources (JSON): List of URLs for AI results
- needs_manual_review (Boolean): Whether this rate needs manual review
- manual_review_reason (String): Reason for manual review

Usage:
    python migrate_add_exchange_rate_ai_fields.py              # Run migration
    python migrate_add_exchange_rate_ai_fields.py --dry-run    # Preview changes without applying
"""

import os
import sys
import argparse
from datetime import datetime
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

# Add parent directories to path to import models
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, backend_dir)

from models.database import Base


class ExchangeRateAIFieldsMigration:
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
        try:
            columns = [col['name'] for col in inspector.get_columns(table_name)]
            return column_name in columns
        except Exception as e:
            self.log(f"Error checking column existence: {e}", "ERROR")
            return False

    def backup_database(self):
        """Create a backup of the database"""
        if self.dry_run:
            self.log("Would create database backup: portfolio.db.backup")
            return True

        import shutil
        timestamp_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"portfolio.db.backup_{timestamp_suffix}"
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

    def add_ai_fields_to_exchange_rates(self):
        """Add AI tracking columns to exchange_rates table"""
        self.log("Adding AI tracking columns to exchange_rates table...")

        # Check if table exists
        inspector = inspect(self.engine)
        if 'exchange_rates' not in inspector.get_table_names():
            self.log("exchange_rates table does not exist!", "ERROR")
            return False

        with self.engine.connect() as conn:
            fields_to_add = [
                ('confidence', 'VARCHAR'),
                ('ai_used', 'BOOLEAN', 0),  # Default False
                ('ai_sources', 'JSON'),
                ('needs_manual_review', 'BOOLEAN', 0),  # Default False
                ('manual_review_reason', 'VARCHAR')
            ]

            added_count = 0
            skipped_count = 0

            for field in fields_to_add:
                column_name = field[0]
                column_type = field[1]
                default_value = field[2] if len(field) > 2 else None

                # Check if column already exists
                if self.check_column_exists('exchange_rates', column_name):
                    self.log(f"Column '{column_name}' already exists, skipping", "WARNING")
                    skipped_count += 1
                    continue

                if self.dry_run:
                    default_clause = f" DEFAULT {default_value}" if default_value is not None else ""
                    self.log(f"Would add column: {column_name} {column_type}{default_clause}")
                    added_count += 1
                    continue

                try:
                    # Build ALTER TABLE statement
                    if default_value is not None:
                        sql = f"ALTER TABLE exchange_rates ADD COLUMN {column_name} {column_type} DEFAULT {default_value}"
                    else:
                        sql = f"ALTER TABLE exchange_rates ADD COLUMN {column_name} {column_type}"

                    conn.execute(text(sql))
                    conn.commit()
                    self.log(f"Successfully added column: {column_name}")
                    added_count += 1
                except Exception as e:
                    self.log(f"Error adding column '{column_name}': {e}", "ERROR")
                    return False

            if added_count > 0:
                self.log(f"Successfully added {added_count} new columns")
            if skipped_count > 0:
                self.log(f"Skipped {skipped_count} existing columns")

            return True

    def verify_migration(self):
        """Verify that migration was successful"""
        self.log("Verifying migration...")

        required_columns = ['confidence', 'ai_used', 'ai_sources', 'needs_manual_review', 'manual_review_reason']
        inspector = inspect(self.engine)

        try:
            existing_columns = [col['name'] for col in inspector.get_columns('exchange_rates')]

            missing_columns = [col for col in required_columns if col not in existing_columns]

            if not missing_columns:
                self.log("[SUCCESS] All required columns exist!")
                return True
            else:
                self.log(f"[WARNING] Missing columns: {', '.join(missing_columns)}", "WARNING")
                return False

        except Exception as e:
            self.log(f"Error during verification: {e}", "ERROR")
            return False

    def run(self):
        """Execute the full migration"""
        self.log("=" * 60)
        self.log("Exchange Rate AI Fields Migration Starting")
        self.log("=" * 60)

        if self.dry_run:
            self.log("DRY-RUN MODE: No changes will be made to the database")
            self.log("")

        # Step 1: Backup database
        if not self.backup_database():
            self.log("Migration aborted due to backup failure", "ERROR")
            return False

        # Step 2: Add AI fields to exchange_rates table
        if not self.add_ai_fields_to_exchange_rates():
            self.log("Migration aborted due to schema update failure", "ERROR")
            return False

        # Step 3: Verify migration
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
    parser = argparse.ArgumentParser(description='Add AI tracking fields to exchange_rates table')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without applying them')
    args = parser.parse_args()

    # Change to backend directory to ensure correct database path
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.chdir(backend_dir)
    print(f"Working directory: {os.getcwd()}")

    migration = ExchangeRateAIFieldsMigration(dry_run=args.dry_run)
    success = migration.run()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
