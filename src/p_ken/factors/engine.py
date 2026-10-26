"""Daily cross-sectional factor returns (formulas: docs/methodology.md).

Two estimators, both on the stocks of a universe for each trading day t:

regression (default)
    z_ik = standardized exposure of stock i to factor k (Blom normal score
           over the stocks of the day that have the exposure)
    f_kt = slope of  r_it = a_kt + f_kt z_ik + e_it   (one factor at a time)

quantile
    f_kt = mean over the top quantile of (r_it - mean_j r_jt)

r_it is the local-currency total return (`ret`) by default, or the specific
return (`sret`). Returns are in decimals.

Exposures come from an ExposureFn: (ym, ymd) -> DataFrame indexed by bid,
one column per factor, where ym is the month of the return file (the returns
are those of the month after ym) and ymd the return date. See sources.py.
"""

from collections.abc import Callable, Iterable, Iterator

import pandas as pd

from p_ken import io
from p_ken.stats import blom, ntile, slopes, zscore

ExposureFn = Callable[[str, str], pd.DataFrame]

MISSING_BELOW = -100  # exposures <= this are missing (data sentinels)
MAX_ABS_RET = 100  # percent; daily returns with |r| >= this are dropped

STANDARDIZE = {
    "blom": blom,
    "zscore": zscore,
    "raw": lambda x: x,
}


def iter_days(
    universe: str,
    start: str,
    end: str | None = None,
    ret_col: str = "ret",
    stocks: Callable[[str], Iterable[str]] | None = None,
) -> Iterator[tuple[str, str, pd.Series]]:
    """Yield (ym, ymd, returns) for each trading day in [start, end].

    returns: decimal returns of that day indexed by bid, for the stocks of
    universe/{ym} (optionally narrowed by stocks(ym)), missing and
    |r| >= MAX_ABS_RET % dropped.
    """
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end) if end else None
    first_ym = io.prev_ym(f"{start_ts:%Y%m}")
    last_ym = io.prev_ym(f"{end_ts:%Y%m}") if end_ts is not None else None
    for ym in io.list_yms(universe, "rtn"):
        if ym < first_ym or (last_ym is not None and ym > last_ym):
            continue
        rtn = io.load_returns(universe, ym).dropna(subset=[ret_col])
        rtn = rtn[rtn[ret_col].abs() < MAX_ABS_RET]
        if stocks is not None:
            rtn = rtn[rtn.bid.isin(set(stocks(ym)))]
        for ymd, day in rtn.groupby("ymd"):
            d = pd.Timestamp(ymd)
            if d < start_ts or (end_ts is not None and d > end_ts):
                continue
            yield ym, ymd, day.drop_duplicates("bid").set_index("bid")[ret_col] / 100


def _exposure(exposures: ExposureFn, ym: str, ymd: str) -> pd.DataFrame | None:
    try:
        x = exposures(ym, ymd)
    except FileNotFoundError:
        return None
    return None if x is None or x.empty else x


def regression_returns(
    universe: str,
    exposures: ExposureFn,
    start: str,
    end: str | None = None,
    ret_col: str = "ret",
    stocks: Callable[[str], Iterable[str]] | None = None,
    standardize: str = "blom",
    min_obs: int = 3,
) -> pd.DataFrame:
    """Daily one-factor regression slopes (index = date, columns = factors).

    standardize: "blom" (default), "zscore" or "raw" - applied to each
    factor over the day's stocks that have the exposure.
    Days without exposures are skipped.
    """
    rows = {}
    for ym, ymd, r in iter_days(universe, start, end, ret_col, stocks):
        x = _exposure(exposures, ym, ymd)
        if x is None:
            continue
        x = x.reindex(r.index).astype(float)
        z = STANDARDIZE[standardize](x.mask(x <= MISSING_BELOW))
        rows[pd.Timestamp(ymd)] = slopes(z, r.to_numpy(float), min_obs)
    if not rows:
        raise ValueError(f"no factor returns for {universe} from {start}")
    return pd.DataFrame(rows).T.sort_index()


def quantile_returns(
    universe: str,
    exposures: ExposureFn,
    start: str,
    end: str | None = None,
    ret_col: str = "ret",
    stocks: Callable[[str], Iterable[str]] | None = None,
    q: int = 5,
    group: int | str | None = None,
    breakpoints: str = "formation",
) -> pd.DataFrame:
    """Daily mean excess return of a quantile group (index = date, columns = factors).

    Stocks are split into q groups by exposure (1 = lowest, q = highest);
    the excess return is r_it minus the day's simple average.
    group:       which group (default q, the top) or "spread" = top - bottom.
    breakpoints: "formation" - dplyr::ntile within each exposure frame (the
                 universe at the formation date; R fret_nam_monitor), or
                 "pooled" - pd.qcut over all (day x stock) rows of the period
                 at once (archive BLF.fret_nam_daily / em-market-weekly).
    """
    group = q if group is None else group
    days = []
    for ym, ymd, r in iter_days(universe, start, end, ret_col, stocks):
        x = _exposure(exposures, ym, ymd)
        if x is not None:
            days.append((ymd, r, x.astype(float).mask(x <= MISSING_BELOW)))
    if not days:
        raise ValueError(f"no quantile returns for {universe} from {start}")

    if breakpoints == "pooled":
        panel = pd.concat({ymd: x for ymd, _, x in days}, names=["ymd", "bid"])
        for col in panel.columns:
            try:
                panel[col] = pd.qcut(panel[col], q, labels=False, duplicates="drop") + 1
            except (ValueError, IndexError):
                panel[col] = float("nan")
        labels_of = {ymd: panel.loc[ymd] for ymd, _, _ in days}
    elif breakpoints == "formation":
        cache: dict[int, pd.DataFrame] = {}
        labels_of = {}
        for ymd, _, x in days:
            if id(x) not in cache:
                cache[id(x)] = x.apply(lambda s: ntile(s, q))
            labels_of[ymd] = cache[id(x)]
    else:
        raise ValueError(f"breakpoints must be 'formation' or 'pooled', not {breakpoints!r}")

    rows = {}
    for ymd, r, x in days:
        excess = r - r.mean()
        labels = labels_of[ymd].reindex(excess.index)
        row = {}
        for col in x.columns:
            if group == "spread":
                row[col] = excess[labels[col] == q].mean() - excess[labels[col] == 1].mean()
            else:
                row[col] = excess[labels[col] == group].mean()
        rows[pd.Timestamp(ymd)] = pd.Series(row)
    return pd.DataFrame(rows).T.sort_index()[list(days[0][2].columns)]
