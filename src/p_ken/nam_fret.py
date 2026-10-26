"""Daily factor returns of the NAM scores.

RGA universe (data/blf): AI, TVL, RVL, ai70_bd30 from the daily score files
    exposures/nam/ai/{ymd}.csv       -> ai, ai70_bd30
    exposures/nam/bigdata/{ymd}.csv  -> tvl, rvl
  For each return date the latest file dated strictly before it is used.

MSCI EM universe (data/gemq): AI, Revision, GEMQ3 from the month-end files
    exposures/nam/{ai,revision,gemq3}/{ym}.csv
  Month-end ym scores are paired with rtn/{ym} (daily returns of the next month).

Method (follows fret_nam_daily in archive/msci_lib.R.r), per day and factor:
drop missing scores (and <= -100) and |ret| >= 100 %, rank ->
(rank - 3/8) / (n + 1/4) -> normal quantile, regress the return (local
currency `ret`, or specific `sret`) on it with an intercept. The slope is the
factor's return for the day.

    from p_ken import nam_fret
    daily = nam_fret.factor_returns("blf", start="2026-01-01", end="2026-09-30")
"""

import bisect
from functools import cache
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from p_ken import fret, io

DATA_ROOT = Path("data")
MISSING_BELOW = -100
MAX_ABS_RET = 100  # percent

UNIVERSES = {"blf": "RGA Universe", "gemq": "MSCI EM Universe"}

# RGA daily scores: output name -> (score file folder, column)
BLF_FACTORS = {
    "AI": ("ai", "ai"),
    "TVL": ("bigdata", "tvl"),
    "RVL": ("bigdata", "rvl"),
    "Composite (ai70_bd30)": ("ai", "ai70_bd30"),
}
# MSCI EM month-end scores: output name -> column of fret.default_exposures
GEMQ_FACTORS = {"AI": "ai", "Revision": "rev", "GEMQ3": "Gousei_3Factor"}

# Same factor, same colour across charts. Blue / orange / aqua are the first
# three categorical slots (pass all-pairs CVD checks); composite scores are
# drawn in near-black ink so they stand apart from every hue.
COMPOSITE = "#262626"
COLORS = {
    "blf": {
        "AI": "#2a78d6",
        "TVL": "#eb6834",
        "RVL": "#1baf7a",
        "Composite (ai70_bd30)": COMPOSITE,
    },
    "gemq": {"AI": "#2a78d6", "Revision": "#eb6834", "GEMQ3": COMPOSITE},
}


# --- exposures ---------------------------------------------------------------


@cache
def _score_dates(folder: str) -> list[str]:
    path = DATA_ROOT / "blf" / "exposures" / "nam" / folder
    return sorted(p.stem for p in path.glob("*.csv") if p.stem.isdigit())


@cache
def _scores(folder: str, ymd: str) -> pd.DataFrame:
    path = DATA_ROOT / "blf" / "exposures" / "nam" / folder / f"{ymd}.csv"
    df = pd.read_csv(path, encoding="utf-8-sig", dtype={"bid": str})
    return df.dropna(subset=["bid"]).drop_duplicates("bid").set_index("bid")


def blf_scores_before(ymd: str) -> pd.DataFrame:
    """RGA scores (index = bid, columns = BLF_FACTORS) from the latest files before ymd."""
    cols = {}
    for name, (folder, col) in BLF_FACTORS.items():
        dates = _score_dates(folder)
        i = bisect.bisect_left(dates, ymd) - 1  # strictly before ymd
        if i < 0:
            raise FileNotFoundError(f"no {folder} score before {ymd}")
        cols[name] = _scores(folder, dates[i])[col]
    return pd.DataFrame(cols)


@cache
def gemq_scores(ym: str) -> pd.DataFrame:
    """MSCI EM month-end scores (index = bid, columns = GEMQ_FACTORS)."""
    exp = fret.default_exposures(ym, DATA_ROOT / "gemq").set_index("bid")
    return exp[list(GEMQ_FACTORS.values())].set_axis(list(GEMQ_FACTORS), axis=1)


# --- returns -----------------------------------------------------------------


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
    universe: str = "blf",
    start: str = "2026-01-01",
    end: str | None = None,
    ret_col: str = "ret",
) -> pd.DataFrame:
    """Daily factor returns (index = date, columns = factors), decimals.

    universe: "blf" (RGA, daily scores) or "gemq" (MSCI EM, month-end scores).
    Months without scores or returns are skipped.
    """
    data_dir = DATA_ROOT / universe
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end) if end else None
    first_ym = io.prev_ym(f"{start_ts:%Y%m}")
    rows = []
    for ym in io.list_yms("rtn", data_dir):
        if ym < first_ym:
            continue
        rtn = io.load_rtn(ym, data_dir)  # returns of the month after ym
        rtn = rtn.dropna(subset=[ret_col])
        rtn = rtn[rtn[ret_col].abs() < MAX_ABS_RET]
        if universe == "gemq":
            try:
                month_scores = gemq_scores(ym)
            except FileNotFoundError:
                continue
        for ymd, day in rtn.groupby("ymd"):
            d = pd.Timestamp(ymd)
            if d < start_ts or (end_ts is not None and d > end_ts):
                continue
            day = day.drop_duplicates("bid").set_index("bid")
            scores = month_scores if universe == "gemq" else blf_scores_before(ymd)
            sc = scores.reindex(day.index)
            y = day[ret_col].to_numpy(float) / 100
            rows.append(
                pd.Series(
                    {f: _slope(sc[f].to_numpy(float), y) for f in sc.columns}, name=d
                )
            )
    if not rows:
        raise ValueError(f"no NAM factor returns for {universe} from {start}")
    return pd.DataFrame(rows).sort_index()
