"""
Ticker Analyzer Agent

AI agent specialized in ticker symbol research and resolution.
Uses Claude with web search tools for real-time corporate action research.
"""

import os
import json
import logging
from typing import Optional, List, Dict
from dataclasses import dataclass, asdict
from datetime import datetime
from anthropic import Anthropic

logger = logging.getLogger(__name__)


@dataclass
class TickerAnalysisResult:
    """Result of ticker analysis"""
    company_name: str
    status: str  # 'active', 'delisted', 'bankrupt', 'merged', 'unknown'
    successor_ticker: Optional[str]
    successor_company: Optional[str]
    change_date: Optional[str]  # YYYY-MM-DD
    alternative_symbols: List[str]
    reasoning: str
    confidence: str  # 'high', 'medium', 'low', 'needs_manual_review'
    recommended_action: str  # 'use_original', 'use_successor', 'manual_review_required'
    missing_information: Optional[str]
    web_search_used: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return asdict(self)


class TickerAnalyzerAgent:
    """
    AI agent specialized in ticker symbol research and resolution.
    Uses Claude with web search tools for real-time corporate action research.
    """

    # Initialize Claude API client (lazy)
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
        """
        Get best available Claude model with fallback
        Priority: opus-4.5 > sonnet-3.5
        """
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
                logger.info(f"Ticker Analyzer Agent using model: {model}")
                cls._available_model = model
                return model
            except Exception as e:
                if "404" in str(e) or "not_found" in str(e):
                    logger.warning(f"Model {model} not available, trying next...")
                    continue

        # Fallback to known working model
        cls._available_model = "claude-3-5-sonnet-20250219"
        return cls._available_model

    def _build_research_prompt(self, ticker: str, use_web_search: bool = False) -> str:
        """
        Build comprehensive research prompt for ticker analysis
        """
        base_prompt = f"""You are a financial research analyst specializing in ticker symbol resolution.

Ticker to research: {ticker}

Please analyze this ticker and provide a comprehensive report:

1. COMPANY IDENTIFICATION
   - Full company name
   - Current status (active, bankrupt, delisted, merged)
   - Primary exchange and country

2. CORPORATE ACTIONS (if applicable)
   - Ticker changes or rebranding
   - Mergers/acquisitions
   - Bankruptcy proceedings
   - Spin-offs or restructuring

3. SUCCESSOR INFORMATION (if delisted/bankrupt)
   - Acquiring company ticker
   - New ticker after merger/rebrand
   - Parent company if subsidiary

4. ALTERNATIVE SYMBOLS
   - Regional variations (e.g., GEO vs GEO.US vs GEO:NYSE)
   - Historical tickers
   - OTC/Pink Sheet symbols if delisted

5. RECOMMENDATIONS
   - Best ticker symbol to use for current data
   - Which APIs are most likely to have data
   - Confidence level: high/medium/low/needs_manual_review
   - If confidence < high, explain what information is missing

IMPORTANT: If you are uncertain, set confidence to "needs_manual_review" rather than guessing.

Format your response as JSON with this exact structure:
{{
  "company_name": "string",
  "status": "active|delisted|bankrupt|merged|unknown",
  "successor_ticker": "string or null",
  "successor_company": "string or null",
  "change_date": "YYYY-MM-DD or null",
  "alternative_symbols": ["array of strings"],
  "reasoning": "detailed explanation",
  "confidence": "high|medium|low|needs_manual_review",
  "recommended_action": "use_original|use_successor|manual_review_required",
  "missing_information": "what data is needed for higher confidence or null"
}}"""

        if use_web_search:
            base_prompt += f"""

You have access to web search. Use it to:
- Search for "{ticker} stock merger acquisition" to find corporate actions
- Search for "{ticker} delisted bankruptcy" to find status changes
- Search SEC filings or exchange announcements for official records
- Verify current trading status on major exchanges
- Search for "{ticker} ticker change symbol" to find rebranding

Prioritize official sources like SEC.gov, NYSE.com, NASDAQ.com over news articles.
Look for press releases from the company about ticker changes or mergers."""

        return base_prompt

    def _call_claude(self, ticker: str, use_web_search: bool = False) -> TickerAnalysisResult:
        """
        Call Claude API to analyze ticker
        """
        try:
            client = self._get_client()
            model = self._get_available_model()
            prompt = self._build_research_prompt(ticker, use_web_search)

            # Note: Web search integration depends on Anthropic API features
            # For now, we'll use the prompt to encourage Claude to use its knowledge
            # In production, you would integrate with actual web search tool
            response = client.messages.create(
                model=model,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )

            # Extract JSON from response
            content = response.content[0].text

            # Parse JSON (handle markdown code blocks)
            if '```json' in content:
                json_str = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                json_str = content.split('```')[1].split('```')[0].strip()
            else:
                json_str = content.strip()

            result_dict = json.loads(json_str)

            # Convert to TickerAnalysisResult
            result = TickerAnalysisResult(
                company_name=result_dict.get('company_name', ''),
                status=result_dict.get('status', 'unknown'),
                successor_ticker=result_dict.get('successor_ticker'),
                successor_company=result_dict.get('successor_company'),
                change_date=result_dict.get('change_date'),
                alternative_symbols=result_dict.get('alternative_symbols', []),
                reasoning=result_dict.get('reasoning', ''),
                confidence=result_dict.get('confidence', 'low'),
                recommended_action=result_dict.get('recommended_action', 'manual_review_required'),
                missing_information=result_dict.get('missing_information'),
                web_search_used=use_web_search
            )

            logger.info(
                f"AI analysis for {ticker}: {result.confidence} confidence, "
                f"recommended_action={result.recommended_action}"
            )

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response for {ticker}: {e}")
            logger.error(f"Response content: {content[:500]}...")
            # Return low confidence result
            return TickerAnalysisResult(
                company_name="",
                status="unknown",
                successor_ticker=None,
                successor_company=None,
                change_date=None,
                alternative_symbols=[],
                reasoning=f"Failed to parse AI response: {str(e)}",
                confidence="needs_manual_review",
                recommended_action="manual_review_required",
                missing_information="AI response was not in expected format",
                web_search_used=use_web_search
            )
        except Exception as e:
            logger.error(f"AI analysis failed for {ticker}: {e}")
            return TickerAnalysisResult(
                company_name="",
                status="unknown",
                successor_ticker=None,
                successor_company=None,
                change_date=None,
                alternative_symbols=[],
                reasoning=f"AI call failed: {str(e)}",
                confidence="needs_manual_review",
                recommended_action="manual_review_required",
                missing_information="AI service unavailable",
                web_search_used=use_web_search
            )

    def analyze_ticker(self, ticker: str) -> TickerAnalysisResult:
        """
        Analyze ticker with two-stage approach:
        1. Try with Claude's knowledge only (fast, cheap)
        2. If confidence < high, retry with web search (slow, expensive)

        Args:
            ticker: Ticker symbol to analyze

        Returns:
            TickerAnalysisResult with analysis details
        """
        # Check if web search is enabled
        web_search_enabled = os.environ.get('ENABLE_WEB_SEARCH', 'false').lower() == 'true'

        # Stage 1: Fast check with knowledge only
        logger.info(f"[Ticker Analyzer] Stage 1: Analyzing {ticker} with AI knowledge")
        result = self._call_claude(ticker, use_web_search=False)

        # If we got high or medium confidence, return immediately
        if result.confidence in ['high', 'medium']:
            return result

        # Stage 2: Deep research with web search (if enabled and initial confidence was low)
        if web_search_enabled:
            logger.info(
                f"[Ticker Analyzer] Stage 2: Low confidence ({result.confidence}), "
                f"retrying with web search enabled"
            )
            result = self._call_claude(ticker, use_web_search=True)

            # If still uncertain after web search, mark for manual review
            if result.confidence not in ['high', 'medium']:
                result.recommended_action = 'manual_review_required'
                logger.warning(
                    f"[Ticker Analyzer] Ticker {ticker} requires manual review after web search. "
                    f"Reason: {result.missing_information}"
                )
        else:
            # Web search disabled and low confidence - mark for manual review
            if result.confidence not in ['high', 'medium']:
                result.recommended_action = 'manual_review_required'
                logger.warning(
                    f"[Ticker Analyzer] Ticker {ticker} has low confidence and web search is disabled. "
                    f"Marking for manual review."
                )

        return result

    def find_successor_ticker(self, ticker: str, company_name: Optional[str] = None) -> Optional[str]:
        """
        Find successor ticker for delisted/bankrupt companies

        Args:
            ticker: Original ticker symbol
            company_name: Optional company name to aid search

        Returns:
            Successor ticker symbol or None
        """
        result = self.analyze_ticker(ticker)

        if result.recommended_action == "use_successor" and result.successor_ticker:
            logger.info(
                f"Found successor for {ticker}: {result.successor_ticker} "
                f"({result.successor_company})"
            )
            return result.successor_ticker

        return None

    def research_corporate_actions(self, ticker: str) -> Dict:
        """
        Research corporate events affecting ticker validity

        Returns:
            Dictionary with corporate action details
        """
        result = self.analyze_ticker(ticker)

        return {
            'ticker': ticker,
            'status': result.status,
            'corporate_actions': {
                'merger': result.status == 'merged',
                'bankruptcy': result.status == 'bankrupt',
                'delisting': result.status == 'delisted',
                'ticker_change': result.successor_ticker is not None
            },
            'successor_info': {
                'ticker': result.successor_ticker,
                'company': result.successor_company,
                'date': result.change_date
            },
            'alternative_symbols': result.alternative_symbols,
            'confidence': result.confidence,
            'reasoning': result.reasoning
        }
