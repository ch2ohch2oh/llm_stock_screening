import numpy as np
from sklearn.linear_model import LinearRegression
from typing import Union
import pandas as pd

def compute_stock_score(
    price_series: Union[np.ndarray, pd.Series],
    ann_return_weight: float = 2.0,
    max_dd_weight: float = -3.0,
    slope_to_noise_weight: float = 1.0,
    annualization_factor: int = 252,
) -> float:
    """
    Computes a score for a stock based on its price series.

    The score is a weighted sum of:
    1. Annualized Return
    2. Maximum Drawdown (with a negative weight)
    3. Slope-to-Noise Ratio (a measure of trend quality)

    Args:
        price_series (Union[np.ndarray, pd.Series]): A series of stock prices.
        ann_return_weight (float): Weight for the annualized return component.
        max_dd_weight (float): Weight for the maximum drawdown component.
        slope_to_noise_weight (float): Weight for the slope-to-noise component.
        annualization_factor (int): Trading days in a year for annualization.

    Returns:
        float: The computed score for the stock.
    """
    # Ensure we are working with a numpy array for consistent, position-based indexing
    prices_arr = np.asarray(price_series)
    if len(prices_arr) < 2:
        return -np.inf  # Not enough data to compute a score

    log_prices = np.log(prices_arr)
    returns = np.diff(log_prices)

    ann_return = (prices_arr[-1] / prices_arr[0]) ** (annualization_factor / len(prices_arr)) - 1
    rolling_max = np.maximum.accumulate(prices_arr)
    drawdowns = (rolling_max - prices_arr) / rolling_max
    max_dd = np.max(drawdowns)

    # Slope to noise (trend fit)
    x = np.arange(len(log_prices)).reshape(-1, 1)
    model = LinearRegression().fit(x, log_prices)
    slope = model.coef_[0]
    residuals = log_prices - model.predict(x)
    noise = np.std(residuals)
    slope_to_noise = slope / noise if noise != 0 else 0

    score = (ann_return_weight * ann_return +
             max_dd_weight * max_dd +
             slope_to_noise_weight * slope_to_noise)
    return score
