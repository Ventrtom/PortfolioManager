"""
Stock Enrichment Service
Orchestrates automatic data enrichment for stocks
"""
import json
import logging
from datetime import datetime
from typing import Optional, Dict
from sqlalchemy.orm import Session
from models.database import Stock
from services.multi_provider_data_service import MultiProviderDataService
from services.ticker_resolution_service import TickerResolutionService

logger = logging.getLogger(__name__)

# Initialize multi-provider service once
multi_provider_service = MultiProviderDataService()

class EnrichmentService:
    """Orchestrate stock data enrichment"""

    @staticmethod
    def enrich_stock(ticker: str, db: Session) -> Dict[str, any]:
        """
        Enrich stock with data from yfinance + AI resolution

        Returns: {
            'success': bool,
            'status': 'complete' | 'failed',
            'data': dict or None,
            'error': str or None
        }
        """
        stock = db.query(Stock).filter(Stock.ticker == ticker).first()

        if not stock:
            return {'success': False, 'status': 'failed', 'data': None, 'error': 'Stock not found'}

        # Update status to in_progress
        stock.enrichment_status = 'in_progress'
        stock.enrichment_attempts += 1
        stock.last_enrichment_attempt = datetime.utcnow()
        db.commit()

        try:
            # Step 1: Try ticker resolution
            resolution = TickerResolutionService.resolve_ticker(ticker)

            if not resolution['success']:
                # All methods failed
                stock.enrichment_status = 'failed'
                stock.enrichment_error = f"Could not resolve ticker via any method"
                db.commit()

                return {
                    'success': False,
                    'status': 'failed',
                    'data': None,
                    'error': stock.enrichment_error
                }

            # Step 2: Fetch data with resolved symbol using multi-provider service
            working_symbol = resolution['resolved_symbol']
            logger.info(f"Resolved {ticker} → {working_symbol} via {resolution['method']}")

            # Try to fetch stock info from multiple providers
            stock_info = multi_provider_service.get_stock_info(working_symbol, db)

            if not stock_info or not stock_info.get('company_name'):
                # All providers failed
                stock.enrichment_status = 'failed'
                stock.enrichment_error = f"All data providers failed for {working_symbol}"
                db.commit()

                return {
                    'success': False,
                    'status': 'failed',
                    'data': None,
                    'error': stock.enrichment_error
                }

            # Extract data from provider response
            logger.info(f"Successfully fetched data for {working_symbol} from {stock_info.get('provider', 'unknown')}")

            market_cap = stock_info.get('market_cap')
            volume = stock_info.get('volume')

            # Step 4: Update stock record
            stock.company_name = stock_info.get('company_name')
            stock.sector = stock_info.get('sector')
            stock.industry = stock_info.get('industry')
            stock.currency = stock_info.get('currency', 'USD')
            stock.market_cap = market_cap
            stock.volume = volume
            stock.last_updated = datetime.utcnow()

            # Store alternative symbols if different from original
            if working_symbol != ticker or resolution['alternative_symbols']:
                stock.alternative_symbols = json.dumps(resolution['alternative_symbols'])

            stock.enrichment_status = 'complete'
            stock.enrichment_error = None

            db.commit()

            logger.info(f"Successfully enriched {ticker} (using {working_symbol})")

            return {
                'success': True,
                'status': 'complete',
                'data': {
                    'company_name': stock.company_name,
                    'sector': stock.sector,
                    'industry': stock.industry,
                    'market_cap': stock.market_cap,
                    'volume': stock.volume,
                    'resolved_symbol': working_symbol,
                    'method': resolution['method']
                },
                'error': None
            }

        except Exception as e:
            logger.error(f"Enrichment failed for {ticker}: {e}")

            stock.enrichment_status = 'failed'
            stock.enrichment_error = str(e)
            db.commit()

            return {
                'success': False,
                'status': 'failed',
                'data': None,
                'error': str(e)
            }
