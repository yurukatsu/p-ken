"""Daily factor returns (formulas: docs/methodology.md).

Default: the local-currency return of each stock regressed, one factor at a
time, on its Blom-standardized exposure; the slope is the factor return.

    from p_ken import factors

    # common (core) factors, by type
    daily = factors.core_factor_returns("gemq", "2026-01-01", "2026-09-30")
    by_type = factors.type_returns(daily, "gemq")

    # NAM factors (regression, or method="q5")
    nam = factors.nam_factor_returns("blf", "2026-01-01", "2026-09-30")

    # your own exposures: month-end table per ym -> regression
    src = factors.monthly(lambda ym: my_table(ym))   # bid + factor columns
    mine = factors.regression_returns("gemq", src, "2026-01-01")
"""

from p_ken.factors.engine import (
    MAX_ABS_RET,
    MISSING_BELOW,
    STANDARDIZE,
    ExposureFn,
    iter_days,
    quantile_returns,
    regression_returns,
)
from p_ken.factors.presets import (
    BLF_NAM,
    GEMQ_NAM,
    core_exposures,
    core_factor_list,
    core_factor_returns,
    gemq_nam_table,
    nam_exposures,
    nam_factor_returns,
    type_returns,
)
from p_ken.factors.sources import daily_scores, month_end_scores, monthly, panel

__all__ = [
    "BLF_NAM",
    "GEMQ_NAM",
    "MAX_ABS_RET",
    "MISSING_BELOW",
    "STANDARDIZE",
    "ExposureFn",
    "core_exposures",
    "core_factor_list",
    "core_factor_returns",
    "daily_scores",
    "gemq_nam_table",
    "iter_days",
    "month_end_scores",
    "monthly",
    "nam_exposures",
    "nam_factor_returns",
    "panel",
    "quantile_returns",
    "regression_returns",
    "type_returns",
]
