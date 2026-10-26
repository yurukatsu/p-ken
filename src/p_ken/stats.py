"""Small numerical building blocks (see docs/methodology.md for the formulas)."""

import numpy as np
import pandas as pd
from scipy.stats import norm

BLOM_ALPHA = 3 / 8


def blom(x: pd.Series | pd.DataFrame) -> pd.Series | pd.DataFrame:
    """Blom normal scores per column: Phi^-1((rank - 3/8) / (n + 1/4)).

    rank = average rank among the non-missing values, n = their count.
    Missing values stay missing.
    """
    rk = x.rank(method="average")
    n = x.notna().sum()
    z = norm.ppf((rk - BLOM_ALPHA) / (n + 1 - 2 * BLOM_ALPHA))
    if isinstance(x, pd.Series):
        return pd.Series(z, index=x.index, name=x.name)
    return pd.DataFrame(z, index=x.index, columns=x.columns)


def blom_r(x: pd.Series, alpha: float = BLOM_ALPHA) -> pd.Series:
    """calc_blom_score() of the R library: uses max(rank) instead of n.

    Identical to `blom` unless the largest values are tied. Kept for GEMQ3.
    """
    rk = x.rank(method="average")
    return pd.Series(norm.ppf((rk - alpha) / (rk.max() - 2 * alpha + 1)), index=x.index)


def zscore(x: pd.DataFrame) -> pd.DataFrame:
    """(x - mean) / sd per column (sample sd), missing ignored."""
    return (x - x.mean()) / x.std()


def ntile(x: pd.Series, n: int = 5) -> pd.Series:
    """dplyr (>= 1.1) ntile(): groups 1..n of (almost) equal size, ties by order."""
    valid = x.notna()
    out = pd.Series(np.nan, index=x.index)
    length = int(valid.sum())
    if length == 0:
        return out
    r = x[valid].rank(method="first").to_numpy()
    n_larger = length % n
    larger_size = int(np.ceil(length / n))
    smaller_size = length // n
    larger_threshold = larger_size * n_larger
    bins = np.where(
        r <= larger_threshold,
        (r + larger_size - 1) / larger_size,
        (r - larger_threshold + smaller_size - 1) / max(smaller_size, 1) + n_larger,
    )
    out[valid] = np.floor(bins)
    return out


def slopes(z: pd.DataFrame, y: np.ndarray, min_obs: int = 3) -> pd.Series:
    """OLS slope of y on each column of z, with an intercept.

    Each column uses only its own non-missing rows:
        b_k = sum (z_ik - zbar_k)(y_i - ybar_k) / sum (z_ik - zbar_k)^2
    NaN when fewer than min_obs rows or no variation.
    """
    x = z.to_numpy(float)
    mask = ~np.isnan(x)
    n = mask.sum(axis=0)
    xz = np.where(mask, x, 0.0)
    ym = np.where(mask, y[:, None], 0.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        xbar = xz.sum(axis=0) / n
        ybar = ym.sum(axis=0) / n
        xc = np.where(mask, x - xbar, 0.0)
        yc = np.where(mask, y[:, None] - ybar, 0.0)
        sxx = (xc**2).sum(axis=0)
        b = (xc * yc).sum(axis=0) / sxx
    b = np.where((n >= min_obs) & (sxx > 0), b, np.nan)
    return pd.Series(b, index=z.columns)


def period_return(level: pd.Series, start: str, end: str) -> float:
    """Return from the last value before `start` to the last value on or before `end`."""
    s = level.dropna()
    before = s[s.index < pd.Timestamp(start)]
    upto = s[s.index <= pd.Timestamp(end)]
    if before.empty or upto.empty:
        return float("nan")
    return upto.iloc[-1] / before.iloc[-1] - 1


def rebase(level: pd.Series, base: str, value: float = 100.0) -> pd.Series:
    """Scale so the value on `base` (or the last one before it) equals `value`."""
    before = level[level.index <= pd.Timestamp(base)]
    if before.empty:
        raise ValueError(f"{level.name}: no value on or before {base}")
    return level[level.index >= before.index[-1]] / before.iloc[-1] * value


def annualized(daily: pd.DataFrame, days_per_year: int = 252) -> pd.DataFrame:
    """Per column: total (sum), annualized mean / sd, ratio and hit rate of daily returns."""
    out = pd.DataFrame(
        {
            "start": daily.apply(lambda s: f"{s.first_valid_index():%Y-%m-%d}"),
            "end": daily.apply(lambda s: f"{s.last_valid_index():%Y-%m-%d}"),
            "days": daily.count(),
            "total": daily.sum(),
            "ann_ret": daily.mean() * days_per_year,
            "ann_risk": daily.std() * np.sqrt(days_per_year),
            "hit": (daily > 0).sum() / daily.count(),
        }
    )
    out["rr"] = out.ann_ret / out.ann_risk
    return out
