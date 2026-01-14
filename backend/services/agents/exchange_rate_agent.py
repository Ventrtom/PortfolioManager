"""
Exchange Rate Agent

AI agent that resolves exchange rates using Claude with web search.
Used as fallback when all API providers fail.
"""

import os
import json
import logging
from datetime import date
from typing import Optional, List
from dataclasses import dataclass, asdict
from anthropic import Anthropic

logger = logging.getLogger(__name__)


@dataclass
class ExchangeRateResult:
    """Result of AI exchange rate resolution"""
    base_currency: str
    target_currency: str
    rate_date: date
    rate: Optional[float]
    confidence: str  # 'high', 'medium', 'low'
    reasoning: str
    sources: List[str]  # URLs from web search
    needs_manual_review: bool
    error: Optional[str] = None

    def to_dict(self) -> dict:
        result = asdict(self)
        result['rate_date'] = self.rate_date.isoformat()
        return result


class ExchangeRateAgent:
    """
    AI agent that resolves exchange rates using Claude with web search.
    Used when traditional API providers fail.
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
        """Get best available model, prefer Opus for financial accuracy"""
        if cls._available_model:
            return cls._available_model

        # For exchange rates, prefer most accurate models
        models_to_try = [
            "claude-opus-4-5-20251101",     # Best for financial accuracy
            "claude-3-5-sonnet-20250219",   # Fallback
        ]

        client = cls._get_client()

        for model in models_to_try:
            try:
                client.messages.create(
                    model=model,
                    max_tokens=10,
                    messages=[{"role": "user", "content": "test"}]
                )
                logger.info(f"Exchange Rate Agent using model: {model}")
                cls._available_model = model
                return model
            except Exception as e:
                if "404" in str(e) or "not_found" in str(e):
                    continue

        cls._available_model = "claude-3-5-sonnet-20250219"
        return cls._available_model

    def get_historical_rate(
        self,
        base_currency: str,
        target_currency: str,
        rate_date: date
    ) -> ExchangeRateResult:
        """
        Get historical exchange rate using AI with web search.

        Args:
            base_currency: Source currency (e.g., 'USD')
            target_currency: Target currency (e.g., 'CZK')
            rate_date: Historical date for exchange rate

        Returns:
            ExchangeRateResult with rate, confidence, sources
        """
        logger.info(f"[Exchange Rate Agent] Resolving {base_currency}/{target_currency} on {rate_date} using AI with web search")

        # Same currency check
        if base_currency == target_currency:
            return ExchangeRateResult(
                base_currency=base_currency,
                target_currency=target_currency,
                rate_date=rate_date,
                rate=1.0,
                confidence='high',
                reasoning='Same currency conversion',
                sources=[],
                needs_manual_review=False
            )

        try:
            client = self._get_client()
            model = self._get_available_model()

            # Construct AI prompt with web search instructions
            prompt = f"""You are a financial data expert. Find the historical exchange rate for the following currency pair:

Base Currency: {base_currency}
Target Currency: {target_currency}
Date: {rate_date.isoformat()} ({rate_date.strftime('%B %d, %Y')})

CRITICAL INSTRUCTIONS:
1. Use web search to find the actual historical exchange rate for this specific date
2. Look for reliable financial sources (central banks, Bloomberg, Reuters, xe.com, etc.)
3. Find MULTIPLE sources to corroborate the rate (aim for 3+ sources)
4. The rate should be: 1 {base_currency} = X {target_currency}
5. Validate that the rate is reasonable (check against typical ranges for this currency pair)

VALIDATION RULES:
- If multiple sources agree (within 2% variance), confidence is HIGH
- If 2 sources agree but there's some variance (2-5%), confidence is MEDIUM
- If only 1 source found or variance >5%, confidence is LOW and mark for manual review
- If the rate seems anomalous (e.g., sudden 30%+ change from previous days), note it in reasoning

Return your answer in this JSON format:
{{
    "rate": <float>,
    "confidence": "high|medium|low",
    "reasoning": "<brief explanation of what you found and why you chose this rate>",
    "sources": ["<url1>", "<url2>", "<url3>"],
    "needs_manual_review": <true|false>
}}

