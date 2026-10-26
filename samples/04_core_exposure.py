"""Core factors (data/gemq/exposures/core) as exposures.

io.load_core(ym) returns bid + every core factor, with the missing sentinel
(-999999998) turned into NaN. Factor names / categories: io.load_core_list().
"""

import pandas as pd

from p_ken import fret, io

print(io.load_core_list().groupby("type").variable.apply(list).to_string())

# (a) A few raw core factors
res = fret.run(
    exposures=io.load_core,
    factors={"B/P": "BP_EST", "E/P": "EP_EST", "ROE": "ROE_EST", "MOM12": "MOM12"},
    out_dir="data/gemq/fret/samples/04_core",
)
print("--- core factors")
print(res["quintile_summary"].query("grp == 'Q5-Q1'").to_string(index=False))


# (b) Every factor in one category, z-scored within the universe each month
def value_z(ym: str) -> pd.DataFrame:
    unv = io.load_unv(ym)[["bid"]]
    core = unv.merge(io.load_core(ym), on="bid", how="left")
    cols = io.load_core_list().query("type == 'Stock Value' or type == 'Flow Value'")
    cols = [c for c in cols.variable if c in core.columns]
    z = (core[cols] - core[cols].mean()) / core[cols].std()
    return pd.DataFrame({"bid": core.bid, "value_composite": z.mean(axis=1)})


res = fret.run(exposures=value_z, out_dir="data/gemq/fret/samples/04_value_z")
print("--- value composite")
print(res["quintile_summary"].query("grp == 'Q5-Q1'").to_string(index=False))
