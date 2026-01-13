"""
Database Migration: Add Import Tracking Fields
Adds import_source, import_batch_id, and broker_transaction_id fields to transactions table
"""
import sqlite3
from datetime import datetime

DATABASE_PATH = './portfolio.db'

def migrate():
    """Add import tracking fields to transactions table"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    print(f"[{datetime.now()}] Starting migration: Add import tracking fields")

    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(transactions)")
        columns = [row[1] for row in cursor.fetchall()]

        # Add import_source column
        if 'import_source' not in columns:
            print("  Adding column: import_source")
            cursor.execute("ALTER TABLE transactions ADD COLUMN import_source TEXT")
        else:
            print("  Column import_source already exists, skipping")

        # Add import_batch_id column
        if 'import_batch_id' not in columns:
            print("  Adding column: import_batch_id")
            cursor.execute("ALTER TABLE transactions ADD COLUMN import_batch_id TEXT")
        else:
            print("  Column import_batch_id already exists, skipping")

        # Add broker_transaction_id column
        if 'broker_transaction_id' not in columns:
            print("  Adding column: broker_transaction_id")
            cursor.execute("ALTER TABLE transactions ADD COLUMN broker_transaction_id TEXT")
            # Create index for faster lookups
            print("  Creating index: idx_broker_transaction_id")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_broker_transaction_id ON transactions(broker_transaction_id)")
        else:
            print("  Column broker_transaction_id already exists, skipping")

        conn.commit()
        print(f"[{datetime.now()}] Migration completed successfully")
        return True

    except Exception as e:
        conn.rollback()
        print(f"[{datetime.now()}] Migration failed: {str(e)}")
        return False

    finally:
        conn.close()

def verify_migration():
    """Verify migration was successful"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("PRAGMA table_info(transactions)")
        columns = [row[1] for row in cursor.fetchall()]

        required_columns = ['import_source', 'import_batch_id', 'broker_transaction_id']
        missing = [col for col in required_columns if col not in columns]

        if missing:
            print(f"  ❌ Verification failed: Missing columns: {', '.join(missing)}")
            return False
        else:
            print(f"  ✅ Verification passed: All import tracking columns present")
            return True

    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 70)
    print("DATABASE MIGRATION: Add Import Tracking Fields")
    print("=" * 70)
    print(f"Database: {DATABASE_PATH}")
    print()

    success = migrate()

    if success:
        print()
        print("Verifying migration...")
        verify_migration()

    print()
    print("=" * 70)
