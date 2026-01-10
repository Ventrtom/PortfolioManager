"""
Test script for Phase 2 - Backend validation and audit trail
Tests that all services integrate correctly
"""
import sys
import io
from datetime import date, timedelta
from models.database import init_db, SessionLocal, Transaction
from services.validation_service import TransactionValidator, ValidationError
from services.audit_service import AuditService
from models.schemas import TransactionUpdate

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_phase2():
    """Test Phase 2 integration"""
    print("=" * 60)
    print("Testing Phase 2: Validation & Audit Services")
    print("=" * 60)

    # Initialize database
    print("\n[1] Initializing database...")
    init_db()
    db = SessionLocal()
    print("✓ Database initialized")

    try:
        # Clean up any test data
        db.query(Transaction).filter(Transaction.ticker == 'TEST').delete()
        db.commit()

        # Test 1: Create a test transaction
        print("\n[2] Creating test transaction...")
        test_txn = Transaction(
            transaction_type='BUY',
            ticker='TEST',
            quantity=100,
            price=50.00,
            total_amount=5000.00,
            transaction_date=date.today() - timedelta(days=10),
            notes='Test transaction'
        )
        db.add(test_txn)
        db.commit()
        db.refresh(test_txn)
        print(f"✓ Test transaction created (ID: {test_txn.id})")

        # Test 2: Test validation - valid update
        print("\n[3] Testing valid update validation...")
        update_valid = TransactionUpdate(quantity=110, price=48.00)
        result = TransactionValidator.validate_transaction_update(
            db, test_txn.id, update_valid
        )
        if result['valid']:
            print("✓ Valid update passed validation")
        else:
            print(f"✗ ERROR: Valid update failed: {result['errors']}")
            return False

        # Test 3: Test validation - future date (should fail)
        print("\n[4] Testing invalid date validation (future date)...")
        update_invalid = TransactionUpdate(
            transaction_date=date.today() + timedelta(days=30)
        )
        result = TransactionValidator.validate_transaction_update(
            db, test_txn.id, update_invalid
        )
        if not result['valid'] and any('future' in err['message'].lower() for err in result['errors']):
            print("✓ Future date correctly rejected")
        else:
            print(f"✗ ERROR: Future date should be rejected")
            return False

        # Test 4: Test portfolio integrity validation
        print("\n[5] Testing portfolio integrity validation...")
        # Create a SELL transaction
        sell_txn = Transaction(
            transaction_type='SELL',
            ticker='TEST',
            quantity=50,
            price=55.00,
            total_amount=2750.00,
            transaction_date=date.today() - timedelta(days=5),
            notes='Test sell'
        )
        db.add(sell_txn)
        db.commit()
        db.refresh(sell_txn)

        # Try to edit the BUY to have less than what was sold (should fail)
        update_insufficient = TransactionUpdate(quantity=30)  # Less than the 50 we sold
        result = TransactionValidator.validate_transaction_update(
            db, test_txn.id, update_insufficient
        )
        if not result['valid'] and any('fifo' in err['code'].lower() or 'insufficient' in err['code'].lower() for err in result['errors']):
            print("✓ Portfolio integrity validation working (FIFO chain break detected)")
        else:
            print(f"✗ ERROR: Should reject selling more than owned")
            print(f"   Result: {result}")
            return False

        # Test 5: Test audit trail
        print("\n[6] Testing audit trail...")
        # Record a change
        AuditService.record_change(db, test_txn, 'UPDATE', original=test_txn)
        db.commit()

        # Retrieve history
        history = AuditService.get_transaction_history(db, test_txn.id)
        if len(history) > 0:
            print(f"✓ Audit trail working ({len(history)} record(s) found)")
            print(f"   Latest change: {history[0].change_type} at {history[0].changed_at}")
        else:
            print("✗ ERROR: No audit history found")
            return False

        # Test 6: Test ValidationError exception
        print("\n[7] Testing ValidationError exception...")
        try:
            # This should raise ValidationError
            from services.transaction_service import TransactionService
            TransactionService.update_transaction(
                db,
                test_txn.id,
                TransactionUpdate(transaction_date=date.today() + timedelta(days=1))
            )
            print("✗ ERROR: Should have raised ValidationError")
            return False
        except ValidationError as e:
            print(f"✓ ValidationError correctly raised: {e.message}")

        print("\n" + "=" * 60)
        print("✓ All Phase 2 Tests PASSED!")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n✗ ERROR: Test failed with exception:")
        print(f"   {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        db.query(Transaction).filter(Transaction.ticker == 'TEST').delete()
        db.commit()
        db.close()

if __name__ == "__main__":
    try:
        success = test_phase2()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ FATAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
