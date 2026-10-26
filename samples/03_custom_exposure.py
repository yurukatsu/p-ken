"""Change the exposures.

`exposures` is either
  - a function ym -> DataFrame with "bid" + factor columns, or
  - a panel DataFrame with "ym", "bid" + factor columns (e.g. read from one CSV).
NaN exposures are excluded from quintiles / regressions for that factor.
"""

import pandas as pd

from p_ken import fret, gemq3, io


# (a) Function: build new factors from the existing scores
def my_exposures(ym: str) -> pd.DataFrame:
    ai = io.load_ai(ym).drop_duplicates("bid").set_index("bid")
    rev = io.load_revision(ym).drop_duplicates("bid").set_index("bid")
    df = ai.join(rev, how="outer").fillna(0.0)
    # AI 70% / Revision 30% blend, re-ranked to a blom score
    df["ai70_rev30"] = gemq3.calc_blom_score(0.7 * df.ai + 0.3 * df.rev)

    # QIP patent count (China only; other stocks NaN -> excluded)
    try:
        qip = io.load_qip(ym).set_index("bid")
        df = df.join(qip.loc[qip.ctry == "CN", "invention_count_12m"].rename("qip"))
    except FileNotFoundError:
        df["qip"] = float("nan")
    return df.reset_index()[["bid", "ai70_rev30", "qip"]]


res = fret.run(
    exposures=my_exposures,
    factors=None,  # None = every numeric column (ai70_rev30, qip)
    out_dir="data/gemq/fret/samples/03_function",
)
print("--- function")
print(res["quintile_summary"].query("grp == 'Q5-Q1'").to_string(index=False))


# (b) Panel DataFrame: one table with ym, bid, <factors>
#     e.g. panel = pd.read_csv("my_scores.csv", dtype={"ym": str})
#     Here it is built from the AI files to show the expected shape.
panel = pd.concat(
    [
        io.load_ai(ym).assign(ym=ym)
        for ym in io.list_yms("exposures/nam/ai")
        if ym >= "201801"
    ],
    ignore_index=True,
)[["ym", "bid", "ai"]]

res = fret.run(
    exposures=panel,
    factors={"AI_from_panel": "ai"},
    n_groups=10,  # deciles: Q1..Q10 and Q10-Q1
    out_dir="data/gemq/fret/samples/03_panel",
)
print("--- panel (deciles)")
print(res["quintile_summary"].query("grp == 'Q10-Q1'").to_string(index=False))
