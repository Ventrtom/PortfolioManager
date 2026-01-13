"""
Data Enricher Agent

AI agent that enriches stock data using Claude when traditional APIs have gaps.
Fills missing fields like sector, industry, and validates data consistency.
"""

import os
import json
import logging
from typing import Optional, List, Dict
from dataclasses import dataclass, asdict
from anthropic import Anthropic

logger = logging.getLogger(__name__)


@dataclass
class EnrichmentData:
    """Result of data enrichment"""
    sector: Optional[str]
    industry: Optional[str]
    market_cap: Optional[float]
    confidence: str  # 'high', 'medium', 'low'
    reasoning: str
    fields_filled: List[str]


class DataEnricherAgent:
    """
    AI agent that enriches stock data using Claude.
    Used when traditional APIs have gaps or failures.
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
        """Get best available model, prefer cheaper Haiku for simple enrichment"""
        if cls._available_model:
            return cls._available_model

        # For data enrichment, prefer cheaper models
        models_to_try = [
            "claude-3-5-haiku-20241022",     # Fast and cheap
            "claude-3-5-sonnet-20250219",    # Fallback
        ]

        client = cls._get_client()

        for model in models_to_try:
            try:
                client.messages.create(
                    model=model,
                    max_tokens=10,
                    messages=[{"role": "user", "content": "test"}]
                )
                logger.info(f"Data Enricher Agent using model: {model}")
                cls._available_model = model
                return model
            except Exception as e:
                if "404" in str(e) or "not_found" in str(e):
                    continue

        cls._available_model = "claude-3-5-sonnet-20250219"
        return cls._available_model

    def enrich_missing_fields(
        self,
        ticker: str,
        company_name: str,
        existing_data: dict
    ) -> EnrichmentData:
        """
        Fill missing sector, industry, market cap using AI knowledge.

        Args:
            ticker: Stock ticker symbol
            company_name: Company name (required for context)
            existing_data: Dict with existing fields (may have None values)

        Returns:
            EnrichmentData with filled fields
        """
        if not company_name:
            logger.warning("Cannot enrich without company name")
            return EnrichmentData(
                sector=None,
                industry=None,
                market_cap=None,
                confidence="low",
                reasoning="No company name provided",
                fields_filled=[]
            )

        try:
            client = self._get_client()
            model = self._get_available_model()

            # Identify missing fields
            missing_fields = []
            if not existing_data.get('sector'):
                missing_fields.append('sector')
            if not existing_data.get('industry'):
                missing_fields.append('industry')
            if not existing_data.get('market_cap'):
                missing_fields.append('market_cap')

            if not missing_fields:
                logger.info(f"No missing fields for {ticker}, skipping enrichment")
                return EnrichmentData(
                    sector=existing_data.get('sector'),
                    industry=existing_data.get('industry'),
                    market_cap=existing_data.get('market_cap'),
                    confidence="high",
                    reasoning="All fields already present",
                    fields_filled=[]
                )

            prompt = f"""You are a financial data analyst. Please fill in missing stock information.

Ticker: {ticker}
Company Name: {company_name}

Current Data:
- Sector: {existing_data.get('sector') or 'MISSING'}
- Industry: {existing_data.get('industry') or 'MISSING'}
- Market Cap: {existing_data.get('market_cap') or 'MISSING'}

Based on the company name and your knowledge, provide the missing fields.

Guidelines:
- For sector, use standard categories: Technology, Healthcare, Financial, Consumer, Industrial, Energy, etc.
- For industry, be more specific (e.g., "Software", "Biotechnology", "Commercial Banks")
- For market cap, provide your best estimate in millions USD (or null if truly unknown)
- Only provide data you're confident about

Respond with JSON:
{{
  "sector": "string or null",
  "industry": "string or null",
  "market_cap": number or null,
  "confidence": "high|medium|low",
  "reasoning": "brief explanation of your analysis"
}}"""

            response = client.messages.create(
                model=model,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text

            # Parse JSON
            if '```json' in content:
                json_str = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                json_str = content.split('```')[1].split('```')[0].strip()
            else:
                json_str = content.strip()

            result = json.loads(json_str)

            # Build enrichment result
            filled_fields = []
            if result.get('sector') and not existing_data.get('sector'):
                filled_fields.append('sector')
            if result.get('industry') and not existing_data.get('industry'):
                filled_fields.append('industry')
            if result.get('market_cap') and not existing_data.get('market_cap'):
                filled_fields.append('market_cap')

            enrichment = EnrichmentData(
                sector=result.get('sector') or existing_data.get('sector'),
                industry=result.get('industry') or existing_data.get('industry'),
                market_cap=result.get('market_cap') or existing_data.get('market_cap'),
                confidence=result.get('confidence', 'low'),
                reasoning=result.get('reasoning', ''),
                fields_filled=filled_fields
            )

            if filled_fields:
                logger.info(
                    f"AI enriched {ticker} ({company_name}): "
                    f"filled {', '.join(filled_fields)} with {enrichment.confidence} confidence"
                )
            else:
                logger.info(f"AI could not fill missing fields for {ticker}")

            return enrichment

        except Exception as e:
            logger.error(f"Data enrichment failed for {ticker}: {e}")
            return EnrichmentData(
                sector=existing_data.get('sector'),
                industry=existing_data.get('industry'),
                market_cap=existing_data.get('market_cap'),
                confidence="low",
                reasoning=f"Enrichment failed: {str(e)}",
                fields_filled=[]
            )

    def validate_data_consistency(
        self,
        ticker: str,
        provider_data: List[dict]
    ) -> Dict:
        """
        Validate conflicting data from multiple providers.
        AI makes judgment calls on which data is correct.

        Args:
            ticker: Stock ticker
            provider_data: List of data dicts from different providers

        Returns:
            Dict with validated/consensus data
        """
        if not provider_data or len(provider_data) < 2:
            # Nothing to validate
            return provider_data[0] if provider_data else {}

        try:
            client = self._get_client()
            model = self._get_available_model()

            # Compare data across providers
            prompt = f"""You are a financial data validator. Multiple data sources provided different information for ticker {ticker}.

Provider Data:
{json.dumps(provider_data, indent=2)}

Analyze the data and provide consensus values. When data conflicts:
1. Prefer data from more reliable sources (yfinance > others)
2. Use the most recent data
3. Prefer more complete data
4. Flag suspicious outliers

Respond with JSON:
{{
  "company_name": "consensus value",
  "sector": "consensus value",
  "industry": "consensus value",
  "market_cap": number or null,
  "confidence": "high|medium|low",
  "conflicts_found": ["list of conflicting fields"],
  "reasoning": "explanation of choices"
}}"""

            response = client.messages.create(
                model=model,
                max_tokens=700,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text

            # Parse JSON
            if '```json' in content:
                json_str = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                json_str = content.split('```')[1].split('```')[0].strip()
            else:
                json_str = content.strip()

            validated = json.loads(json_str)

            logger.info(
                f"Data validation for {ticker}: "
                f"{len(validated.get('conflicts_found', []))} conflicts resolved"
            )

            return validated

        except Exception as e:
            logger.error(f"Data validation failed for {ticker}: {e}")
            # Return first provider's data as fallback
            return provider_data[0]
