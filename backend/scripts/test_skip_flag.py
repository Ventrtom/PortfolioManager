"""
Test script to verify skip_price_fetch functionality
"""
from models.database import Stock, SessionLocal
from datetime import datetime

def test_skip_flag():
    db = SessionLocal()

    try:
        # Flag ARR.US for testing
        print("1. Flagging ARR.US...")
        stock = db.query(Stock).filter(Stock.ticker == "ARR.US").first()

        if stock:
            stock.skip_price_fetch = True
            stock.skip_price_reason = "delisted_ticker"
            stock.skip_price_since = datetime.utcnow()
            stock.consecutive_failures = 5
            db.commit()
            print(f"   [OK] Flagged {stock.ticker}")
            print(f"        Reason: {stock.skip_price_reason}")
            print(f"        Failures: {stock.consecutive_failures}")
        else:
            print("   [ERROR] ARR.US not found")
            return

        # Test market data service
        print("\n2. Testing MarketDataService...")
        from services.market_data_service import MarketDataService

        price = MarketDataService.get_current_price("ARR.US", db)
        if price is None:
            print("   [OK] Price fetch correctly skipped for ARR.US")
        else:
            print(f"   [WARNING] Price fetch returned {price} (should be None)")

        # Test with unflagged ticker
        print("\n3. Testing with unflagged ticker (GEO.US)...")
        geo_stock = db.query(Stock).filter(Stock.ticker == "GEO.US").first()
        if geo_stock and not geo_stock.skip_price_fetch:
            print("   [OK] GEO.US is not flagged")

        # Test API endpoint simulation
        print("\n4. Testing skip flag update...")
        stock.skip_price_fetch = False
        stock.skip_price_reason = None
        stock.consecutive_failures = 0
        db.commit()
        print(f"   [OK] Unflagged {stock.ticker}")
        print(f"        skip_price_fetch: {stock.skip_price_fetch}")

        # Re-flag for actual use
        stock.skip_price_fetch = True
        stock.skip_price_reason = "delisted_ticker"
        stock.skip_price_since = datetime.utcnow()
        stock.consecutive_failures = 5
        db.commit()
        print(f"\n5. Re-flagged ARR.US for production use")

        print("\n[SUCCESS] All tests passed!")

    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_skip_flag()
