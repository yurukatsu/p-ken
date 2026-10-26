"""Ready-made factor sets used in the report.

common (core) factors - both universes
    exposures: core factors at the previous month end, Blom score over the
    universe with missing -> 0 (exp_em), then the engine's daily Blom score.
    type returns: equal-weight mean of the factor returns of each fc_list type.

NAM factors
    gemq (MSCI EM): AI, Revision, GEMQ3 at the previous month end
    blf (RGA):      AI, TVL, RVL, ai70_bd30 from the daily score files
                    (latest file before each return date)
    method "q5": mean excess return of the top quintile instead of the slope
    (gemq: R fret_nam_monitor, blf: archive BLF.fret_nam_daily, CN=False).
"""

import pandas as pd

from p_ken import io
from p_ken.factors import sources
from p_ken.factors.engine import MISSING_BELOW, quantile_returns, regression_returns
from p_ken.stats import blom

# --- common (core) factors --------------------------------------------------------


def core_factor_list(universe: str) -> pd.DataFrame:
    """fc_list.csv of the universe: variable, type."""
    return io.load_core_list(universe)


def core_exposures(universe: str, factors: list[str] | None = None) -> sources.ExposureFn:
    """Core exposures at ym end: universe stocks, Blom score per factor, missing -> 0."""
    factors = factors or core_factor_list(universe).variable.tolist()

    def load(ym: str) -> pd.DataFrame:
        bids = io.load_universe(universe, ym).bid.drop_duplicates()
        core = io.load_core(universe, ym).set_index("bid").reindex(bids)
        x = core[[f for f in factors if f in core.columns]].astype(float)
        return blom(x.mask(x <= MISSING_BELOW)).fillna(0.0)

    return sources.monthly(load)


def core_factor_returns(
    universe: str, start: str, end: str | None = None, ret_col: str = "ret"
) -> pd.DataFrame:
    """Daily common factor returns (one column per core factor)."""
    return regression_returns(universe, core_exposures(universe), start, end, ret_col)


def type_returns(daily: pd.DataFrame, universe: str) -> pd.DataFrame:
    """Equal-weight mean of factor returns per fc_list type (fc_list order)."""
    fl = core_factor_list(universe)
    fl = fl[fl.variable.isin(daily.columns)]
    order = list(dict.fromkeys(fl.type))
    return pd.DataFrame({t: daily[fl.loc[fl.type == t, "variable"]].mean(axis=1) for t in order})


# --- NAM factors ----------------------------------------------------------------------

# MSCI EM: output name -> column of the month-end score table
GEMQ_NAM = {"AI": "ai", "Revision": "rev", "GEMQ3": "Gousei_3Factor"}
# RGA: output name -> (daily score file kind, column)
BLF_NAM = {
    "AI": ("ai", "ai"),
    "TVL": ("bigdata", "tvl"),
    "RVL": ("bigdata", "rvl"),
    "Composite (ai70_bd30)": ("ai", "ai70_bd30"),
}


def gemq_nam_table(ym: str) -> pd.DataFrame:
    """MSCI EM month-end NAM scores for the universe at ym (universe order).

    AI and Revision are the raw files (missing = NaN); GEMQ3 comes from
    p_ken.gemq3 (missing already 0).
    """
    ai = io.load_ai(ym).drop_duplicates("bid").set_index("bid")
    rev = io.load_revision(ym).drop_duplicates("bid").set_index("bid")
    gem = io.load_gemq3(ym).set_index("bid")[["Gousei_3Factor"]]
    scores = ai.join(rev, how="outer").join(gem, how="outer")
    unv = io.load_universe("gemq", ym)[["bid"]]
    table = unv.join(scores, on="bid").set_index("bid")
    return table[list(GEMQ_NAM.values())].set_axis(list(GEMQ_NAM), axis=1)


def nam_exposures(universe: str, timing: str = "default") -> sources.ExposureFn:
    """NAM exposure source. timing="month_end" = archive BLF timing (RGA only)."""
    if universe == "gemq":
        return sources.monthly(gemq_nam_table)
    if timing == "month_end":
        return sources.month_end_scores(BLF_NAM, universe)
    return sources.daily_scores(BLF_NAM, universe)


def nam_factor_returns(
    universe: str,
    start: str,
    end: str | None = None,
    ret_col: str = "ret",
    method: str = "regression",
    q: int = 5,
) -> pd.DataFrame:
    """Daily NAM factor returns. method: "regression" (default) or "q5"."""
    if method == "regression":
        return regression_returns(universe, nam_exposures(universe), start, end, ret_col)
    if method != "q5":
        raise ValueError(f"method must be 'regression' or 'q5', not {method!r}")
    if universe == "gemq":
        return quantile_returns(
            universe, nam_exposures(universe), start, end, ret_col, q=q, breakpoints="formation"
        )
    return quantile_returns(
        universe,
        nam_exposures(universe, timing="month_end"),
        start,
        end,
        ret_col,
        q=q,
        breakpoints="pooled",
    )
