"""Default factor returns: NAM factors on MSCI EM (AI, Revision, GEMQ3).

Local-currency return regressed on the Blom-standardized exposure, one factor
at a time; the slope is the daily factor return (docs/methodology.md).

    uv run python samples/01_default.py
"""

from p_ken import factors
from p_ken.stats import annualized

for ret_col in ["ret", "sret"]:  # local-currency total / specific return
    daily = factors.nam_factor_returns("gemq", "2026-01-01", "2026-09-30", ret_col)
    print(
        f"=== {ret_col}  (sum Jul-Sep: "
        + ", ".join(f"{k} {v:+.2%}" for k, v in daily.loc["2026-07-01":].sum().items())
        + ")"
    )
    print(annualized(daily).round(4).to_string())
