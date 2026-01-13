"""
AI Orchestrator

Coordinates multiple AI agents and data sources for intelligent stock enrichment.
Routes requests based on context and aggregates results.
"""

import logging
from typing import Optional, Dict
from datetime import datetime
from sqlalchemy.orm import Session
from dataclasses import dataclass, asdict

from services.agents.ticker_analyzer_agent import TickerAnalyzerAgent
from services.agents.data_enricher_agent import DataEnricherAgent
from services.multi_provider_data_service import MultiProviderDataService
from services.ticker_resolution_service import TickerResolutionService

logger = logging.getLogger(__name__)


@dataclass
class EnrichmentResult:
    """Result of intelligent stock enrichment"""
    success: bool
    status: str  # 'complete', 'partial', 'failed', 'manual'
    company_name: Optional[str]
    sector: Optional[str]
    industry: Optional[str]
    market_cap: Optional[float]
    volume: Optional[int]
    currency: str
    resolved_symbol: Optional[str]
    alternative_symbols: list
    resolution_method: str
    ai_enrichment_used: bool
    ai_confidence: Optional[str]
    needs_manual_review: bool
    error: Optional[str]

    def to_dict(self) -> dict:
        return asdict(self)


class AIOrchestrator:
    """
    Coordinates multiple AI agents and data sources.
    Intelligently routes requests based on context.
    """

    def __init__(self):
        self.ticker_analyzer = TickerAnalyzerAgent()
        self.data_enricher = DataEnricherAgent()
        self.multi_provider = MultiProviderDataService()

    def enrich_stock_intelligent(
        self,
        ticker: str,
        db: Session
    ) -> EnrichmentResult:
        """
        Intelligent stock enrichment with AI coordination.

        Flow:
        1. Resolve ticker symbol (with AI if needed)
        2. Fetch data from providers
        3. Use AI to fill gaps in data
        4. Validate and aggregate results

        Args:
            ticker: Stock ticker symbol
            db: Database session

        Returns:
            EnrichmentResult with complete data or failure info
        """
        logger.info(f"[AI Orchestrator] Starting intelligent enrichment for {ticker}")

        # Step 1: Ticker resolution
        resolution = TickerResolutionService.resolve_ticker(ticker)

        if not resolution['success']:
            # Check if manual review needed
            if resolution.get('needs_manual_review'):
                return EnrichmentResult(
                    success=False,
                    status='manual',
                    company_name=None,
                    sector=None,
                    industry=None,
                    market_cap=None,
                    volume=None,
                    currency='USD',
                    resolved_symbol=None,
                    alternative_symbols=resolution.get('alternative_symbols', []),
                    resolution_method=resolution['method'],
                    ai_enrichment_used=False,
                    ai_confidence=None,
                    needs_manual_review=True,
                    error=resolution.get('manual_review_reason', 'Ticker resolution failed')
                )
            else:
                return EnrichmentResult(
                    success=False,
                    status='failed',
                    company_name=None,
                    sector=None,
                    industry=None,
                    market_cap=None,
                    volume=None,
                    currency='USD',
                    resolved_symbol=None,
                    alternative_symbols=[],
                    resolution_method=resolution['method'],
                    ai_enrichment_used=False,
                    ai_confidence=None,
                    needs_manual_review=False,
                    error='Could not resolve ticker'
                )

        working_symbol = resolution['resolved_symbol']
        logger.info(f"[AI Orchestrator] Resolved {ticker} → {working_symbol} via {resolution['method']}")

        # Step 2: Fetch data from providers
        stock_info = self.multi_provider.get_stock_info(working_symbol, db)

        if not stock_info or not stock_info.get('company_name'):
            # Providers failed completely
            logger.warning(f"[AI Orchestrator] All providers failed for {working_symbol}")
            return EnrichmentResult(
                success=False,
                status='failed',
                company_name=None,
                sector=None,
                industry=None,
                market_cap=None,
                volume=None,
                currency='USD',
                resolved_symbol=working_symbol,
                alternative_symbols=resolution.get('alternative_symbols', []),
                resolution_method=resolution['method'],
                ai_enrichment_used=False,
                ai_confidence=None,
                needs_manual_review=True,
                error=f'All data providers failed for {working_symbol}'
            )

        # Step 3: Check if AI enrichment needed for gaps
        has_gaps = not all([
            stock_info.get('sector'),
            stock_info.get('industry'),
            stock_info.get('market_cap')
        ])

        ai_enrichment_used = False
        ai_confidence = None

        if has_gaps:
            logger.info(f"[AI Orchestrator] Data gaps detected for {working_symbol}, using AI enrichment")

            # Use AI to fill missing fields
            enrichment = self.data_enricher.enrich_missing_fields(
                ticker=working_symbol,
                company_name=stock_info['company_name'],
                existing_data=stock_info
            )

            # Merge AI enrichment with provider data
            if enrichment.fields_filled:
                stock_info['sector'] = enrichment.sector or stock_info.get('sector')
                stock_info['industry'] = enrichment.industry or stock_info.get('industry')
                stock_info['market_cap'] = enrichment.market_cap or stock_info.get('market_cap')

                ai_enrichment_used = True
                ai_confidence = enrichment.confidence

                logger.info(
                    f"[AI Orchestrator] AI filled fields: {', '.join(enrichment.fields_filled)} "
                    f"with {ai_confidence} confidence"
                )

        # Step 4: Determine final status
        has_company_name = bool(stock_info.get('company_name'))
        has_some_data = any([
            stock_info.get('sector'),
            stock_info.get('industry'),
            stock_info.get('market_cap')
        ])

        if has_company_name and has_some_data:
            status = 'complete' if all([
                stock_info.get('sector'),
                stock_info.get('industry')
            ]) else 'partial'
        else:
            status = 'failed'

        result = EnrichmentResult(
            success=has_company_name,
            status=status,
            company_name=stock_info.get('company_name'),
            sector=stock_info.get('sector'),
            industry=stock_info.get('industry'),
            market_cap=stock_info.get('market_cap'),
            volume=stock_info.get('volume'),
            currency=stock_info.get('currency', 'USD'),
            resolved_symbol=working_symbol,
            alternative_symbols=resolution.get('alternative_symbols', []),
            resolution_method=resolution['method'],
            ai_enrichment_used=ai_enrichment_used,
            ai_confidence=ai_confidence,
            needs_manual_review=False,
            error=None
        )

        logger.info(
            f"[AI Orchestrator] Enrichment complete for {ticker}: "
            f"status={status}, ai_used={ai_enrichment_used}"
        )

        return result

    def get_enrichment_strategy(self, ticker: str) -> Dict:
        """
        Analyze ticker and recommend enrichment strategy.
        Useful for bulk operations to optimize cost/speed.

        Returns:
            {
                'strategy': 'fast'|'standard'|'deep',
                'estimated_cost': float,
                'estimated_time_sec': float,
                'reasoning': str
            }
        """
        # Simple heuristic based on ticker format
        if '.' in ticker or ':' in ticker or '-' in ticker:
            # Broker-specific format, likely needs AI
            return {
                'strategy': 'deep',
                'estimated_cost': 0.015,
                'estimated_time_sec': 8.0,
                'reasoning': 'Non-standard ticker format requires AI resolution'
            }
        elif len(ticker) <= 4 and ticker.isalpha():
            # Standard US ticker
            return {
                'strategy': 'fast',
                'estimated_cost': 0.0,
                'estimated_time_sec': 2.0,
                'reasoning': 'Standard ticker, providers should handle'
            }
        else:
            # Uncertain, use standard approach
            return {
                'strategy': 'standard',
                'estimated_cost': 0.005,
                'estimated_time_sec': 5.0,
                'reasoning': 'May need AI assistance'
            }
