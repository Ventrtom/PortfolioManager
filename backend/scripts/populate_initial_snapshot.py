from models.database import SessionLocal
from services.analytics_service import AnalyticsService
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def populate_initial_snapshot():
    """Create initial KPI snapshot after migration"""
    db = SessionLocal()
    try:
        logger.info("Calculating initial KPI snapshot...")
        result = AnalyticsService.recalculate_and_save_kpis(db, use_cached_prices=True)
        logger.info(f"Initial snapshot created successfully at {result.metadata.calculated_at}")
        logger.info(f"Calculation took {result.metadata.calculation_duration_ms}ms")
    except Exception as e:
        logger.error(f"Failed to create initial snapshot: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    populate_initial_snapshot()
