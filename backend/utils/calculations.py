import numpy as np
from typing import List, Dict, Optional
from datetime import date
from collections import defaultdict


class DataFrequencyDetector:
    """Detect time series data frequency for correct annualization"""

    @staticmethod
    def detect_frequency(dates: List[date]) -> Dict:
        """
        Detect data frequency from date series.

        Args:
            dates: List of dates in the time series

        Returns:
            {
                'frequency': 'daily' | 'weekly' | 'monthly' | 'unknown',
                'periods_per_year': int,
                'avg_gap_days': float,
                'sample_size': int,
                'confidence': 'high' | 'medium' | 'low'
            }
        """
        if len(dates) < 2:
            return {
                'frequency': 'unknown',
                'periods_per_year': 252,  # Default to daily
                'avg_gap_days': 1,
                'sample_size': len(dates),
                'confidence': 'low'
            }

        # Calculate gaps between consecutive dates
        sorted_dates = sorted(dates)
        gaps = [(sorted_dates[i+1] - sorted_dates[i]).days for i in range(len(sorted_dates) - 1)]

        # Remove zeros (duplicate dates)
        gaps = [g for g in gaps if g > 0]

        if not gaps:
            return {
                'frequency': 'unknown',
                'periods_per_year': 252,
                'avg_gap_days': 0,
                'sample_size': 0,
                'confidence': 'low'
            }

        avg_gap = np.mean(gaps)
        std_gap = np.std(gaps)

        # Determine frequency based on average gap
        if avg_gap <= 1.5:
            frequency = 'daily'
            periods_per_year = 252  # Trading days
        elif 5 <= avg_gap <= 9:
            frequency = 'weekly'
            periods_per_year = 52
        elif 28 <= avg_gap <= 33:
            frequency = 'monthly'
            periods_per_year = 12
        else:
            frequency = 'unknown'
            # Estimate periods per year
            periods_per_year = max(1, int(365 / avg_gap))

        # Confidence based on consistency (low std = high confidence)
        # Made more lenient - weekly data with weekend gaps is normal
        if std_gap < avg_gap * 0.5:
            confidence = 'high'
        elif std_gap < avg_gap * 0.8:
            confidence = 'medium'
        else:
            confidence = 'low'

        return {
            'frequency': frequency,
            'periods_per_year': periods_per_year,
            'avg_gap_days': float(avg_gap),
            'sample_size': len(gaps),
            'confidence': confidence
        }


