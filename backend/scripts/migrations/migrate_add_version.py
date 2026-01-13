"""
Migration script to add 'version' column to existing transactions table
SQLite doesn't support ALTER TABLE ADD COLUMN with defaults easily,
so we'll create a new table and copy data over
"""
import sys
import io
from sqlalchemy import text
from models.database import engine, SessionLocal

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def migrate_add_version_column():
    """Add version column to transactions table"""
    print("=" * 60)
    print("Migration: Adding 'version' column to transactions table")
    print("=" * 60)

    db = SessionLocal()
    try:
        # Check if version column already exists
        print("\n[1] Checking if version column exists...")
        result = db.execute(text("PRAGMA table_info(transactions)"))
        columns = [row[1] for row in result]

        if 'version' in columns:
            print("✓ Version column already exists - no migration needed")
            return True

        print("   Version column not found - proceeding with migration")

        # SQLite migration: Create new table with version column
        print("\n[2] Creating temporary table with new schema...")
        db.execute(text("""
            CREATE TABLE transactions_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_type VARCHAR NOT NULL,
                ticker VARCHAR NOT NULL,
                quantity FLOAT,
                price FLOAT,
                total_amount FLOAT NOT NULL,
                transaction_date DATE NOT NULL,
                notes TEXT,
                created_at DATETIME,
                updated_at DATETIME,
                version INTEGER NOT NULL DEFAULT 1
            )
        """))
        print("✓ Temporary table created")

        # Copy data from old table to new table
        print("\n[3] Copying data to new table...")
        db.execute(text("""
            INSERT INTO transactions_new
            (id, transaction_type, ticker, quantity, price, total_amount,
             transaction_date, notes, created_at, updated_at, version)
            SELECT
                id, transaction_type, ticker, quantity, price, total_amount,
                transaction_date, notes, created_at, updated_at, 1
            FROM transactions
        """))
        print("✓ Data copied successfully")

        # Drop old table
        print("\n[4] Dropping old table...")
        db.execute(text("DROP TABLE transactions"))
        print("✓ Old table dropped")

        # Rename new table
        print("\n[5] Renaming new table...")
        db.execute(text("ALTER TABLE transactions_new RENAME TO transactions"))
        print("✓ Table renamed")

        # Recreate indexes
        print("\n[6] Recreating indexes...")
        db.execute(text("CREATE INDEX ix_transactions_ticker ON transactions (ticker)"))
        db.execute(text("CREATE INDEX ix_transactions_transaction_date ON transactions (transaction_date)"))
        db.execute(text("CREATE INDEX ix_transactions_id ON transactions (id)"))
        print("✓ Indexes recreated")

        # Commit the transaction
        db.commit()
        print("\n" + "=" * 60)
        print("✓ Migration completed successfully!")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n✗ ERROR: Migration failed!")
        print(f"   {str(e)}")
        db.rollback()
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    try:
        success = migrate_add_version_column()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ FATAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
