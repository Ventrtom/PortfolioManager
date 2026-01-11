"""
Ticker Resolution Service
Uses AI (Claude API) to resolve alternative ticker symbols when yfinance fails
"""
import os
import json
import logging
from typing import Optional, List, Dict
from anthropic import Anthropic

logger = logging.getLogger(__name__)

class TickerResolutionService:
    """AI-powered ticker symbol resolution"""

    # Initialize Claude API client (lazy)
    _client: Optional[Anthropic] = None

    @classmethod
    def _get_client(cls) -> Anthropic:
        """Get or create Anthropic client"""
        if cls._client is None:
            api_key = os.environ.get('ANTHROPIC_API_KEY')
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable not set")
            cls._client = Anthropic(api_key=api_key)
        return cls._client

    @staticmethod
    def generate_ticker_variations(ticker: str) -> List[str]:
        """
        Generate common ticker variations
        Example: GEO.US → [GEO, GEO:US, GEO-US, GEO.NYSE]
        """
        variations = [ticker]  # Include original

        # Remove common suffixes
        if '.' in ticker:
            base = ticker.split('.')[0]
            variations.append(base)

            # Try different exchange formats
            variations.append(f"{base}:US")
            variations.append(f"{base}-US")
            variations.append(f"{base}.NYSE")
            variations.append(f"{base}.NASDAQ")

        # Remove hyphens/colons
        if '-' in ticker or ':' in ticker:
            clean = ticker.replace('-', '').replace(':', '')
            variations.append(clean)

        return list(dict.fromkeys(variations))  # Remove duplicates, preserve order

    @classmethod
    def resolve_with_ai(cls, ticker: str) -> Optional[Dict[str, any]]:
        """
        Use Claude API to research ticker and find alternative symbols
        Returns: {
            'alternative_symbols': ['GEO', 'GEO:NYSE'],
            'company_name': 'GEO Group Inc.',
            'confidence': 'high' | 'medium' | 'low'
        }
        """
        try:
            client = cls._get_client()

            prompt = f"""Research the stock ticker symbol "{ticker}" and help resolve it.

This ticker may be a broker-specific format (e.g., "GEO.US") that doesn't work with standard APIs like yfinance.

Please provide:
1. The most likely standard ticker symbol(s) used by major exchanges
2. The company's full name
3. Your confidence level in this answer

Respond ONLY with valid JSON in this exact format:
{{
    "alternative_symbols": ["TICKER1", "TICKER2"],
    "company_name": "Company Name Inc.",
    "confidence": "high|medium|low",
    "reasoning": "Brief explanation"
}}

If you cannot determine the ticker with reasonable confidence, respond with:
{{
    "alternative_symbols": [],
    "company_name": null,
    "confidence": "none",
    "reasoning": "Could not identify this ticker"
}}"""

            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=500,
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

            result = json.loads(json_str)

            logger.info(f"AI resolution for {ticker}: {result['confidence']} confidence, "
                       f"{len(result.get('alternative_symbols', []))} symbols found")

            return result if result['confidence'] != 'none' else None

        except Exception as e:
            logger.error(f"AI resolution failed for {ticker}: {e}")
            return None

    @classmethod
    def resolve_ticker(cls, ticker: str) -> Dict[str, any]:
        """
        3-tier ticker resolution:
        1. Try original ticker with multi-provider fallback
        2. Try common variations with multi-provider fallback
        3. Use AI to research

        Returns: {
            'success': bool,
            'resolved_symbol': str or None,
            'alternative_symbols': List[str],
            'method': 'direct' | 'variation' | 'ai' | 'failed',
            'ai_data': dict or None
        }
        """
        from services.multi_provider_data_service import MultiProviderDataService
        from models.database import SessionLocal

        db = SessionLocal()
        multi_provider = MultiProviderDataService()

        try:
            # Tier 1: Try original ticker with all providers
            logger.info(f"[Tier 1] Trying original ticker: {ticker}")
            stock_info = multi_provider.get_stock_info(ticker, db)
            if stock_info and stock_info.get('company_name'):
                return {
                    'success': True,
                    'resolved_symbol': ticker,
                    'alternative_symbols': [ticker],
                    'method': 'direct',
                    'ai_data': None
                }

            # Tier 2: Try variations with all providers
            variations = cls.generate_ticker_variations(ticker)
            logger.info(f"[Tier 2] Trying {len(variations)} variations: {variations}")

            for variant in variations:
                if variant == ticker:  # Skip original (already tried)
                    continue

                logger.info(f"  Trying variation: {variant}")
                stock_info = multi_provider.get_stock_info(variant, db)

                if stock_info and stock_info.get('company_name'):
                    # Success - found a working variation
                    return {
                        'success': True,
                        'resolved_symbol': variant,
                        'alternative_symbols': [variant],
                        'method': 'variation',
                        'ai_data': None
                    }

            # Tier 3: Use AI only if API key is available
            api_key = os.environ.get('ANTHROPIC_API_KEY')
            if not api_key:
                logger.warning(f"[Tier 3] Skipping AI resolution - ANTHROPIC_API_KEY not set")
                return {
                    'success': False,
                    'resolved_symbol': None,
                    'alternative_symbols': [],
                    'method': 'failed',
                    'ai_data': None
                }

            logger.info(f"[Tier 3] Using AI to resolve ticker: {ticker}")
            ai_result = cls.resolve_with_ai(ticker)

            if ai_result and ai_result['alternative_symbols']:
                # Try each AI-suggested symbol with all providers
                for symbol in ai_result['alternative_symbols']:
                    logger.info(f"  Trying AI suggestion: {symbol}")
                    stock_info = multi_provider.get_stock_info(symbol, db)

                    if stock_info and stock_info.get('company_name'):
                        return {
                            'success': True,
                            'resolved_symbol': symbol,
                            'alternative_symbols': ai_result['alternative_symbols'],
                            'method': 'ai',
                            'ai_data': ai_result
                        }

            # All methods failed
            return {
                'success': False,
                'resolved_symbol': None,
                'alternative_symbols': [],
                'method': 'failed',
                'ai_data': ai_result
            }

        finally:
            db.close()
