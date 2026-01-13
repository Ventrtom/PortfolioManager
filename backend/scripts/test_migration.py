"""
Test script to verify database migration for Phase 1
Tests that new TransactionHistory table and version column are created
"""
import sys
import io
from sqlalchemy import inspect
from models.database import engine, init_db, Transaction, TransactionHistory

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_migration():
    """Test that migration creates new schema correctly"""
    print("=" * 60)
    print("Testing Phase 1 Database Migration")
    print("=" * 60)

    # Initialize database (creates tables if not exist)
    print("\n[1] Initializing database...")
    init_db()
    print("✓ Database initialized")

    # Inspect the database
    inspector = inspect(engine)

    # Check Transaction table has version column
    print("\n[2] Checking Transaction table schema...")
    transaction_columns = [col['name'] for col in inspector.get_columns('transactions')]
    print(f"   Transaction columns: {', '.join(transaction_columns)}")

    if 'version' in transaction_columns:
        print("✓ Version column added to Transaction table")
    else:
        print("✗ ERROR: Version column NOT found in Transaction table")
        return False

    # Check TransactionHistory table exists
    print("\n[3] Checking TransactionHistory table...")
    tables = inspector.get_table_names()

    if 'transaction_history' in tables:
        print("✓ TransactionHistory table created")

        # Check columns
        history_columns = [col['name'] for col in inspector.get_columns('transaction_history')]
        print(f"   History columns: {', '.join(history_columns)}")

        expected_columns = [
            'id', 'transaction_id', 'transaction_type', 'ticker',
            'quantity', 'price', 'total_amount', 'transaction_date',
            'notes', 'change_type', 'changed_by', 'changed_at', 'changed_fields'
        ]

        missing_columns = [col for col in expected_columns if col not in history_columns]
        if missing_columns:
            print(f"✗ ERROR: Missing columns: {', '.join(missing_columns)}")
            return False
        else:
            print("✓ All expected columns present")
    else:
        print("✗ ERROR: TransactionHistory table NOT created")
        return False

    # Check indexes
    print("\n[4] Checking indexes...")
    history_indexes = inspector.get_indexes('transaction_history')
    index_columns = []
    for idx in history_indexes:
        index_columns.extend(idx['column_names'])

    print(f"   Indexed columns: {', '.join(set(index_columns))}")

    expected_indexes = ['transaction_id', 'ticker', 'transaction_date', 'changed_at']
    for col in expected_indexes:
        if col in index_columns:
            print(f"✓ Index on {col}")
        else:
            print(f"⚠ Warning: No index on {col}")

    print("\n" + "=" * 60)
    print("✓ Phase 1 Migration Test PASSED")
    print("=" * 60)
    return True

if __name__ == "__main__":
    try:
        success = test_migration()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ ERROR: Migration test failed with exception:")
        print(f"   {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
