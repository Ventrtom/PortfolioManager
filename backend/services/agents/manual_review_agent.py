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


# Tool definition for Claude to trigger save actions
SAVE_MAPPING_TOOL = {
    "name": "save_ticker_mapping",
    "description": "Save the confirmed ticker mapping to the database. ONLY call this tool when: 1) A ticker has been successfully checked and verified in this conversation, 2) The user has explicitly confirmed they want to save (e.g., 'yes', 'save it', 'that's correct', 'confirm'). Do NOT call this tool if no ticker has been checked yet or if the user seems uncertain.",
    "input_schema": {
        "type": "object",
        "properties": {
            "resolved_ticker": {
                "type": "string",
                "description": "The verified ticker symbol to save as the mapping (must have been checked in this conversation)"
            },
            "user_confirmed": {
                "type": "boolean",
                "description": "Set to true only if the user explicitly confirmed they want to save"
            }
        },
        "required": ["resolved_ticker", "user_confirmed"]
    }
}


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

    def _extract_verified_tickers_from_history(
        self,
        conversation_history: List[Dict[str, str]]
    ) -> set:
        """
        Extract tickers that were successfully verified in previous conversation turns.

        This is used as a security guard to ensure we only save tickers that have
        been checked and found valid in this conversation.

        Args:
            conversation_history: Previous messages in conversation

        Returns:
            Set of ticker symbols that were successfully checked
        """
        import re
        verified_tickers = set()

        for msg in conversation_history:
            content = msg.get('content', '')
            # Look for successful ticker check patterns in assistant messages
            # Pattern: "✓ TICKER: Company Name" or "I checked TICKER" with positive result
            if msg.get('role') == 'assistant':
                # Match "✓ TICKER:" pattern (from system context injection)
                matches = re.findall(r'✓\s*([A-Z]{1,5}):', content)
                verified_tickers.update(matches)

                # Also match patterns like "TICKER is valid" or "found TICKER"
                # Looking for uppercase tickers followed by positive indicators
                positive_patterns = [
                    r'([A-Z]{1,5})\s+(?:is|was)\s+(?:valid|found|correct|verified)',
                    r'found\s+([A-Z]{1,5})',
                    r'([A-Z]{1,5})\s+stands?\s+for',
                    r'([A-Z]{1,5}):\s+[A-Z]',  # "GEO: The GEO Group" pattern
                ]
                for pattern in positive_patterns:
                    matches = re.findall(pattern, content)
                    verified_tickers.update(matches)

        return verified_tickers

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
                'executed_action': {...}  # Action executed by AI (e.g., save), or None
            }
        """
        import re

        try:
            client = self._get_client()
            model = self._get_available_model()

            # Extract previously verified tickers from conversation history
            verified_tickers = self._extract_verified_tickers_from_history(conversation_history)

            # Build system prompt with tool use instructions
            system_prompt = f"""You are a helpful AI assistant specializing in stock ticker resolution.

You are helping the user resolve ticker symbol: {original_ticker}

This ticker failed automatic resolution and needs manual guidance. Your role:
1. Listen to the user's instructions
2. Check alternative ticker symbols when requested
3. Provide clear, concise responses about what you found
4. Save the mapping when the user confirms

IMPORTANT - You have a save_ticker_mapping tool available. Use it when:
- A ticker has been successfully checked and found valid in this conversation
- The user explicitly confirms they want to save (e.g., "yes", "save it", "that's correct", "confirm", "looks good")

DO NOT use the save tool if:
- No ticker has been checked yet in this conversation
- The user is just asking questions or seems uncertain
- The user hasn't explicitly confirmed

Previously verified tickers in this conversation: {list(verified_tickers) if verified_tickers else 'None yet'}

When checking a ticker, provide:
- Company name
- Sector and industry
- Whether it seems to match the original company

