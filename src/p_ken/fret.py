"""Daily factor returns with a pluggable universe and exposures.

Follows fret_nam_monitor() in archive/msci_lib.R.r. For each month ym:
  - universe and exposures are taken at ym end
  - returns are the daily returns of the following month (data/gemq/rtn/{ym}.csv)
  - daily excess return = ret - equal-weight mean of the universe (that day)

Two definitions are produced:
  - quintile:   mean excess return per group (dplyr::ntile, highest = Q{n})
                plus Q{n}-Q1
  - regression: per day OLS  excess_ret = a + b * exposure  (one factor at a time)

Universe and exposures can each be given as
  - a function  ym -> DataFrame with a "bid" column (+ factor columns), or
  - a DataFrame with "ym" and "bid" columns (a panel covering many months).
Universe may also return a plain list of bids. See samples/ for examples.

`ret_col` selects total ("ret") or specific ("sret") returns.
Returns are in decimals (the source files are in percent, see `ret_scale`).
"""

from collections.abc import Callable, Iterable
from pathlib import Path

import numpy as np
import pandas as pd

from p_ken import io

DEFAULT_FACTORS = {"AI": "ai", "Revision": "rev", "GEMQ3": "Gousei_3Factor"}
N_GROUPS = 5

Source = Callable[[str], pd.DataFrame | Iterable[str]] | pd.DataFrame


# --- helpers ----------------------------------------------------------------


def ntile(x: pd.Series, n: int = N_GROUPS) -> pd.Series:
    """Port of dplyr (>= 1.1) ntile(): ties broken by order, NaN stays NaN."""
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


