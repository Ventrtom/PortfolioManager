from sqlalchemy import create_engine, Column, Integer, Float, String, Date, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

# Database setup
DATABASE_URL = "sqlite:///./portfolio.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Database models
class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    transaction_type = Column(String, nullable=False)  # BUY, SELL, DIVIDEND, FEE, TAX
    ticker = Column(String, nullable=False, index=True)
    quantity = Column(Float, nullable=True)  # Null for fees/taxes
    price = Column(Float, nullable=True)  # Price per share
    total_amount = Column(Float, nullable=False)  # Total transaction amount
    transaction_date = Column(Date, nullable=False, index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    version = Column(Integer, default=1, nullable=False)  # Optimistic locking


class Stock(Base):
    __tablename__ = "stocks"

    ticker = Column(String, primary_key=True, index=True)
    company_name = Column(String, nullable=True)
    sector = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    currency = Column(String, default="USD")
    last_updated = Column(DateTime, nullable=True)


class StockPrice(Base):
    __tablename__ = "stock_prices"

    ticker = Column(String, primary_key=True, index=True)
    price = Column(Float, nullable=False)
    price_date = Column(Date, primary_key=True)


class TransactionHistory(Base):
    __tablename__ = "transaction_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    transaction_id = Column(Integer, index=True, nullable=False)

    # Snapshot of transaction fields at time of change
    transaction_type = Column(String, nullable=False)
    ticker = Column(String, nullable=False, index=True)
    quantity = Column(Float, nullable=True)
    price = Column(Float, nullable=True)
    total_amount = Column(Float, nullable=False)
    transaction_date = Column(Date, nullable=False, index=True)
    notes = Column(Text, nullable=True)

    # Audit metadata
    change_type = Column(String, nullable=False)  # 'CREATE', 'UPDATE', 'DELETE'
    changed_by = Column(String, nullable=True)  # Future: user identification
    changed_at = Column(DateTime, default=datetime.utcnow, index=True)
    changed_fields = Column(Text, nullable=True)  # JSON string of changed fields


# Database initialization
def init_db():
    """Create all tables in the database"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
