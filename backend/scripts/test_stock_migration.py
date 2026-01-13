"""Test stock enrichment migration"""
import sys
import io
from sqlalchemy import inspect
from models.database import engine, init_db

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_migration():
    print("=" * 60)
    print("Testing Stock Enrichment Migration")
    print("=" * 60)

    init_db()
    inspector = inspect(engine)

    columns = [col['name'] for col in inspector.get_columns('stocks')]

    required = ['market_cap', 'volume', 'alternative_symbols', 'enrichment_status',
                'enrichment_attempts', 'enrichment_error', 'last_enrichment_attempt',
                'is_manually_edited', 'created_at']

    missing = [c for c in required if c not in columns]

    if missing:
        print(f"✗ Missing columns: {missing}")
        return False

    print("✓ All new columns present")
    print(f"\nFound columns: {', '.join(columns)}")
    return True

if __name__ == "__main__":
    success = test_migration()
    sys.exit(0 if success else 1)
