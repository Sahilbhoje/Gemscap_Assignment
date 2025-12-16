from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd
from statsmodels.regression.linear_model import OLS
from statsmodels.tools import add_constant
from statsmodels.tsa.stattools import adfuller


@dataclass
class PairAnalytics:
    beta: float
    intercept: float
    spread_last: float
    zscore_last: float
    adf_pvalue: Optional[float]
    corr_last: Optional[float]


def compute_hedge_ratio(y: pd.Series, x: pd.Series, add_intercept: bool = True) -> Tuple[float, float]:
    df = pd.concat([y.rename("y"), x.rename("x")], axis=1).dropna()
    if df.empty or df.shape[0] < 10:
        return 1.0, 0.0
    X = add_constant(df["x"]) if add_intercept else df[["x"]]
    model = OLS(df["y"], X).fit()
    if add_intercept:
        return float(model.params["x"]), float(model.params["const"])
    return float(model.params["x"]), 0.0


def compute_spread_zscore(y: pd.Series, x: pd.Series, beta: float, intercept: float = 0.0, window: int = 100) -> Tuple[pd.Series, pd.Series]:
    s = y - (beta * x + intercept)
    m = s.rolling(window, min_periods=max(10, window // 5)).mean()
    sd = s.rolling(window, min_periods=max(10, window // 5)).std(ddof=0)
    z = (s - m) / sd
    return s, z


def compute_corr(y: pd.Series, x: pd.Series, window: int = 100) -> pd.Series:
    df = pd.concat([y.rename("y"), x.rename("x")], axis=1).dropna()
    return df["y"].rolling(window).corr(df["x"]) if not df.empty else pd.Series(dtype=float)


def adf_test(series: pd.Series, maxlag: Optional[int] = None) -> Optional[float]:
    s = series.dropna()
    if s.shape[0] < 20:
        return None
    try:
        res = adfuller(s.values, maxlag=maxlag, autolag="AIC")
        return float(res[1])  # p-value
    except Exception:
        return None


def build_pair_analytics(y_close: pd.Series, x_close: pd.Series, window: int = 100, add_intercept: bool = True) -> PairAnalytics:
    beta, intercept = compute_hedge_ratio(y_close, x_close, add_intercept=add_intercept)
    spread, z = compute_spread_zscore(y_close, x_close, beta, intercept, window=window)
    p_adf = adf_test(spread)
    corr = compute_corr(y_close, x_close, window=window)
    return PairAnalytics(
        beta=beta,
        intercept=intercept,
        spread_last=float(spread.dropna().iloc[-1]) if not spread.dropna().empty else float("nan"),
        zscore_last=float(z.dropna().iloc[-1]) if not z.dropna().empty else float("nan"),
        adf_pvalue=p_adf,
        corr_last=float(corr.dropna().iloc[-1]) if not corr.dropna().empty else None,
    )