class FinancialCalculations:
    """Helper functions for financial calculations"""

    @staticmethod
    def calculate_fifo_cost_basis(purchases: List[Dict], quantity_to_sell: float) -> tuple:
        """
        Calculate cost basis using FIFO (First In, First Out) method
        Returns (cost_basis, remaining_purchases)

        purchases: List of dicts with 'quantity' and 'price' keys
        quantity_to_sell: Number of shares to sell
        """
        total_cost = 0
        remaining_quantity = quantity_to_sell
        remaining_purchases = []

        for purchase in purchases:
            if remaining_quantity <= 0:
                remaining_purchases.append(purchase.copy())
                continue

            if purchase['quantity'] <= remaining_quantity:
                # Use entire purchase
                total_cost += purchase['quantity'] * purchase['price']
                remaining_quantity -= purchase['quantity']
            else:
                # Use partial purchase
                total_cost += remaining_quantity * purchase['price']
                # Keep the unused portion - preserve all fields including transaction_id
                partial_purchase = {
                    'quantity': purchase['quantity'] - remaining_quantity,
                    'price': purchase['price'],
                    'date': purchase['date']
                }
                # Preserve transaction_id if it exists (for FIFO lot tracking)
                if 'transaction_id' in purchase:
                    partial_purchase['transaction_id'] = purchase['transaction_id']
                # Preserve cost_czk if it exists (for CZK cost tracking)
                if 'cost_czk' in purchase:
                    # Proportional CZK cost for remaining shares
                    remaining_ratio = (purchase['quantity'] - remaining_quantity) / purchase['quantity']
                    partial_purchase['cost_czk'] = purchase['cost_czk'] * remaining_ratio
                remaining_purchases.append(partial_purchase)
                remaining_quantity = 0

        cost_basis = total_cost
        return cost_basis, remaining_purchases

    @staticmethod
    def calculate_fifo_cost_basis_czk(purchases: List[Dict], quantity_to_sell: float) -> tuple:
        """
        Calculate cost basis in CZK using FIFO (First In, First Out) method.
        Returns (cost_basis_czk, remaining_purchases)

        This version tracks CZK cost (normalized at transaction date) instead of
        native currency cost, which is essential for correct multi-currency
        portfolio calculations.

        purchases: List of dicts with 'quantity', 'price', and 'cost_czk' keys
                   'cost_czk' is the CZK-normalized cost for the entire lot
        quantity_to_sell: Number of shares to sell
        """
        total_cost_czk = 0.0
        remaining_quantity = quantity_to_sell
        remaining_purchases = []

        for purchase in purchases:
            if remaining_quantity <= 0:
                remaining_purchases.append(purchase.copy())
                continue

            # Get CZK cost per share for this lot
            lot_quantity = purchase['quantity']
            lot_cost_czk = purchase.get('cost_czk', 0)
            cost_per_share_czk = lot_cost_czk / lot_quantity if lot_quantity > 0 else 0

            if lot_quantity <= remaining_quantity:
                # Use entire purchase
                total_cost_czk += lot_cost_czk
                remaining_quantity -= lot_quantity
            else:
                # Use partial purchase
                used_quantity = remaining_quantity
                used_cost_czk = cost_per_share_czk * used_quantity
                total_cost_czk += used_cost_czk

                # Keep the unused portion
                remaining_lot_quantity = lot_quantity - used_quantity
                remaining_lot_cost_czk = cost_per_share_czk * remaining_lot_quantity

                partial_purchase = {
                    'quantity': remaining_lot_quantity,
                    'price': purchase['price'],
                    'cost_czk': remaining_lot_cost_czk,
                    'date': purchase['date']
                }
                # Preserve transaction_id if it exists
                if 'transaction_id' in purchase:
                    partial_purchase['transaction_id'] = purchase['transaction_id']
                remaining_purchases.append(partial_purchase)
                remaining_quantity = 0

        return total_cost_czk, remaining_purchases

    @staticmethod
    def calculate_returns(initial_value: float, final_value: float) -> Dict:
        """
        Calculate absolute and percentage returns
        Returns dict with 'absolute_return' and 'percent_return'
        """
        if initial_value == 0:
            return {'absolute_return': 0, 'percent_return': 0}

        absolute_return = final_value - initial_value
        percent_return = (absolute_return / initial_value) * 100

        return {
            'absolute_return': absolute_return,
            'percent_return': percent_return
        }

    @staticmethod
    def calculate_volatility(prices: List[float], dates: Optional[List[date]] = None) -> Dict:
        """
        Calculate volatility metrics from price series with automatic frequency detection.

        Args:
            prices: List of portfolio values or prices
            dates: Optional list of dates (for frequency detection)

        Returns:
            {
                'daily_volatility': float,
                'annualized_volatility': float,
                'frequency': str,
                'periods_per_year': int,
                'data_quality': str
            }
        """
        if len(prices) < 2:
            return {
                'daily_volatility': 0,
                'annualized_volatility': 0,
                'frequency': 'unknown',
                'periods_per_year': 0,
                'data_quality': 'insufficient'
            }

        # Detect frequency if dates provided
        freq_info = None
        if dates and len(dates) == len(prices):
            freq_info = DataFrequencyDetector.detect_frequency(dates)

        # Default to daily if no dates provided
        periods_per_year = freq_info['periods_per_year'] if freq_info else 252

        # Calculate returns
        prices_array = np.array(prices)

        # Filter out zero and NaN values
        valid_prices = prices_array[~np.isnan(prices_array) & (prices_array > 0)]

        if len(valid_prices) < 2:
            return {
                'daily_volatility': 0,
                'annualized_volatility': 0,
                'frequency': freq_info['frequency'] if freq_info else 'unknown',
                'periods_per_year': periods_per_year,
                'data_quality': 'insufficient'
            }

        # Calculate returns, filtering out invalid divisions
        returns = np.diff(valid_prices) / valid_prices[:-1]

        # Remove any NaN or infinite values from returns
        returns = returns[np.isfinite(returns)]

        if len(returns) < 2:
            return {
                'daily_volatility': 0,
                'annualized_volatility': 0,
                'frequency': freq_info['frequency'] if freq_info else 'unknown',
                'periods_per_year': periods_per_year,
                'data_quality': 'insufficient'
            }

        # Calculate period volatility (standard deviation)
        period_volatility = np.std(returns, ddof=1)

        # CRITICAL FIX: Annualize using detected frequency
        annualized_volatility = period_volatility * np.sqrt(periods_per_year)

        # Ensure values are finite
        period_vol = float(period_volatility) if np.isfinite(period_volatility) else 0.0
        annual_vol = float(annualized_volatility) if np.isfinite(annualized_volatility) else 0.0

        return {
            'daily_volatility': period_vol,  # Actually "period" volatility
            'annualized_volatility': annual_vol,
            'frequency': freq_info['frequency'] if freq_info else 'assumed_daily',
            'periods_per_year': periods_per_year,
            'data_quality': freq_info['confidence'] if freq_info else 'assumed'
        }

    @staticmethod
    def calculate_sharpe_ratio(returns: List[float], risk_free_rate: float = 0.03,
                               dates: Optional[List[date]] = None) -> Dict:
        """
        Calculate Sharpe ratio with frequency detection.

        Args:
            returns: List of period returns
            risk_free_rate: Annual risk-free rate (default 3%)
            dates: Optional list of dates (for frequency detection, needs n+1 dates for n returns)

        Returns:
            {
                'sharpe_ratio': float,
                'annualized_return': float,
                'annualized_volatility': float,
                'frequency': str,
                'data_quality': str
            }
        """
        if len(returns) < 2:
            return {
                'sharpe_ratio': 0,
                'annualized_return': 0,
                'annualized_volatility': 0,
                'frequency': 'unknown',
                'data_quality': 'insufficient'
            }

        # Detect frequency
        freq_info = None
        if dates and len(dates) >= len(returns) + 1:  # Need n+1 dates for n returns
            freq_info = DataFrequencyDetector.detect_frequency(dates)

        periods_per_year = freq_info['periods_per_year'] if freq_info else 252

        returns_array = np.array(returns)

        # Filter out NaN and infinite values
        valid_returns = returns_array[np.isfinite(returns_array)]

        if len(valid_returns) < 2:
            return {
                'sharpe_ratio': 0,
                'annualized_return': 0,
                'annualized_volatility': 0,
                'frequency': freq_info['frequency'] if freq_info else 'unknown',
                'data_quality': 'insufficient'
            }

        avg_return = np.mean(valid_returns)
        std_return = np.std(valid_returns, ddof=1)

        if std_return == 0 or not np.isfinite(std_return):
            annualized_return = avg_return * periods_per_year if np.isfinite(avg_return) else 0
            return {
                'sharpe_ratio': 0,
                'annualized_return': float(annualized_return),
                'annualized_volatility': 0,
                'frequency': freq_info['frequency'] if freq_info else 'assumed_daily',
                'data_quality': 'zero_volatility'
            }

        # CRITICAL FIX: Use detected frequency for annualization
        annualized_return = avg_return * periods_per_year
        annualized_std = std_return * np.sqrt(periods_per_year)

        sharpe_ratio = (annualized_return - risk_free_rate) / annualized_std

        return {
            'sharpe_ratio': float(sharpe_ratio) if np.isfinite(sharpe_ratio) else 0.0,
            'annualized_return': float(annualized_return) if np.isfinite(annualized_return) else 0.0,
            'annualized_volatility': float(annualized_std) if np.isfinite(annualized_std) else 0.0,
            'frequency': freq_info['frequency'] if freq_info else 'assumed_daily',
            'data_quality': freq_info['confidence'] if freq_info else 'assumed'
        }

    @staticmethod
    def calculate_herfindahl_index(weights: List[float]) -> float:
        """
        Calculate Herfindahl-Hirschman Index for diversification
        HHI = sum of squared weights
        Range: 0 to 1 (or 0 to 10000 if using percentages)
        Lower values indicate better diversification
        """
        if not weights:
            return 0

        weights_array = np.array(weights)
        hhi = np.sum(weights_array ** 2)

        return float(hhi)

    @staticmethod
    def calculate_dividend_yield(annual_dividends: float, portfolio_value: float) -> float:
        """Calculate dividend yield as percentage"""
        if portfolio_value == 0:
            return 0

        return (annual_dividends / portfolio_value) * 100

    @staticmethod
    def calculate_cagr(initial_value: float, final_value: float, years: float) -> float:
        """
        Calculate Compound Annual Growth Rate
        years: Can be fractional (e.g., 1.5 years)
        """
        if initial_value == 0 or years == 0:
            return 0

        cagr = (pow(final_value / initial_value, 1 / years) - 1) * 100

        return float(cagr)

    @staticmethod
    def calculate_max_drawdown(values: List[float]) -> Dict:
        """
        Calculate maximum drawdown
        Returns dict with max_drawdown percentage and peak/trough dates
        """
        if len(values) < 2:
            return {'max_drawdown': 0, 'peak_index': 0, 'trough_index': 0}

        values_array = np.array(values)
        cumulative_max = np.maximum.accumulate(values_array)
        drawdowns = (values_array - cumulative_max) / cumulative_max

        max_drawdown_idx = np.argmin(drawdowns)
        max_drawdown = drawdowns[max_drawdown_idx]

        # Find the peak before the max drawdown
        peak_idx = np.argmax(values_array[:max_drawdown_idx + 1]) if max_drawdown_idx > 0 else 0

        return {
            'max_drawdown': float(abs(max_drawdown) * 100),  # Convert to percentage
            'peak_index': int(peak_idx),
            'trough_index': int(max_drawdown_idx)
        }

    @staticmethod
    def calculate_portfolio_concentration(holdings_values: List[float]) -> Dict:
        """
        Calculate concentration metrics
        Returns largest position %, top 5 concentration, and HHI
        """
        if not holdings_values or sum(holdings_values) == 0:
            return {
                'largest_position_percent': 0,
                'top_5_concentration': 0,
                'herfindahl_index': 0
            }

        total = sum(holdings_values)
        sorted_values = sorted(holdings_values, reverse=True)

        # Calculate percentages
        percentages = [v / total for v in sorted_values]

        largest_position_percent = percentages[0] * 100 if percentages else 0
        top_5_concentration = sum(percentages[:5]) * 100

        # Calculate HHI
        hhi = FinancialCalculations.calculate_herfindahl_index(percentages)

        return {
            'largest_position_percent': largest_position_percent,
            'top_5_concentration': top_5_concentration,
            'herfindahl_index': hhi
        }


