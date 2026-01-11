import numpy as np
from typing import List, Dict
from datetime import date


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
                # Keep the unused portion
                remaining_purchases.append({
                    'quantity': purchase['quantity'] - remaining_quantity,
                    'price': purchase['price'],
                    'date': purchase['date']
                })
                remaining_quantity = 0

        cost_basis = total_cost
        return cost_basis, remaining_purchases

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
    def calculate_volatility(prices: List[float]) -> Dict:
        """
        Calculate volatility metrics from price series
        Returns dict with daily and annualized volatility
        """
        if len(prices) < 2:
            return {'daily_volatility': 0, 'annualized_volatility': 0}

        # Calculate daily returns
        prices_array = np.array(prices)

        # Filter out zero and NaN values
        valid_prices = prices_array[~np.isnan(prices_array) & (prices_array > 0)]

        if len(valid_prices) < 2:
            return {'daily_volatility': 0, 'annualized_volatility': 0}

        # Calculate returns, filtering out invalid divisions
        returns = np.diff(valid_prices) / valid_prices[:-1]

        # Remove any NaN or infinite values from returns
        returns = returns[np.isfinite(returns)]

        if len(returns) < 2:
            return {'daily_volatility': 0, 'annualized_volatility': 0}

        # Calculate standard deviation (volatility)
        daily_volatility = np.std(returns, ddof=1)

        # Annualize (assuming 252 trading days)
        annualized_volatility = daily_volatility * np.sqrt(252)

        # Ensure values are finite
        daily_vol = float(daily_volatility) if np.isfinite(daily_volatility) else 0.0
        annual_vol = float(annualized_volatility) if np.isfinite(annualized_volatility) else 0.0

        return {
            'daily_volatility': daily_vol,
            'annualized_volatility': annual_vol
        }

    @staticmethod
    def calculate_sharpe_ratio(returns: List[float], risk_free_rate: float = 0.03) -> float:
        """
        Calculate Sharpe ratio
        returns: List of period returns
        risk_free_rate: Annual risk-free rate (default 3%)
        """
        if len(returns) < 2:
            return 0

        returns_array = np.array(returns)

        # Filter out NaN and infinite values
        valid_returns = returns_array[np.isfinite(returns_array)]

        if len(valid_returns) < 2:
            return 0

        avg_return = np.mean(valid_returns)
        std_return = np.std(valid_returns, ddof=1)

        if std_return == 0 or not np.isfinite(std_return):
            return 0

        # Annualize assuming daily returns
        annualized_return = avg_return * 252
        annualized_std = std_return * np.sqrt(252)

        sharpe_ratio = (annualized_return - risk_free_rate) / annualized_std

        # Ensure result is finite
        return float(sharpe_ratio) if np.isfinite(sharpe_ratio) else 0.0

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
