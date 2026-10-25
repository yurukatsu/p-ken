"""Daily factor returns for AI, Revision and GEMQ3.

Follows fret_nam_monitor() in archive/msci_lib.R.r:
  - exposures are taken at the previous month end (exp_ym = ym - 1)
  - universe = MSCI EM constituents at exp_ym
  - daily excess return = ret - equal-weight mean of the universe (that day)

Two definitions are produced:
  - quintile:   mean excess return per quintile (dplyr::ntile, Q5 = highest)
                plus Q5-Q1
  - regression: per day OLS  excess_ret = a + b * exposure  (one factor at a time)

Returns are in decimals (the source files are in percent).
"""

from pathlib import Path

import numpy as np
import pandas as pd

from p_ken import io

FACTORS = {"AI": "ai", "Revision": "rev", "GEMQ3": "Gousei_3Factor"}
N_GROUPS = 5


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


def load_exposures(exp_ym: str, data_dir: Path = io.DATA_DIR) -> pd.DataFrame:
    """Universe at exp_ym with ai, rev and Gousei_3Factor (NaN when missing).

    As in fret_nam_monitor, AI / Revision are raw (NaN excluded from quintiles)
    while GEMQ3 comes from get_gemq3 (missing already filled with 0).
    """
    unv = io.load_unv(exp_ym, data_dir)[["bid"]]
    ai = io.load_ai(exp_ym, data_dir).drop_duplicates("bid").set_index("bid")
    rev = io.load_revision(exp_ym, data_dir).drop_duplicates("bid").set_index("bid")
    gem = io.load_gemq3(exp_ym, data_dir).set_index("bid")[["Gousei_3Factor"]]
    return unv.join(ai, on="bid").join(rev, on="bid").join(gem, on="bid")


def _ols(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    """Slope, its t-stat and intercept of y = a + b x."""
    n = len(x)
    if n < 3:
        return np.nan, np.nan, np.nan
    xm = x - x.mean()
    sxx = (xm**2).sum()
    b = (xm * (y - y.mean())).sum() / sxx
    a = y.mean() - b * x.mean()
    resid = y - a - b * x
    se = np.sqrt((resid**2).sum() / (n - 2) / sxx)
    return b, b / se if se > 0 else np.nan, a


def factor_returns_month(
    ym: str, data_dir: Path = io.DATA_DIR
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Quintile and regression factor returns for each day of month ym."""
    exp = load_exposures(io.prev_ym(ym), data_dir)
    for name, col in FACTORS.items():
        exp[f"q_{name}"] = ntile(exp[col])

    rtn = io.load_rtn(ym, data_dir)
    rtn = rtn[rtn.bid.isin(exp.bid)].copy()
    rtn["dret"] = (rtn.ret - rtn.groupby("ymd").ret.transform("mean")) / 100
    df = rtn.merge(exp, on="bid", how="inner")

    q_rows, r_rows = [], []
    for name, col in FACTORS.items():
        g = (
            df.dropna(subset=[f"q_{name}", "dret"])
            .groupby(["ymd", f"q_{name}"])
            .dret.agg(["mean", "size"])
            .reset_index()
        )
        g.columns = ["ymd", "grp", "ret", "n"]
        g["grp"] = "Q" + g.grp.astype(int).astype(str)
        wide = g.pivot(index="ymd", columns="grp", values="ret")
        ls = (wide[f"Q{N_GROUPS}"] - wide["Q1"]).rename("ret").reset_index()
        ls["grp"], ls["n"] = f"Q{N_GROUPS}-Q1", np.nan
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


def run_all(
    data_dir: Path = io.DATA_DIR, out_dir: Path | None = None
) -> dict[str, pd.DataFrame]:
    """Compute factor returns for every month that has returns and prior exposures."""
    out_dir = out_dir or data_dir / "fret"
    out_dir.mkdir(parents=True, exist_ok=True)
    have_exp = set(io.list_yms("scores/gemq3", data_dir))
    qs, rs = [], []
    for ym in io.list_yms("rtn", data_dir):
        if io.prev_ym(ym) not in have_exp:
            continue
        q, r = factor_returns_month(ym, data_dir)
        qs.append(q)
        rs.append(r)
    quint = pd.concat(qs, ignore_index=True)
    reg = pd.concat(rs, ignore_index=True)
    res = {
        "quintile_daily": quint,
        "regression_daily": reg,
        "quintile_summary": summarize(quint, "ret", ["factor", "grp"]),
        "regression_summary": summarize(reg, "coef", ["factor"]),
    }
    for k, v in res.items():
        v.to_csv(out_dir / f"{k}.csv", index=False)
    return res