class RealizedGainsCalculator:
    """Calculate realized gains from SELL transactions using FIFO"""

    @staticmethod
    def calculate_realized_gain_for_sell(ticker: str, sell_transaction, db) -> Dict:
        """
        Calculate realized gain for a specific SELL transaction.

        Args:
            ticker: Stock ticker
            sell_transaction: Transaction object for the SELL
            db: Database session

        Returns:
            {
                'realized_gain_czk': float,
                'cost_basis_czk': float,
                'proceeds_czk': float,
                'quantity_sold': float,
                'matched_lots': List[Dict],
                'warnings': List[str]
            }
        """
        from sqlalchemy.orm import Session
        from models.database import Transaction
        from services.exchange_rate_service import CurrencyNormalizer

        warnings = []

        # Get all BUY transactions for this ticker before the sell
        buy_txns = db.query(Transaction).filter(
            Transaction.ticker == ticker,
            Transaction.transaction_type == 'BUY',
            Transaction.transaction_date <= sell_transaction.transaction_date
        ).order_by(Transaction.transaction_date.asc(), Transaction.id.asc()).all()

        if not buy_txns:
            warnings.append(f"SELL without matching BUY for {ticker} on {sell_transaction.transaction_date}")
            return {
                'realized_gain_czk': 0,
                'cost_basis_czk': 0,
                'proceeds_czk': 0,
                'quantity_sold': sell_transaction.quantity,
                'matched_lots': [],
                'warnings': warnings
            }

        # Get all SELL transactions before this one (to track what's been used)
        prior_sells = db.query(Transaction).filter(
            Transaction.ticker == ticker,
            Transaction.transaction_type == 'SELL',
            Transaction.transaction_date < sell_transaction.transaction_date
        ).order_by(Transaction.transaction_date.asc(), Transaction.id.asc()).all()

        # Include same-day sells with lower ID (for same-day sells)
        same_date_sells = db.query(Transaction).filter(
            Transaction.ticker == ticker,
            Transaction.transaction_type == 'SELL',
            Transaction.transaction_date == sell_transaction.transaction_date,
            Transaction.id < sell_transaction.id
        ).all()

        prior_sells.extend(same_date_sells)

        # Build purchase list for FIFO (normalize to CZK)
        purchases = []
        for buy in buy_txns:
            # Normalize buy amount to CZK
            buy_normalized = CurrencyNormalizer.normalize_transaction(buy, db)
            if buy_normalized['conversion_warning']:
                warnings.append(buy_normalized['conversion_warning'])

            # Use absolute value to handle negative BUY amounts (semantic sign convention)
            # BUY amounts are stored as negative (money out), but we need positive price per share
            price_per_share_czk = abs(buy_normalized['amount_czk']) / buy.quantity if buy.quantity > 0 else 0

            purchases.append({
                'quantity': buy.quantity,
                'price': price_per_share_czk,  # CZK price per share (always positive)
                'date': buy.transaction_date,
                'transaction_id': buy.id
            })

        # Reduce purchases by prior sells (FIFO)
        for prior_sell in prior_sells:
            _, purchases = FinancialCalculations.calculate_fifo_cost_basis(
                purchases,
                prior_sell.quantity
            )

        # Now calculate cost basis for THIS sell
        quantity_to_sell = sell_transaction.quantity
        cost_basis_czk, remaining_purchases = FinancialCalculations.calculate_fifo_cost_basis(
            purchases,
            quantity_to_sell
        )

        # Track matched lots
        matched_lots = []
        remaining_qty = quantity_to_sell

        for purchase in purchases:
            if remaining_qty <= 0:
                break

            qty_from_lot = min(purchase['quantity'], remaining_qty)
            holding_period = (sell_transaction.transaction_date - purchase['date']).days

            matched_lots.append({
                'buy_transaction_id': purchase['transaction_id'],
                'quantity': qty_from_lot,
                'purchase_price_czk': purchase['price'],
                'purchase_date': purchase['date'],
                'holding_period_days': holding_period
            })

            remaining_qty -= qty_from_lot

        # Calculate proceeds (normalize sell to CZK)
        sell_normalized = CurrencyNormalizer.normalize_transaction(sell_transaction, db)
        if sell_normalized['conversion_warning']:
            warnings.append(sell_normalized['conversion_warning'])

        proceeds_czk = sell_normalized['amount_czk']

        # Realized gain
        realized_gain_czk = proceeds_czk - cost_basis_czk

        return {
            'realized_gain_czk': realized_gain_czk,
            'cost_basis_czk': cost_basis_czk,
            'proceeds_czk': proceeds_czk,
            'quantity_sold': quantity_to_sell,
            'matched_lots': matched_lots,
            'warnings': warnings
        }

    @staticmethod
    def calculate_total_realized_gains(db) -> float:
        """
        Calculate total realized gains across all SELL transactions.

        Args:
            db: Database session

        Returns:
            Total realized gains in CZK
        """
        from models.database import Transaction

        sell_transactions = db.query(Transaction).filter(
            Transaction.transaction_type == 'SELL'
        ).order_by(Transaction.transaction_date.asc(), Transaction.id.asc()).all()

        total_realized_gain_czk = 0

        for sell in sell_transactions:
            result = RealizedGainsCalculator.calculate_realized_gain_for_sell(
                sell.ticker,
                sell,
                db
            )
            total_realized_gain_czk += result['realized_gain_czk']

        return total_realized_gain_czk

    @staticmethod
    def get_realized_gains_by_ticker(db) -> Dict[str, float]:
        """
        Get realized gains broken down by ticker.

        Args:
            db: Database session

        Returns:
            {ticker: realized_gain_czk}
        """
        from models.database import Transaction

        sell_transactions = db.query(Transaction).filter(
            Transaction.transaction_type == 'SELL'
        ).order_by(Transaction.transaction_date.asc()).all()

        gains_by_ticker = defaultdict(float)

        for sell in sell_transactions:
            result = RealizedGainsCalculator.calculate_realized_gain_for_sell(
                sell.ticker,
                sell,
                db
            )
            gains_by_ticker[sell.ticker] += result['realized_gain_czk']

        return dict(gains_by_ticker)

    @staticmethod
    def get_realized_gains_by_year(db) -> Dict[int, float]:
        """
        Get realized gains broken down by tax year.

        Args:
            db: Database session

        Returns:
            {year: realized_gain_czk}
        """
        from models.database import Transaction

        sell_transactions = db.query(Transaction).filter(
            Transaction.transaction_type == 'SELL'
        ).order_by(Transaction.transaction_date.asc()).all()

        gains_by_year = defaultdict(float)

        for sell in sell_transactions:
            result = RealizedGainsCalculator.calculate_realized_gain_for_sell(
                sell.ticker,
                sell,
                db
            )
            year = sell.transaction_date.year
            gains_by_year[year] += result['realized_gain_czk']

        return dict(gains_by_year)
