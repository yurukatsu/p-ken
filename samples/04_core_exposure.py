"""Core factors: a few single factors, and a value composite of your own.

uv run python samples/04_core_exposure.py
"""

import pandas as pd

from p_ken import factors, io
from p_ken.stats import zscore

# (a) selected core factors with the report's preset (Blom, missing -> 0)
src = factors.core_exposures("gemq", ["BP_EST", "EP_EST", "ROE_EST", "MOM12"])
daily = factors.regression_returns("gemq", src, "2026-01-01", "2026-09-30")
print("--- core factors, sum Jul-Sep")
print(daily.loc["2026-07-01":].sum().map("{:+.2%}".format).to_string())


# (b) a composite: mean z-score of every Stock / Flow Value factor
def value_composite(ym: str) -> pd.DataFrame:
    fl = io.load_core_list("gemq")
    cols = fl.loc[fl.type.isin(["Stock Value", "Flow Value"]), "variable"].tolist()
    bids = io.load_universe("gemq", ym).bid
    core = io.load_core("gemq", ym).set_index("bid").reindex(bids)
    x = core[[c for c in cols if c in core.columns]]
    return pd.DataFrame({"value_composite": zscore(x).mean(axis=1)}).rename_axis("bid")


comp = factors.regression_returns(
    "gemq", factors.monthly(value_composite), "2026-01-01", "2026-09-30"
)
print(
    "--- value composite, sum Jul-Sep:", f"{comp.loc['2026-07-01':, 'value_composite'].sum():+.2%}"
)
