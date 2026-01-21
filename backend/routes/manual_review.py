"""
Manual Review API Routes

Endpoints for interactive AI-assisted ticker resolution
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime

from models.database import Stock, get_db
from services.agents.manual_review_agent import ManualReviewAgent

router = APIRouter()


class ChatRequest(BaseModel):
    """Request to chat with manual review agent"""
    message: str
    conversation_history: List[Dict[str, str]] = []


class ChatResponse(BaseModel):
    """Response from manual review agent"""
    message: str
    actions: List[Dict[str, Any]]
    suggested_actions: List[Dict[str, Any]]
    executed_action: Optional[Dict[str, Any]] = None  # Action executed by AI (e.g., save)


class SaveMappingRequest(BaseModel):
    """Request to save a ticker mapping"""
    resolved_ticker: str


@router.get("/api/stocks/{ticker}/manual-review/start")
def start_manual_review(ticker: str, db: Session = Depends(get_db)):
    """
    Start a manual review session for a ticker.

    Returns initial context and greeting message.
    """
    # Get stock record
    stock = db.query(Stock).filter(Stock.ticker == ticker).first()

    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {ticker} not found")

    # Get initial message from agent
    agent = ManualReviewAgent()
    initial_message = agent.get_initial_message(
        ticker=ticker,
        reason=stock.enrichment_error
    )

    return {
        'ticker': ticker,
        'status': stock.enrichment_status,
        'error': stock.enrichment_error,
        'initial_message': initial_message,
        'conversation_history': []
    }


@router.post("/api/stocks/{ticker}/manual-review/chat", response_model=ChatResponse)
def chat_with_agent(
    ticker: str,
    request: ChatRequest,
    db: Session = Depends(get_db)
):
    """
    Send a message to the manual review agent.

    The agent will:
    - Process the user's message
    - Perform requested actions (check tickers, search companies)
    - Return a helpful response with suggestions
    """
    # Verify stock exists
    stock = db.query(Stock).filter(Stock.ticker == ticker).first()

    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {ticker} not found")

    # Process message with agent
    agent = ManualReviewAgent()
    result = agent.chat(
        original_ticker=ticker,
        user_message=request.message,
        conversation_history=request.conversation_history,
        db=db
    )

    return ChatResponse(
        message=result['message'],
        actions=result['actions'],
        suggested_actions=result['suggested_actions'],
        executed_action=result.get('executed_action')
    )


@router.post("/api/stocks/{ticker}/manual-review/save")
def save_ticker_mapping(
    ticker: str,
    request: SaveMappingRequest,
    db: Session = Depends(get_db)
):
    """
    Save a confirmed ticker mapping.

    This updates the stock record with data from the resolved ticker.
    """
    # Verify stock exists
    stock = db.query(Stock).filter(Stock.ticker == ticker).first()

    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {ticker} not found")

    # Save mapping
    agent = ManualReviewAgent()
    result = agent.save_mapping(
        original_ticker=ticker,
        resolved_ticker=request.resolved_ticker,
        db=db
    )

    if not result['success']:
        raise HTTPException(status_code=400, detail=result['error'])

    return {
        'success': True,
        'message': f'Successfully resolved {ticker} to {request.resolved_ticker}',
        'data': result
    }


@router.get("/api/stocks/manual-review/queue")
def get_manual_review_queue(db: Session = Depends(get_db)):
    """
    Get all stocks that need manual review.

    Returns stocks with enrichment_status='manual' sorted by most recent.
    """
    stocks = db.query(Stock).filter(
        Stock.enrichment_status == 'manual'
    ).order_by(
        Stock.last_enrichment_attempt.desc()
    ).all()

    return {
        'count': len(stocks),
        'stocks': [
            {
                'ticker': stock.ticker,
                'company_name': stock.company_name,
                'error': stock.enrichment_error,
                'attempts': stock.enrichment_attempts,
                'last_attempt': stock.last_enrichment_attempt.isoformat() if stock.last_enrichment_attempt else None
            }
            for stock in stocks
        ]
    }
