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

    # Cache for the best available model
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
        Caches the result to avoid repeated API calls
        Priority: opus-4.5 > sonnet-3.5 (latest) > haiku (fallback)
        """
        if cls._available_model:
            return cls._available_model

        models_to_try = [
            "claude-opus-4-5-20251101",      # Latest, most capable (if available)
            "claude-3-5-sonnet-20250219",    # Fast and capable
            "claude-3-5-haiku-20241022",     # Cheaper fallback
        ]

        client = cls._get_client()

        for model in models_to_try:
            try:
                # Test model availability with minimal call
                client.messages.create(
                    model=model,
                    max_tokens=10,
                    messages=[{"role": "user", "content": "test"}]
                )
                logger.info(f"Using Claude model for ticker resolution: {model}")
                cls._available_model = model
                return model
            except Exception as e:
                error_str = str(e)
                if "404" in error_str or "not_found" in error_str:
                    logger.warning(f"Model {model} not available, trying next...")
                    continue
                else:
                    # Other error - might be rate limit, network issue, etc.
                    logger.error(f"Error testing model {model}: {e}")
                    # Still try the next model
                    continue

        raise ValueError(f"No available Claude models found. Tried: {models_to_try}")

    @staticmethod
    def generate_ticker_variations(ticker: str) -> List[str]:
        """
        Generate common ticker variations
        Example: GEO.US → [GEO, GEO:US, GEO-US, GEO.NYSE]
        Example: IUIT.UK → [IUIT.UK, IUIT.L, IUIT, IUIT.LSE]
        """
        variations = [ticker]  # Include original
        ticker_upper = ticker.upper()

        # UK/European ETF format conversions
        # Users often input .UK but Yahoo Finance uses .L for London
        uk_eu_suffixes = {
            '.UK': ['.L', '.LSE'],      # UK -> London Stock Exchange
            '.LON': ['.L', '.LSE'],     # London variant
            '.LSE': ['.L'],             # LSE -> Yahoo format
        }

        for old_suffix, new_suffixes in uk_eu_suffixes.items():
            if ticker_upper.endswith(old_suffix):
                base = ticker[:-len(old_suffix)]
                for new_suffix in new_suffixes:
                    variations.append(f"{base}{new_suffix}")
                variations.append(base)  # Also try without suffix
                break

        # If ticker ends with .L (Yahoo London format), also try EODHD format
        if ticker_upper.endswith('.L'):
            base = ticker[:-2]
            variations.append(f"{base}.LSE")
            variations.append(base)

        # Remove common US suffixes
        if '.' in ticker:
            base = ticker.split('.')[0]
            if base not in variations:
                variations.append(base)

            # Try different US exchange formats
            variations.append(f"{base}:US")
            variations.append(f"{base}-US")
            variations.append(f"{base}.NYSE")
            variations.append(f"{base}.NASDAQ")

        # If no suffix and short ticker (likely ETF), try London formats
        if '.' not in ticker and len(ticker) <= 5:
            variations.append(f"{ticker}.L")    # Yahoo Finance London
            variations.append(f"{ticker}.LSE")  # EODHD London

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

            # Use dynamic model selection with fallback
            model = cls._get_available_model()
            response = client.messages.create(
                model=model,
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

            # Tier 3: Use AI Ticker Analyzer Agent
            api_key = os.environ.get('ANTHROPIC_API_KEY')
            if not api_key:
                logger.warning(f"[Tier 3] Skipping AI resolution - ANTHROPIC_API_KEY not set")
                return {
                    'success': False,
                    'resolved_symbol': None,
                    'alternative_symbols': [],
                    'method': 'failed',
                    'ai_data': None,
                    'needs_manual_review': True,
                    'manual_review_reason': 'All providers failed and AI is not configured'
                }

            logger.info(f"[Tier 3] Using AI Ticker Analyzer Agent: {ticker}")
            from services.agents.ticker_analyzer_agent import TickerAnalyzerAgent

            analyzer = TickerAnalyzerAgent()
            analysis = analyzer.analyze_ticker(ticker)

            # Check if AI recommends using a successor ticker
            if analysis.recommended_action == "use_successor" and analysis.successor_ticker:
                successor = analysis.successor_ticker
                logger.info(f"  AI identified successor ticker: {successor} ({analysis.successor_company})")

                # Try successor ticker
                stock_info = multi_provider.get_stock_info(successor, db)

                if stock_info and stock_info.get('company_name'):
                    return {
                        'success': True,
                        'resolved_symbol': successor,
                        'alternative_symbols': analysis.alternative_symbols,
                        'method': 'ai_successor',
                        'ai_data': analysis.to_dict(),
                        'note': f"Original ticker {ticker} resolved to successor {successor}"
                    }

            # Try all alternative symbols suggested by AI
            if analysis.alternative_symbols:
                for symbol in analysis.alternative_symbols:
                    logger.info(f"  Trying AI suggested symbol: {symbol}")
                    stock_info = multi_provider.get_stock_info(symbol, db)

                    if stock_info and stock_info.get('company_name'):
                        return {
                            'success': True,
                            'resolved_symbol': symbol,
                            'alternative_symbols': analysis.alternative_symbols,
                            'method': 'ai',
                            'ai_data': analysis.to_dict()
                        }

            # Check if manual review is required
            if analysis.recommended_action == 'manual_review_required':
                logger.warning(f"[Tier 3] Ticker {ticker} marked for manual review by AI")
                return {
                    'success': False,
                    'resolved_symbol': None,
                    'alternative_symbols': analysis.alternative_symbols,
                    'method': 'failed',
                    'ai_data': analysis.to_dict(),
                    'needs_manual_review': True,
                    'manual_review_reason': analysis.missing_information or 'AI could not resolve with confidence'
                }

            # All methods failed
            return {
                'success': False,
                'resolved_symbol': None,
                'alternative_symbols': analysis.alternative_symbols,
                'method': 'failed',
                'ai_data': analysis.to_dict(),
                'needs_manual_review': analysis.confidence not in ['high', 'medium'],
                'manual_review_reason': 'No working symbols found'
            }

        finally:
            db.close()
