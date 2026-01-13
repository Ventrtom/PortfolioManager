from models.database import engine, Base, PortfolioSnapshot
from sqlalchemy import inspect
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    """Create portfolio_snapshots table if it doesn't exist"""
    inspector = inspect(engine)
    if 'portfolio_snapshots' not in inspector.get_table_names():
        logger.info("Creating portfolio_snapshots table...")
        PortfolioSnapshot.__table__.create(engine)
        logger.info("Portfolio snapshots table created successfully")
    else:
        logger.info("Portfolio snapshots table already exists")

if __name__ == "__main__":
    migrate()
