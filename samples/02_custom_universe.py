"""Change the universe.

`universe` is any function exp_ym -> DataFrame with a "bid" column
(or a plain list of bids). Exposures stay the default AI / Revision / GEMQ3.
The excess return benchmark is the equal-weight mean of this universe.
"""

from p_ken import fret, io


# (a) China only (bid prefix CHN / HKG)
def china(exp_ym: str):
    unv = io.load_unv(exp_ym)
    return unv[unv.bid.str[:3].isin(["CHN", "HKG"])]


# (b) Top 300 by index weight
def top300(exp_ym: str):
    return io.load_unv(exp_ym).nlargest(300, "weight")


# (c) Excluding China, as a list of bids
def ex_china(exp_ym: str) -> list[str]:
    unv = io.load_unv(exp_ym)
    return unv.loc[~unv.bid.str[:3].isin(["CHN", "HKG"]), "bid"].tolist()


for name, universe in {"china": china, "top300": top300, "ex_china": ex_china}.items():
    res = fret.run(
        universe=universe,
        factors=fret.DEFAULT_FACTORS,
        start="202301",  # return months 2023/01 onward (end= also available)
        out_dir=f"data/GEMQ/fret/samples/02_{name}",
    )
    print(f"--- {name}")
    print(res["quintile_summary"].query("grp == 'Q5-Q1'").to_string(index=False))
