"""
Manual Review Agent

Interactive AI agent for manually resolving ticker issues through conversation.
User can chat with the agent to guide ticker resolution, verification, and correction.
"""

import os
import json
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from anthropic import Anthropic

logger = logging.getLogger(__name__)


@dataclass
class ChatMessage:
    """Single message in the conversation"""
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: str = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TickerCheckResult:
    """Result of checking a ticker symbol"""
    ticker: str
    found: bool
    company_name: Optional[str]
    sector: Optional[str]
    industry: Optional[str]
    market_cap: Optional[float]
    provider: Optional[str]
    error: Optional[str]


class ManualReviewAgent:
    """
    Interactive AI agent for manual ticker resolution.

    Features:
    - Conversational interface for user guidance
    - Can check alternative tickers on demand
    - Verifies user suggestions
    - Saves confirmed mappings
    """

    _client: Optional[Anthropic] = None
    _available_model: Optional[str] = None

    @classmethod
    def _get_client(cls) -> Anthropic:
        """Get or create Anthropic client"""
        if cls._client is None:
            api_key = os.environ.get('ANTHROPIC_API_KEY')
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable not set")
            cls._client = Anthropic(api_key=api_key)
        return cls._client

    @classmethod
    def _get_available_model(cls) -> str:
        """Get best available model"""
        if cls._available_model:
            return cls._available_model

        models_to_try = [
            "claude-opus-4-5-20251101",
            "claude-3-5-sonnet-20250219",
        ]

        client = cls._get_client()

        for model in models_to_try:
            try:
                client.messages.create(
                    model=model,
                    max_tokens=10,
                    messages=[{"role": "user", "content": "test"}]
                )
                logger.info(f"Manual Review Agent using model: {model}")
                cls._available_model = model
                return model
            except Exception as e:
                if "404" in str(e) or "not_found" in str(e):
                    continue

        cls._available_model = "claude-3-5-sonnet-20250219"
        return cls._available_model

    def check_ticker(self, ticker: str, db=None) -> TickerCheckResult:
        """
        Check if a ticker exists and fetch its data.

        Args:
            ticker: Ticker symbol to check
            db: Database session (optional)

        Returns:
            TickerCheckResult with findings
        """
        try:
            from services.multi_provider_data_service import MultiProviderDataService

            multi_provider = MultiProviderDataService()
            stock_info = multi_provider.get_stock_info(ticker, db)

            if stock_info and stock_info.get('company_name'):
                return TickerCheckResult(
                    ticker=ticker,
                    found=True,
                    company_name=stock_info.get('company_name'),
                    sector=stock_info.get('sector'),
                    industry=stock_info.get('industry'),
                    market_cap=stock_info.get('market_cap'),
                    provider=stock_info.get('provider'),
                    error=None
                )
            else:
                return TickerCheckResult(
                    ticker=ticker,
                    found=False,
                    company_name=None,
                    sector=None,
                    industry=None,
                    market_cap=None,
                    provider=None,
                    error="Ticker not found in any data provider"
                )
        except Exception as e:
            logger.error(f"Error checking ticker {ticker}: {e}")
            return TickerCheckResult(
                ticker=ticker,
                found=False,
                company_name=None,
                sector=None,
                industry=None,
                market_cap=None,
                provider=None,
                error=str(e)
            )

    def chat(
        self,
        original_ticker: str,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        db=None
    ) -> Dict[str, Any]:
        """
        Process user message and return AI response with actions.

        Args:
            original_ticker: The problematic ticker being resolved
            user_message: User's message
            conversation_history: Previous messages in conversation
            db: Database session

        Returns:
            {
                'message': str,  # AI's response
                'actions': [...]  # Actions performed (ticker checks, etc)
                'suggested_actions': [...]  # Quick action buttons to show
            }
        """
        try:
            client = self._get_client()
            model = self._get_available_model()

            # Build system prompt
            system_prompt = f"""You are a helpful AI assistant specializing in stock ticker resolution.

You are helping the user resolve ticker symbol: {original_ticker}

This ticker failed automatic resolution and needs manual guidance. Your role:
1. Listen to the user's instructions
2. Check alternative ticker symbols when requested
3. Provide clear, concise responses about what you found
4. Ask for confirmation before saving changes
5. Be conversational and helpful

Available actions you can suggest:
- "check <TICKER>" - Check if a ticker exists and get its data
- "save as <TICKER>" - Save the mapping (only after user confirms)
- "search <COMPANY NAME>" - Search for a company (future feature)

When checking a ticker, provide:
- Company name
- Sector and industry
- Whether it seems to match the original company

Keep responses brief and actionable. Use a friendly, professional tone."""

            # Parse user message for actions
            user_message_lower = user_message.lower()
            actions_performed = []

            # Check if user wants to check a specific ticker
            if "check" in user_message_lower or "try" in user_message_lower:
                # Extract potential ticker symbols (2-5 uppercase letters)
                import re
                potential_tickers = re.findall(r'\b[A-Z]{1,5}\b', user_message)

                for ticker_candidate in potential_tickers:
                    if ticker_candidate != original_ticker:
                        logger.info(f"Checking ticker suggested by user: {ticker_candidate}")
                        result = self.check_ticker(ticker_candidate, db)
                        actions_performed.append({
                            'type': 'ticker_check',
                            'ticker': ticker_candidate,
                            'result': asdict(result)
                        })

            # Build conversation for Claude
            messages = []

            # Add conversation history
            for msg in conversation_history:
                messages.append({
                    "role": msg['role'],
                    "content": msg['content']
                })

            # Add current user message
            messages.append({
                "role": "user",
                "content": user_message
            })

            # If we performed ticker checks, add results to the conversation
            if actions_performed:
                context_info = "\n\n[System: I checked the following tickers for you]\n"
                for action in actions_performed:
                    if action['type'] == 'ticker_check':
                        result = action['result']
                        ticker = result['ticker']
                        if result['found']:
                            context_info += f"\n✓ {ticker}: {result['company_name']}"
                            if result['sector']:
                                context_info += f" | {result['sector']}"
                            if result['industry']:
                                context_info += f" - {result['industry']}"
                        else:
                            context_info += f"\n✗ {ticker}: Not found ({result['error']})"

                # Append system context to last user message
                messages[-1]['content'] += context_info

            # Call Claude
            response = client.messages.create(
                model=model,
                max_tokens=1000,
                system=system_prompt,
                messages=messages
            )

            ai_response = response.content[0].text

            # Determine suggested quick actions based on context
            suggested_actions = []

            # If we found a valid ticker, suggest saving
            if actions_performed:
                for action in actions_performed:
                    if action['type'] == 'ticker_check' and action['result']['found']:
                        suggested_actions.append({
                            'type': 'save_mapping',
                            'label': f"Save as {action['result']['ticker']}",
                            'ticker': action['result']['ticker']
                        })

            # Always allow user to try another ticker
            suggested_actions.append({
                'type': 'check_ticker',
                'label': 'Check another ticker',
                'ticker': None
            })

            return {
                'message': ai_response,
                'actions': actions_performed,
                'suggested_actions': suggested_actions
            }

        except Exception as e:
            logger.error(f"Manual review chat error: {e}")
            return {
                'message': f"Sorry, I encountered an error: {str(e)}",
                'actions': [],
                'suggested_actions': []
            }

    def save_mapping(
        self,
        original_ticker: str,
        resolved_ticker: str,
        db
    ) -> Dict[str, Any]:
        """
        Save the confirmed ticker mapping and update stock data.

        Args:
            original_ticker: Original problematic ticker
            resolved_ticker: Confirmed correct ticker
            db: Database session

        Returns:
            Result of the save operation
        """
        try:
            from models.database import Stock
            from services.multi_provider_data_service import MultiProviderDataService
            from datetime import datetime

            # Get stock record
            stock = db.query(Stock).filter(Stock.ticker == original_ticker).first()

            if not stock:
                return {
                    'success': False,
                    'error': f'Stock {original_ticker} not found in database'
                }

            # Fetch data for resolved ticker
            multi_provider = MultiProviderDataService()
            stock_info = multi_provider.get_stock_info(resolved_ticker, db)

            if not stock_info or not stock_info.get('company_name'):
                return {
                    'success': False,
                    'error': f'Could not fetch data for {resolved_ticker}'
                }

            # Update stock with resolved data
            stock.company_name = stock_info.get('company_name')
            stock.sector = stock_info.get('sector')
            stock.industry = stock_info.get('industry')
            stock.currency = stock_info.get('currency', 'USD')
            stock.market_cap = stock_info.get('market_cap')
            stock.volume = stock_info.get('volume')
            stock.last_updated = datetime.utcnow()

            # Store the resolved symbol (what actually worked)
            stock.resolved_symbol = resolved_ticker

            # Store alternative symbols mapping
            import json
            stock.alternative_symbols = json.dumps([resolved_ticker])

            # Mark as manually resolved
            stock.enrichment_status = 'complete'
            stock.enrichment_error = None

            db.commit()

            logger.info(
                f"Manual review: Saved mapping {original_ticker} → {resolved_ticker} "
                f"({stock_info.get('company_name')})"
            )

            return {
                'success': True,
                'resolved_ticker': resolved_ticker,
                'company_name': stock_info.get('company_name'),
                'data': stock_info
            }

        except Exception as e:
            logger.error(f"Error saving mapping {original_ticker} → {resolved_ticker}: {e}")
            db.rollback()
            return {
                'success': False,
                'error': str(e)
            }

    def get_initial_message(self, ticker: str, reason: str = None) -> str:
        """
        Get initial greeting message when starting manual review.

        Args:
            ticker: The problematic ticker
            reason: Why it failed (optional)

        Returns:
            Greeting message
        """
        greeting = f"I couldn't automatically resolve ticker **{ticker}**."

        if reason:
            greeting += f"\n\nReason: {reason}"

        greeting += "\n\nHow can I help you resolve this? You can:"
        greeting += "\n- Tell me to check an alternative ticker symbol"
        greeting += "\n- Ask me to search for the company name"
        greeting += "\n- Provide any information about this stock"

        return greeting
