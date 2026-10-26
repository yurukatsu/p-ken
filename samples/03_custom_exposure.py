"""Your own exposures: a month-end table per ym, or one panel for all months.

uv run python samples/03_custom_exposure.py
"""

import pandas as pd

from p_ken import factors, io
from p_ken.stats import blom


# (a) function ym -> table (bid + factor columns) at ym end
def my_exposures(ym: str) -> pd.DataFrame:
    ai = io.load_ai(ym).drop_duplicates("bid").set_index("bid")
    rev = io.load_revision(ym).drop_duplicates("bid").set_index("bid")
    df = ai.join(rev, how="outer").fillna(0.0)
    df["ai70_rev30"] = blom(0.7 * df.ai + 0.3 * df.rev)  # AI 70% / Revision 30%
    qip = io.load_qip(ym).set_index("bid")
    df = df.join(qip.loc[qip.ctry == "CN", "invention_count_12m"].rename("qip"))  # China only
    return df[["ai70_rev30", "qip"]].reset_index()


src = factors.monthly(my_exposures)
reg = factors.regression_returns("gemq", src, "2026-01-01", "2026-09-30")
print("--- regression slope, sum Jul-Sep")
print(reg.loc["2026-07-01":].sum().map("{:+.2%}".format).to_string())

# quantile version: top decile excess return, and top - bottom
q10 = factors.quantile_returns("gemq", src, "2026-01-01", "2026-09-30", q=10)
spread = factors.quantile_returns("gemq", src, "2026-01-01", "2026-09-30", q=10, group="spread")
print("--- D10 excess / D10 - D1, sum Jul-Sep")
print(
    pd.DataFrame({"D10": q10.loc["2026-07-01":].sum(), "D10-D1": spread.loc["2026-07-01":].sum()})
    .map("{:+.2%}".format)
    .to_string()
)

# (b) one panel table with a ym column (e.g. read from a CSV of your own)
panel = pd.concat(
    [
        io.load_ai(ym).assign(ym=ym)
        for ym in io.list_yms("gemq", "exposures/nam/ai")
        if ym >= "202512"
    ],
    ignore_index=True,
)
ai = factors.regression_returns("gemq", factors.panel(panel), "2026-01-01", "2026-09-30")
print("--- AI from a panel, sum Jul-Sep:", f"{ai.loc['2026-07-01':, 'ai'].sum():+.2%}")
