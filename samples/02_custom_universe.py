"""Change the universe.

`universe` is any function ym -> DataFrame with a "bid" column
(or a plain list of bids). Exposures stay the default AI / Revision / GEMQ3.
The excess return benchmark is the equal-weight mean of this universe.
"""

from p_ken import fret, io


# (a) China only (bid prefix CHN / HKG)
def china(ym: str):
    unv = io.load_unv(ym)
    return unv[unv.bid.str[:3].isin(["CHN", "HKG"])]


# (b) Top 300 by index weight
def top300(ym: str):
    return io.load_unv(ym).nlargest(300, "weight")


# (c) Excluding China, as a list of bids
def ex_china(ym: str) -> list[str]:
    unv = io.load_unv(ym)
    return unv.loc[~unv.bid.str[:3].isin(["CHN", "HKG"]), "bid"].tolist()


for name, universe in {"china": china, "top300": top300, "ex_china": ex_china}.items():
    res = fret.run(
        universe=universe,
        factors=fret.DEFAULT_FACTORS,
        start="202301",  # universe/exposure months from 2023/01 (end= also available)
        out_dir=f"data/gemq/fret/samples/02_{name}",
    )
    print(f"--- {name}")
    print(res["quintile_summary"].query("grp == 'Q5-Q1'").to_string(index=False))
