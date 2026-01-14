from dotenv import load_dotenv
import os

# Load environment variables FIRST (before any other imports)
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from models.database import init_db
from routes import transactions, portfolio, analytics, stocks, manual_review

# Initialize FastAPI app
app = FastAPI(
    title="Portfolio Manager API",
    description="API for managing investment portfolios",
    version="1.0.0"
)

# Configure CORS
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
allowed_origins = [origin.strip() for origin in cors_origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
def startup_event():
    init_db()
    print("Database initialized successfully")

# Include routers
app.include_router(transactions.router, prefix="/api/transactions", tags=["Transactions"])
app.include_router(portfolio.router, prefix="/api/portfolio", tags=["Portfolio"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(stocks.router, prefix="/api/stocks", tags=["Stocks"])
app.include_router(manual_review.router, tags=["Manual Review"])

# Health check endpoint
@app.get("/")
def root():
    return {"message": "Portfolio Manager API is running", "version": "1.0.0"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}
