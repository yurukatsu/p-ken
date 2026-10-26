"""Fetch daily MSCI EM / ACWI / World index levels (USD) from LSEG.

Uses LSEGClient from the sibling `datastream` project (credentials in its .env),
so run it with that project's environment from the p-ken root:

    uv run --project ../datastream python scripts/fetch_msci_index.py
    uv run --project ../datastream python scripts/fetch_msci_index.py --start 2018-01-01

Output (long format), default data/index_return/msci.csv:
    dateymd, index, variant, ric, close, return
  index:   EM / ACWI / World
  variant: price / net / gross (net = net total return)
  return:  daily simple return of close; NaN for the first row and when the
           previous value is more than MAX_GAP_DAYS earlier (LSEG history before
           ~2007 has gaps / monthly-only values for some series)
"""

import argparse
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from marketdata import LSEGClient

INDICES = {"EM": "MIEF", "ACWI": "MIWD", "World": "MIWO"}
VARIANTS = {"price": "P", "net": "N", "gross": "G"}
RICS = {
    f".{code}00000{v}US": (name, variant)
    for name, code in INDICES.items()
    for variant, v in VARIANTS.items()
}
CHUNK_YEARS = 5  # split long ranges to stay under the per-request row limit
MAX_GAP_DAYS = 7


def fetch(client: LSEGClient, start: str, end: str) -> pd.DataFrame:
    """Wide frame: index = date, columns = RIC."""
    frames = []
    s, e = date.fromisoformat(start), date.fromisoformat(end)
    while s <= e:
        nxt = s.replace(year=s.year + CHUNK_YEARS)
        chunk_end = min(nxt - timedelta(days=1), e)
        df = client.get_history(
            universe=list(RICS),
            fields=["TR.PriceClose"],
            start=s.isoformat(),
            end=chunk_end.isoformat(),
        )
        frames.append(df)
        s = nxt
    wide = pd.concat(frames)
    wide.index = pd.to_datetime(wide.index)
    wide.columns.name = None
    wide = wide[~wide.index.duplicated(keep="last")].sort_index()
    return wide.apply(pd.to_numeric, errors="coerce")


def to_long(wide: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for ric, (name, variant) in RICS.items():
        s = wide[ric].dropna() if ric in wide else pd.Series(dtype=float)
        ret = s.pct_change()
        gap = s.index.to_series().diff().dt.days
        ret[gap > MAX_GAP_DAYS] = float("nan")
        rows.append(
            pd.DataFrame(
                {
                    "dateymd": s.index.strftime("%Y%m%d"),
                    "index": name,
                    "variant": variant,
                    "ric": ric,
                    "close": s.to_numpy(),
                    "return": ret.to_numpy(),
                }
            )
        )
    return pd.concat(rows, ignore_index=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--start", default="1999-01-01", help="YYYY-MM-DD")
    parser.add_argument("--end", default=date.today().isoformat(), help="YYYY-MM-DD")
    parser.add_argument("--out", type=Path, default=Path("data/index_return/msci.csv"))
    args = parser.parse_args()

    with LSEGClient() as client:
        wide = fetch(client, args.start, args.end)
    long = to_long(wide)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    long.to_csv(args.out, index=False)
    summary = long.groupby(["index", "variant"]).agg(
        start=("dateymd", "min"), end=("dateymd", "max"), rows=("close", "size")
    )
    print(summary.to_string())
    print(f"Saved: {args.out} ({len(long)} rows)")


if __name__ == "__main__":
    main()
