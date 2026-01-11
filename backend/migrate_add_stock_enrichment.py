"""
Migration to add enrichment fields to Stock table
Run: python backend/migrate_add_stock_enrichment.py
"""
import sys
import io
from sqlalchemy import inspect, text
from models.database import engine, init_db, SessionLocal

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def migrate():
    print("=" * 60)
    print("Stock Table Enrichment Migration")
    print("=" * 60)

    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns('stocks')]

    if 'market_cap' in columns:
        print("✓ Migration already applied")
        return

    print("\n[1] Adding new columns to stocks table...")

    with engine.connect() as conn:
        # SQLite doesn't support adding multiple columns at once
        conn.execute(text("ALTER TABLE stocks ADD COLUMN market_cap FLOAT"))
        conn.execute(text("ALTER TABLE stocks ADD COLUMN volume INTEGER"))
        conn.execute(text("ALTER TABLE stocks ADD COLUMN alternative_symbols TEXT"))
        conn.execute(text("ALTER TABLE stocks ADD COLUMN enrichment_status TEXT DEFAULT 'pending'"))
        conn.execute(text("ALTER TABLE stocks ADD COLUMN enrichment_attempts INTEGER DEFAULT 0"))
        conn.execute(text("ALTER TABLE stocks ADD COLUMN enrichment_error TEXT"))
        conn.execute(text("ALTER TABLE stocks ADD COLUMN last_enrichment_attempt TEXT"))
        conn.execute(text("ALTER TABLE stocks ADD COLUMN is_manually_edited INTEGER DEFAULT 0"))
        conn.execute(text("ALTER TABLE stocks ADD COLUMN created_at TEXT"))
        conn.commit()

    print("✓ Migration complete")

    # Update existing stocks to 'complete' status
    print("\n[2] Updating existing stocks to 'complete' status...")
    db = SessionLocal()
    from models.database import Stock
    stocks = db.query(Stock).all()
    for stock in stocks:
        if stock.company_name:  # Has data, mark as complete
            stock.enrichment_status = 'complete'
    db.commit()
    db.close()
    print(f"✓ Updated {len(stocks)} existing stocks")

if __name__ == "__main__":
    try:
        migrate()
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