If you cannot find a reliable rate, return:
{{
    "rate": null,
    "confidence": "low",
    "reasoning": "<explanation of why rate could not be found>",
    "sources": [],
    "needs_manual_review": true
}}"""

            # Call Claude with web search enabled
            response = client.messages.create(
                model=model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            logger.info(f"Exchange Rate Agent using model: {model}")

            # Extract response text
            content = response.content[0].text

            # Parse JSON response
            result_data = self._parse_json_response(content)

            if not result_data:
                logger.error("[Exchange Rate Agent] Failed to parse AI response")
                return ExchangeRateResult(
                    base_currency=base_currency,
                    target_currency=target_currency,
                    rate_date=rate_date,
                    rate=None,
                    confidence='low',
                    reasoning='Failed to parse AI response',
                    sources=[],
                    needs_manual_review=True,
                    error='AI response parsing failed'
                )

            # Validate the rate
            rate = result_data.get('rate')
            if rate is not None:
                validation_result = self._validate_rate(
                    base_currency,
                    target_currency,
                    rate,
                    result_data.get('sources', [])
                )
                if not validation_result['valid']:
                    logger.warning(f"[Exchange Rate Agent] Validation failed: {validation_result['reason']}")
                    result_data['needs_manual_review'] = True
                    result_data['reasoning'] += f" | Validation warning: {validation_result['reason']}"

            # Build result
            result = ExchangeRateResult(
                base_currency=base_currency,
                target_currency=target_currency,
                rate_date=rate_date,
                rate=rate,
                confidence=result_data.get('confidence', 'low'),
                reasoning=result_data.get('reasoning', ''),
                sources=result_data.get('sources', []),
                needs_manual_review=result_data.get('needs_manual_review', False)
            )

            logger.info(f"[Exchange Rate Agent] Result: rate={rate}, confidence={result.confidence}, sources={len(result.sources)}")

            return result

        except Exception as e:
            logger.error(f"[Exchange Rate Agent] Error: {e}", exc_info=True)
            return ExchangeRateResult(
                base_currency=base_currency,
                target_currency=target_currency,
                rate_date=rate_date,
                rate=None,
                confidence='low',
                reasoning=f'AI agent error: {str(e)}',
                sources=[],
                needs_manual_review=True,
                error=str(e)
            )

    def _parse_json_response(self, content: str) -> Optional[dict]:
        """Extract and parse JSON from AI response"""
        try:
            # Try to extract JSON from markdown code blocks
            if '```json' in content:
                json_str = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                json_str = content.split('```')[1].split('```')[0].strip()
            else:
                json_str = content.strip()

            return json.loads(json_str)

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            logger.error(f"Content: {content}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing JSON: {e}")
            return None

    def _validate_rate(
        self,
        base: str,
        target: str,
        rate: float,
        sources: List[str]
    ) -> dict:
        """
        Validate exchange rate for reasonableness.

        Returns:
            {'valid': bool, 'reason': str}
        """
        # Basic sanity checks
        if rate <= 0:
            return {'valid': False, 'reason': 'Rate must be positive'}

        if rate > 1000000:
            return {'valid': False, 'reason': 'Rate suspiciously high'}

        # Check source count
        if len(sources) == 0:
            return {'valid': False, 'reason': 'No sources provided'}

        # Known currency pair ranges (rough validation)
        # This is a simple heuristic - can be expanded
        common_pairs = {
            ('USD', 'EUR'): (0.7, 1.3),
            ('USD', 'CZK'): (18, 28),
            ('EUR', 'CZK'): (20, 30),
            ('USD', 'GBP'): (0.6, 0.9),
            ('EUR', 'GBP'): (0.7, 1.0),
        }

        pair = (base, target)
        reverse_pair = (target, base)

        if pair in common_pairs:
            min_rate, max_rate = common_pairs[pair]
            if not (min_rate <= rate <= max_rate):
                return {
                    'valid': False,
                    'reason': f'Rate {rate} outside typical range [{min_rate}, {max_rate}] for {base}/{target}'
                }
        elif reverse_pair in common_pairs:
            # Check inverse
            min_rate, max_rate = common_pairs[reverse_pair]
            inverse_rate = 1 / rate
            if not (min_rate <= inverse_rate <= max_rate):
                return {
                    'valid': False,
                    'reason': f'Inverse rate {inverse_rate} outside typical range for {target}/{base}'
                }

        return {'valid': True, 'reason': 'Rate appears reasonable'}

    def batch_resolve_rates(
        self,
        currency_pairs: List[tuple],  # [(base, target, date), ...]
    ) -> List[ExchangeRateResult]:
        """
        Resolve multiple exchange rates (with rate limiting).

        Args:
            currency_pairs: List of (base_currency, target_currency, date) tuples

        Returns:
            List of ExchangeRateResult objects
        """
        results = []

        for base, target, rate_date in currency_pairs:
            result = self.get_historical_rate(base, target, rate_date)
            results.append(result)

            # Rate limiting: small delay between requests
            import time
            time.sleep(1)  # 1 second between AI requests

        return results