def _ols(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    """Slope, its t-stat and intercept of y = a + b x."""
    n = len(x)
    if n < 3:
        return np.nan, np.nan, np.nan
    xm = x - x.mean()
    sxx = (xm**2).sum()
    if sxx == 0:
        return np.nan, np.nan, np.nan
    b = (xm * (y - y.mean())).sum() / sxx
    a = y.mean() - b * x.mean()
    resid = y - a - b * x
    se = np.sqrt((resid**2).sum() / (n - 2) / sxx)
    return b, b / se if se > 0 else np.nan, a


def _resolve(source: Source, ym: str) -> pd.DataFrame | None:
    """Get the DataFrame (with "bid") for ym from a function or a panel."""
    if isinstance(source, pd.DataFrame):
        df = source[source["ym"].astype(str) == ym].drop(columns="ym")
    else:
        try:
            df = source(ym)
        except FileNotFoundError:
            return None
        if not isinstance(df, pd.DataFrame):
            df = pd.DataFrame({"bid": list(df)})
    if df is None or df.empty:
        return None
    return df.drop_duplicates("bid")


def _factor_map(factors, exp: pd.DataFrame) -> dict[str, str]:
    """Normalize `factors` to {output name: column}."""
    if factors is None:
        cols = exp.drop(columns="bid").select_dtypes("number").columns
        return {c: c for c in cols}
    if isinstance(factors, dict):
        return dict(factors)
    return {c: c for c in factors}


# --- default inputs (AI / Revision / GEMQ3 on MSCI EM) ------------------------


def default_universe(ym: str, data_dir: Path = io.DATA_DIR) -> pd.DataFrame:
    return io.load_unv(ym, data_dir)


def default_exposures(ym: str, data_dir: Path = io.DATA_DIR) -> pd.DataFrame:
    """ai, rev and Gousei_3Factor.

    As in fret_nam_monitor, AI / Revision are raw (NaN excluded from quintiles)
    while GEMQ3 comes from get_gemq3 (missing already filled with 0).
    Requires exposures/nam/gemq3 (run `p-ken gemq3` first).
    """
    ai = io.load_ai(ym, data_dir).drop_duplicates("bid").set_index("bid")
    rev = io.load_revision(ym, data_dir).drop_duplicates("bid").set_index("bid")
    gem = io.load_gemq3(ym, data_dir).set_index("bid")[["Gousei_3Factor"]]
    return ai.join(rev, how="outer").join(gem, how="outer").reset_index()


# --- core ---------------------------------------------------------------------


def factor_returns_month(
    exp: pd.DataFrame,
    rtn: pd.DataFrame,
    factors: dict[str, str],
    n_groups: int = N_GROUPS,
    ret_col: str = "ret",
    ret_scale: float = 0.01,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Quintile and regression factor returns for each day in `rtn`.

    exp: one row per universe stock ("bid" + exposure columns, NaN allowed).
    rtn: daily returns with ymd, bid and `ret_col`.
    """
    exp = exp.copy()
    for name, col in factors.items():
        exp[f"q_{name}"] = ntile(exp[col], n_groups)

    rtn = rtn.loc[rtn.bid.isin(exp.bid), ["ymd", "bid", ret_col]].dropna()
    rtn["dret"] = (
        rtn[ret_col] - rtn.groupby("ymd")[ret_col].transform("mean")
    ) * ret_scale
    df = rtn.merge(exp, on="bid", how="inner")

    top, ls_name = f"Q{n_groups}", f"Q{n_groups}-Q1"
    q_rows, r_rows = [], []
    for name, col in factors.items():
        g = (
            df.dropna(subset=[f"q_{name}", "dret"])
            .groupby(["ymd", f"q_{name}"])
            .dret.agg(["mean", "size"])
            .reset_index()
        )
        g.columns = ["ymd", "grp", "ret", "n"]
        g["grp"] = "Q" + g.grp.astype(int).astype(str)
        wide = g.pivot(index="ymd", columns="grp", values="ret")
        if {top, "Q1"} <= set(wide.columns):
            ls = (wide[top] - wide["Q1"]).rename("ret").reset_index()
            ls["grp"], ls["n"] = ls_name, np.nan
            g = pd.concat([g, ls[g.columns]], ignore_index=True)
        g.insert(1, "factor", name)
        q_rows.append(g)

        for ymd, d in df.dropna(subset=[col, "dret"]).groupby("ymd"):
            b, t, a = _ols(d[col].to_numpy(float), d.dret.to_numpy(float))
            r_rows.append(
                {
                    "ymd": ymd,
                    "factor": name,
                    "coef": b,
                    "tstat": t,
                    "intercept": a,
                    "n": len(d),
                }
            )

    return pd.concat(q_rows, ignore_index=True), pd.DataFrame(r_rows)


def run(
    universe: Source = default_universe,
    exposures: Source = default_exposures,
    factors: dict[str, str] | list[str] | None = None,
    months: Iterable[str] | None = None,
    start: str | None = None,
    end: str | None = None,
    returns: Callable[[str], pd.DataFrame] = io.load_rtn,
    ret_col: str = "ret",
    n_groups: int = N_GROUPS,
    ret_scale: float = 0.01,
    out_dir: Path | str | None = None,
    verbose: bool = False,
) -> dict[str, pd.DataFrame]:
    """Daily factor returns over many months.

    universe:  ym -> DataFrame with "bid" (or list of bids), or a panel
               DataFrame with "ym", "bid".
    exposures: ym -> DataFrame with "bid" + factor columns, or a panel
               DataFrame with "ym", "bid" + factor columns.
    factors:   {output name: column} or list of columns. None = every numeric
               column of the exposures.
    months:    universe/exposure months (YYYYMM). Each is paired with the
               following month's daily returns. None = every month in rtn/.
    start/end: optional YYYYMM bounds (inclusive) on those months.
    returns:   ym -> daily returns (ymd, bid, ret[, sret]) of the month after ym.
    ret_col:   "ret" (total) or "sret" (specific).
    out_dir:   if given, CSVs are written there.

    Months whose returns, universe or exposures are missing are skipped.
    Returns quintile_daily, regression_daily and their summaries.
    """
    months = [str(m) for m in months] if months is not None else io.list_yms("rtn")
    months = [m for m in months if (start is None or m >= str(start))]
    months = [m for m in months if (end is None or m <= str(end))]
    qs, rs = [], []
    for ym in months:
        unv = _resolve(universe, ym)
        exp = _resolve(exposures, ym)
        if unv is None or exp is None:
            if verbose:
                print(f"skip {ym}: no universe/exposures")
            continue
        try:
            rtn = returns(ym)
        except FileNotFoundError:
            if verbose:
                print(f"skip {ym}: no returns")
            continue
        exp = unv[["bid"]].merge(exp, on="bid", how="left")
        fmap = _factor_map(factors, exp)
        q, r = factor_returns_month(exp, rtn, fmap, n_groups, ret_col, ret_scale)
        qs.append(q)
        rs.append(r)
        if verbose:
            print(f"done {ym} (n={len(exp)}, returns {rtn.ymd.min()}-{rtn.ymd.max()})")
    if not qs:
        raise ValueError("no month could be computed")

    quint = pd.concat(qs, ignore_index=True)
    reg = pd.concat(rs, ignore_index=True)
    res = {
        "quintile_daily": quint,
        "regression_daily": reg,
        "quintile_summary": summarize(quint, "ret", ["factor", "grp"]),
        "regression_summary": summarize(reg, "coef", ["factor"]),
    }
    if out_dir is not None:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for k, v in res.items():
            v.to_csv(out_dir / f"{k}.csv", index=False)
    return res


# --- output helpers -------------------------------------------------------------


def summarize(df: pd.DataFrame, value: str, keys: list[str]) -> pd.DataFrame:
    """Annualized return / risk / RR from daily returns (simple sum, 252 days)."""
    g = df.groupby(keys)[value]
    out = pd.DataFrame(
        {
            "start": df.groupby(keys).ymd.min(),
            "end": df.groupby(keys).ymd.max(),
            "days": g.count(),
            "cum": g.sum(),
            "ann_ret": g.mean() * 252,
            "ann_risk": g.std() * np.sqrt(252),
            "hit": g.apply(lambda s: (s > 0).mean()),
        }
    )
    out["rr"] = out.ann_ret / out.ann_risk
    return out.reset_index()


def cumulative(
    res: dict[str, pd.DataFrame], kind: str = "quintile", grp: str = "Q5-Q1"
) -> pd.DataFrame:
    """Cumulative (simple sum) daily series, one column per factor, for plotting."""
    if kind == "quintile":
        d = res["quintile_daily"]
        d = d[d.grp == grp].pivot(index="ymd", columns="factor", values="ret")
    else:
        d = res["regression_daily"].pivot(index="ymd", columns="factor", values="coef")
    d.index = pd.to_datetime(d.index.astype(str), format="%Y%m%d")
    return d.fillna(0).cumsum()


def run_all(
    data_dir: Path = io.DATA_DIR, out_dir: Path | None = None
) -> dict[str, dict[str, pd.DataFrame]]:
    """Default run: AI / Revision / GEMQ3 on MSCI EM, total and specific returns.

    Writes data/gemq/fret/{ret,sret}/*.csv.
    """
    out_dir = Path(out_dir or data_dir / "fret")
    return {
        ret_col: run(
            universe=lambda ym: default_universe(ym, data_dir),
            exposures=lambda ym: default_exposures(ym, data_dir),
            factors=DEFAULT_FACTORS,
            returns=lambda ym: io.load_rtn(ym, data_dir),
            ret_col=ret_col,
            out_dir=out_dir / ret_col,
        )
        for ret_col in ("ret", "sret")
    }
