"""Exposure sources: which exposures apply to the returns of a given day.

An ExposureFn is called as fn(ym, ymd), where rtn/{ym} holds the returns of
the month after ym and ymd is the return date. It returns a DataFrame indexed
by bid with one column per factor (raw values; the engine standardizes).

monthly(loader)         month-end exposures at ym for every day of the next
                        month (formation = previous month end)
panel(df)               the same from one table with a "ym" column
daily_scores(columns)   RGA daily score files: the latest file dated strictly
                        before the return date (formation = previous day)
month_end_scores(...)   RGA score files at the latest month end on or before
                        the return date (archive BLF.fret_nam_daily timing)
"""

import bisect
from collections.abc import Callable
from functools import cache

import pandas as pd

from p_ken import io
from p_ken.factors.engine import ExposureFn


def _by_bid(df: pd.DataFrame) -> pd.DataFrame:
    if "bid" in df.columns:
        df = df.drop_duplicates("bid").set_index("bid")
    return df.drop(columns=["ym"], errors="ignore")


def monthly(loader: Callable[[str], pd.DataFrame]) -> ExposureFn:
    """loader(ym) -> exposures at ym end (with a "bid" column or bid index)."""

    @cache
    def at(ym: str) -> pd.DataFrame:
        return _by_bid(loader(ym))

    return lambda ym, ymd: at(ym)


def panel(df: pd.DataFrame, ym_col: str = "ym") -> ExposureFn:
    """Month-end exposures from one table with columns ym, bid, <factors>."""
    yms = df[ym_col].astype(str)
    return monthly(lambda ym: df[yms == ym].drop(columns=ym_col))


def _latest(dates: list[str], ymd: str, inclusive: bool) -> str:
    i = (bisect.bisect_right if inclusive else bisect.bisect_left)(dates, ymd) - 1
    if i < 0:
        raise FileNotFoundError(f"no score file {'on or ' if inclusive else ''}before {ymd}")
    return dates[i]


def _score_frame(columns: dict[str, tuple[str, str]], ymd: str, inclusive: bool, universe: str):
    cols = {}
    for name, (kind, col) in columns.items():
        day = _latest(io.score_dates(kind, universe), ymd, inclusive)
        cols[name] = io.load_scores(kind, day, universe)[col]
    return pd.DataFrame(cols)


def daily_scores(columns: dict[str, tuple[str, str]], universe: str = "blf") -> ExposureFn:
    """columns: output name -> (score kind "ai" / "bigdata", column).

    Each return date uses, per kind, the latest file dated strictly before it.
    """

    @cache
    def at(ymd: str) -> pd.DataFrame:
        return _score_frame(columns, ymd, inclusive=False, universe=universe)

    return lambda ym, ymd: at(ymd)


def month_end_scores(
    columns: dict[str, tuple[str, str]], universe: str = "blf", base_kind: str = "ai"
) -> ExposureFn:
    """archive BLF.fret_nam_daily timing for the daily score files.

    Month end = last trading day of each month (from the return files). A
    return date uses the scores at the latest month end on or before it (so
    the month-end day itself uses that day's scores), taken from the latest
    files on or before that month end. Rows = all bids of the `base_kind`
    file, i.e. quantile breakpoints are set on the whole score universe.
    """
    days = sorted(
        {d for ym in io.list_yms(universe, "rtn") for d in io.load_returns(universe, ym).ymd}
    )
    month_ends = pd.Series(days).groupby(pd.Series(days).str[:6]).max().tolist()

    @cache
    def at(me: str) -> pd.DataFrame:
        frame = _score_frame(columns, me, inclusive=True, universe=universe)
        base = io.load_scores(base_kind, _latest(io.score_dates(base_kind, universe), me, True))
        return frame.reindex(base.index)

    def fn(ym: str, ymd: str) -> pd.DataFrame:
        me = _latest(month_ends, ymd, inclusive=True)
        return at(me)

    return fn