Keep responses brief and actionable. Use a friendly, professional tone."""

            # Parse user message for actions
            user_message_lower = user_message.lower()
            actions_performed = []
            newly_verified_tickers = set()

            # Check if user wants to check a specific ticker
            if "check" in user_message_lower or "try" in user_message_lower:
                # Extract potential ticker symbols (2-5 uppercase letters)
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
                        if result.found:
                            newly_verified_tickers.add(ticker_candidate)

            # Combine historical and newly verified tickers
            all_verified_tickers = verified_tickers | newly_verified_tickers

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

            # Call Claude with tool use enabled
            response = client.messages.create(
                model=model,
                max_tokens=1000,
                system=system_prompt,
                messages=messages,
                tools=[SAVE_MAPPING_TOOL]
            )

            # Process response - may contain text and/or tool use
            ai_response = ""
            executed_action = None
            tool_use_block = None

            for block in response.content:
                if block.type == "text":
                    ai_response = block.text
                elif block.type == "tool_use":
                    tool_use_block = block

            # Handle tool use if Claude called the save tool
            if tool_use_block and tool_use_block.name == "save_ticker_mapping":
                tool_input = tool_use_block.input
                resolved_ticker = tool_input.get("resolved_ticker", "").upper()
                user_confirmed = tool_input.get("user_confirmed", False)

                logger.info(
                    f"AI requested save: ticker={resolved_ticker}, "
                    f"confirmed={user_confirmed}, verified_tickers={all_verified_tickers}"
                )

                # Security guards
                if not user_confirmed:
                    # AI should not have called tool without confirmation
                    logger.warning("AI called save tool without user_confirmed=True")
                    ai_response = "I need you to confirm before I can save. Would you like me to save this mapping?"
                elif resolved_ticker not in all_verified_tickers:
                    # Ticker wasn't verified - need to check it first
                    logger.warning(
                        f"AI tried to save unverified ticker {resolved_ticker}. "
                        f"Verified: {all_verified_tickers}"
                    )
                    # Check the ticker now
                    check_result = self.check_ticker(resolved_ticker, db)
                    actions_performed.append({
                        'type': 'ticker_check',
                        'ticker': resolved_ticker,
                        'result': asdict(check_result)
                    })
                    if check_result.found:
                        ai_response = (
                            f"I found {resolved_ticker} ({check_result.company_name}). "
                            f"Would you like me to save this as the mapping for {original_ticker}?"
                        )
                        all_verified_tickers.add(resolved_ticker)
                    else:
                        ai_response = (
                            f"I couldn't find {resolved_ticker} in any data provider. "
                            f"Could you suggest a different ticker symbol?"
                        )
                else:
                    # All guards passed - execute the save
                    logger.info(f"Executing save: {original_ticker} → {resolved_ticker}")
                    save_result = self.save_mapping(original_ticker, resolved_ticker, db)

                    if save_result.get('success'):
                        company_name = save_result.get('company_name', resolved_ticker)
                        ai_response = (
                            f"Done! I've saved the mapping: **{original_ticker}** → **{resolved_ticker}** "
                            f"({company_name}). The stock data has been updated."
                        )
                        executed_action = {
                            'type': 'save_mapping',
                            'ticker': resolved_ticker,
                            'company_name': company_name,
                            'success': True
                        }
                    else:
                        error = save_result.get('error', 'Unknown error')
                        ai_response = f"I tried to save the mapping, but encountered an error: {error}"
                        logger.error(f"Save failed: {error}")

            # Determine suggested quick actions based on context
            suggested_actions = []

            # Don't show save buttons if we just executed a save
            if not executed_action:
                # If we found valid tickers, suggest saving
                for action in actions_performed:
                    if action['type'] == 'ticker_check' and action['result']['found']:
                        suggested_actions.append({
                            'type': 'save_mapping',
                            'label': f"Save as {action['result']['ticker']}",
                            'ticker': action['result']['ticker']
                        })

                # Also add buttons for previously verified tickers if they exist
                for vt in verified_tickers:
                    if not any(a.get('ticker') == vt for a in suggested_actions):
                        suggested_actions.append({
                            'type': 'save_mapping',
                            'label': f"Save as {vt}",
                            'ticker': vt
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
                'suggested_actions': suggested_actions,
                'executed_action': executed_action
            }

        except Exception as e:
            logger.error(f"Manual review chat error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'message': f"Sorry, I encountered an error: {str(e)}",
                'actions': [],
                'suggested_actions': [],
                'executed_action': None
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
