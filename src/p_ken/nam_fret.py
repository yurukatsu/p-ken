"""Daily factor returns of the NAM scores (AI, TVL, RVL, ai70_bd30) on the RGA universe.

Method (follows fret_nam_daily in archive/msci_lib.R.r):
  - exposures: the daily score files in data/blf/exposures/nam
      ai/{ymd}.csv       -> ai, ai70_bd30
      bigdata/{ymd}.csv  -> tvl, rvl
    For each return date the latest file dated strictly before it is used
    (no look-ahead).
  - returns: data/blf/rtn (local currency `ret`, or specific `sret`),
    stocks of the RGA universe; |ret| >= 100 % dropped.
  - each day and factor: drop missing scores (and <= -100), rank ->
    (rank - 3/8) / (n + 1/4) -> normal quantile, and regress the return on
    it with an intercept. The slope is the factor's return for the day.

    from p_ken import nam_fret
    daily = nam_fret.factor_returns(start="2026-01-01", end="2026-09-30")
"""

import bisect
from functools import cache
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from p_ken import io

DATA_DIR = Path("data/blf")
NAM_DIR = DATA_DIR / "exposures" / "nam"
MISSING_BELOW = -100
MAX_ABS_RET = 100  # percent

# output name -> (score file folder, column)
FACTORS = {
    "AI": ("ai", "ai"),
    "TVL": ("bigdata", "tvl"),
    "RVL": ("bigdata", "rvl"),
    "Composite (ai70_bd30)": ("ai", "ai70_bd30"),
}
# categorical slots 1-3 and 7 (violet: more contrast than yellow for the composite)
COLORS = {
    "AI": "#2a78d6",
    "TVL": "#eb6834",
    "RVL": "#1baf7a",
    "Composite (ai70_bd30)": "#6250d6",
}


@cache
def _score_dates(folder: str) -> list[str]:
    return sorted(p.stem for p in (NAM_DIR / folder).glob("*.csv") if p.stem.isdigit())


@cache
def _scores(folder: str, ymd: str) -> pd.DataFrame:
    df = pd.read_csv(
        NAM_DIR / folder / f"{ymd}.csv", encoding="utf-8-sig", dtype={"bid": str}
    )
    return df.dropna(subset=["bid"]).drop_duplicates("bid").set_index("bid")


def scores_before(ymd: str) -> pd.DataFrame:
    """Scores (index = bid, columns = FACTORS) from the latest files before ymd."""
    cols = {}
    for name, (folder, col) in FACTORS.items():
        dates = _score_dates(folder)
        i = bisect.bisect_left(dates, ymd) - 1  # strictly before ymd
        if i < 0:
            raise FileNotFoundError(f"no {folder} score before {ymd}")
        cols[name] = _scores(folder, dates[i])[col]
    return pd.DataFrame(cols)


def _slope(x: np.ndarray, y: np.ndarray) -> float:
    """Slope of y on the Blom score of x (missing x dropped)."""
    ok = ~np.isnan(x) & (x > MISSING_BELOW)
    x, y = x[ok], y[ok]
    if len(x) < 3:
        return np.nan
    rk = pd.Series(x).rank(method="average").to_numpy()
    s = norm.ppf((rk - 3 / 8) / (len(x) + 1 / 4))
    sc = s - s.mean()
    sxx = (sc**2).sum()
    return float(sc @ (y - y.mean()) / sxx) if sxx > 0 else np.nan


def factor_returns(
    start: str = "2026-01-01", end: str | None = None, ret_col: str = "ret"
) -> pd.DataFrame:
    """Daily factor returns (index = date, columns = FACTORS), decimals."""
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end) if end else None
    first_ym = io.prev_ym(f"{start_ts:%Y%m}")
    rows = []
    for ym in io.list_yms("rtn", DATA_DIR):
        if ym < first_ym:
            continue
        rtn = io.load_rtn(ym, DATA_DIR)  # returns of the month after ym
        rtn = rtn.dropna(subset=[ret_col])
        rtn = rtn[rtn[ret_col].abs() < MAX_ABS_RET]
        for ymd, day in rtn.groupby("ymd"):
            d = pd.Timestamp(ymd)
            if d < start_ts or (end_ts is not None and d > end_ts):
                continue
            day = day.drop_duplicates("bid").set_index("bid")
            sc = scores_before(ymd).reindex(day.index)
            y = day[ret_col].to_numpy(float) / 100
            rows.append(
                pd.Series(
                    {f: _slope(sc[f].to_numpy(float), y) for f in FACTORS}, name=d
                )
            )
    if not rows:
        raise ValueError(f"no NAM factor returns from {start}")
    return pd.DataFrame(rows).sort_index()
