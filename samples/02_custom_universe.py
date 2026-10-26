"""Narrow the universe: `stocks=` takes ym -> bids (applied to every day of the next month).

uv run python samples/02_custom_universe.py
"""

from p_ken import factors, io


def china(ym: str) -> list[str]:  # listing prefix CHN / HKG
    unv = io.load_universe("gemq", ym)
    return unv.loc[unv.bid.str[:3].isin(["CHN", "HKG"]), "bid"].tolist()


def top300(ym: str) -> list[str]:  # largest 300 by index weight
    return io.load_universe("gemq", ym).nlargest(300, "weight").bid.tolist()


def ex_china(ym: str) -> list[str]:
    unv = io.load_universe("gemq", ym)
    return unv.loc[~unv.bid.str[:3].isin(["CHN", "HKG"]), "bid"].tolist()


exposures = factors.nam_exposures("gemq")  # AI, Revision, GEMQ3 at the previous month end
for name, stocks in {"china": china, "top300": top300, "ex_china": ex_china}.items():
    daily = factors.regression_returns("gemq", exposures, "2026-01-01", "2026-09-30", stocks=stocks)
    print(f"--- {name}: sum Jul-Sep")
    print(daily.loc["2026-07-01":].sum().map("{:+.2%}".format).to_string())
