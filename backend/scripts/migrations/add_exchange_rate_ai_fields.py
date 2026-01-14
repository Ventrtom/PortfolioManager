"""
Migration: Add AI tracking fields to ExchangeRate table

Adds the following columns:
- confidence: str (high/medium/low)
- ai_used: bool
- ai_sources: JSON
- needs_manual_review: bool
- manual_review_reason: str

Run this script to update an existing database with these new columns.
"""

import sqlite3
import sys
import os
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from models.database import DATABASE_URL


def add_ai_fields_to_exchange_rates():
    """Add AI tracking fields to exchange_rates table"""

    # Extract database path from DATABASE_URL
    if DATABASE_URL.startswith("sqlite:///"):
        db_path = DATABASE_URL.replace("sqlite:///", "")
        # Handle relative paths
        if db_path.startswith("./"):
            db_path = os.path.join(backend_path, db_path[2:])
    else:
        print("This migration script only supports SQLite databases")
        print(f"Current DATABASE_URL: {DATABASE_URL}")
        print("For PostgreSQL or other databases, you'll need to modify this script")
        return False

    if not os.path.exists(db_path):
        print(f"Database not found at: {db_path}")
        return False

    print(f"Connecting to database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(exchange_rates)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        columns_to_add = {
            'confidence': 'TEXT',
            'ai_used': 'INTEGER DEFAULT 0',  # SQLite uses INTEGER for BOOLEAN
            'ai_sources': 'TEXT',  # SQLite stores JSON as TEXT
            'needs_manual_review': 'INTEGER DEFAULT 0',
            'manual_review_reason': 'TEXT'
        }

        added_count = 0
        skipped_count = 0

        for column_name, column_type in columns_to_add.items():
            if column_name in existing_columns:
                print(f"  Column '{column_name}' already exists, skipping")
                skipped_count += 1
                continue

            print(f"  Adding column '{column_name}' ({column_type})")
            cursor.execute(f"ALTER TABLE exchange_rates ADD COLUMN {column_name} {column_type}")
            added_count += 1

        conn.commit()

        print(f"\nMigration complete!")
        print(f"  Added: {added_count} columns")
        print(f"  Skipped (already exist): {skipped_count} columns")

        # Verify the changes
        cursor.execute("PRAGMA table_info(exchange_rates)")
        columns = cursor.fetchall()
        print(f"\nExchangeRate table now has {len(columns)} columns:")
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")

        return True

    except sqlite3.Error as e:
        print(f"Error during migration: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()


def main():
    print("=" * 60)
    print("ExchangeRate AI Fields Migration")
    print("=" * 60)
    print()

    success = add_ai_fields_to_exchange_rates()

    if success:
        print("\n✓ Migration successful!")
        print("\nThe ExchangeRate table now supports AI-powered rate resolution.")
        print("You can now use the ExchangeRateAgent for fallback rate resolution.")
    else:
        print("\n✗ Migration failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
