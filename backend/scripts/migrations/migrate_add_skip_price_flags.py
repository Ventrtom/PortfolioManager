"""
Migration script to add skip_price_fetch columns to stocks table
and auto-flag tickers with repeated enrichment failures
"""
import sqlite3
from datetime import datetime

DATABASE_PATH = "portfolio.db"


def migrate():
    """Add skip price fetch columns and flag failed tickers"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    print("Starting migration: Adding skip_price_fetch columns...")

    try:
        # Add new columns (with error handling for existing columns)
        columns_to_add = [
            ("skip_price_fetch", "BOOLEAN DEFAULT 0"),
            ("skip_price_reason", "TEXT"),
            ("skip_price_since", "DATETIME"),
            ("consecutive_failures", "INTEGER DEFAULT 0")
        ]

        columns_added = 0
        for col_name, col_def in columns_to_add:
            try:
                print(f"  - Adding {col_name} column...")
                cursor.execute(f"ALTER TABLE stocks ADD COLUMN {col_name} {col_def}")
                columns_added += 1
            except sqlite3.OperationalError as e:
                if "duplicate column" in str(e).lower():
                    print(f"    [SKIP] {col_name} already exists")
                else:
                    raise

        conn.commit()
        if columns_added > 0:
            print(f"[OK] {columns_added} column(s) added successfully")
        else:
            print("[OK] All columns already exist")

        # Auto-flag tickers with enrichment failures
        print("\nAuto-flagging tickers with repeated enrichment failures...")

        # Find stocks with enrichment_status='failed' and enrichment_attempts >= 3
        cursor.execute("""
            SELECT ticker, enrichment_attempts, enrichment_error
            FROM stocks
            WHERE enrichment_status = 'failed' AND enrichment_attempts >= 3
        """)

        failed_stocks = cursor.fetchall()

        if failed_stocks:
            print(f"  Found {len(failed_stocks)} ticker(s) to flag:")

            for ticker, attempts, error in failed_stocks:
                print(f"    - {ticker} (attempts: {attempts})")

                cursor.execute("""
                    UPDATE stocks
                    SET skip_price_fetch = 1,
                        skip_price_reason = 'enrichment_failed',
                        skip_price_since = ?,
                        consecutive_failures = ?
                    WHERE ticker = ?
                """, (datetime.utcnow().isoformat(), attempts, ticker))

            conn.commit()
            print(f"[OK] Flagged {len(failed_stocks)} ticker(s)")
        else:
            print("  No tickers need flagging")

        # Display summary
        print("\nMigration Summary:")
        cursor.execute("SELECT COUNT(*) FROM stocks WHERE skip_price_fetch = 1")
        flagged_count = cursor.fetchone()[0]
        print(f"  Total flagged tickers: {flagged_count}")

        cursor.execute("SELECT COUNT(*) FROM stocks")
        total_count = cursor.fetchone()[0]
        print(f"  Total stocks: {total_count}")

        # List flagged tickers
        if flagged_count > 0:
            print("\nFlagged Tickers:")
            cursor.execute("""
                SELECT ticker, skip_price_reason, consecutive_failures
                FROM stocks
                WHERE skip_price_fetch = 1
            """)
            for ticker, reason, failures in cursor.fetchall():
                print(f"  - {ticker}: {reason} ({failures} failures)")

        print("\n[OK] Migration completed successfully!")

    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print(f"[WARNING] Warning: Columns already exist. Migration may have been run before.")
            print(f"  Error: {e}")
        else:
            print(f"[ERROR] Error during migration: {e}")
            conn.rollback()
            raise

    finally:
        conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Skip Price Fetch Flags Migration")
    print("=" * 60)
    migrate()
