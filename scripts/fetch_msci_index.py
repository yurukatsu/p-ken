# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "lseg-data>=2.1.1",
#     "pandas>=2.3",
# ]
# ///
"""Fetch daily MSCI EM / ACWI / World index levels (USD) from LSEG.

Self-contained: dependencies are declared above (PEP 723), so uv installs them
in an isolated environment. Run from the p-ken root:

    uv run scripts/fetch_msci_index.py
    uv run scripts/fetch_msci_index.py --start 2018-01-01 --env-file ../datastream/.env
    uv run scripts/fetch_msci_index.py --indices EM ACWI

Credentials: LSEG_APP_KEY, LSEG_USERNAME, LSEG_PASSWORD, taken from the
environment or from --env-file (default: .env; existing env vars win).

Output: one file per index in --out-dir (default data/index_return):
    msci_em.csv, msci_acwi.csv, msci_world.csv
  columns: dateymd, close, return, net, net_return, gross, gross_return
    close / return             price index (no dividends)
    net / net_return           net total return index (net dividends reinvested)
    gross / gross_return       gross total return index
  Levels are daily closes in USD (TR.PriceClose). Returns are daily simple
  returns of each level; NaN on the first day and when the previous value is
  more than MAX_GAP_DAYS earlier (LSEG history before ~2007 has gaps /
  monthly-only values for some series). Dates where a level is missing are
  left blank for that level.
"""

import argparse
import os
from datetime import date, timedelta
from pathlib import Path

import lseg.data as ld
import pandas as pd

INDICES = {"EM": "MIEF", "ACWI": "MIWD", "World": "MIWO"}
# variant code -> (level column, return column)
VARIANTS = {
    "P": ("close", "return"),
    "N": ("net", "net_return"),
    "G": ("gross", "gross_return"),
}


def ric(index: str, variant: str) -> str:
    return f".{INDICES[index]}00000{variant}US"


CHUNK_YEARS = 5  # split long ranges to stay under the per-request row limit
MAX_GAP_DAYS = 7
CREDENTIALS = ("LSEG_APP_KEY", "LSEG_USERNAME", "LSEG_PASSWORD")

pd.set_option(
    "future.no_silent_downcasting", True
)  # silence a FutureWarning inside lseg


def load_env_file(path: Path) -> None:
    """Minimal .env reader (KEY=VALUE lines). Existing env vars are kept."""
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.removeprefix("export ").strip()
        os.environ.setdefault(key, value.strip().strip("'\""))


def open_session():
    missing = [k for k in CREDENTIALS if not os.environ.get(k)]
    if missing:
        raise SystemExit(
            f"missing credentials: {', '.join(missing)} (env or --env-file)"
        )
    session = ld.session.platform.Definition(
        app_key=os.environ["LSEG_APP_KEY"],
        grant=ld.session.platform.GrantPassword(
            username=os.environ["LSEG_USERNAME"],
            password=os.environ["LSEG_PASSWORD"],
        ),
        signon_control=True,
    ).get_session()
    session.open()
    ld.session.set_default(session)
    return session


def fetch(rics: list[str], start: str, end: str) -> pd.DataFrame:
    """Wide frame: index = date, columns = RIC."""
    frames = []
    s, e = date.fromisoformat(start), date.fromisoformat(end)
    while s <= e:
        nxt = s.replace(year=s.year + CHUNK_YEARS)
        chunk_end = min(nxt - timedelta(days=1), e)
        df = ld.get_history(
            universe=rics,
            fields=["TR.PriceClose"],
            start=s.isoformat(),
            end=chunk_end.isoformat(),
            interval="1D",
        )
        frames.append(df)
        s = nxt
    wide = pd.concat(frames)
    wide.index = pd.to_datetime(wide.index)
    wide.columns.name = None
    wide = wide[~wide.index.duplicated(keep="last")].sort_index()
    if len(rics) == 1:  # a single RIC comes back with the field name as column
        wide.columns = rics
    return wide.apply(pd.to_numeric, errors="coerce")


def daily_return(level: pd.Series) -> pd.Series:
    """Simple return; NaN across gaps longer than MAX_GAP_DAYS."""
    level = level.dropna()
    ret = level.pct_change()
    gap = level.index.to_series().diff().dt.days
    ret[gap > MAX_GAP_DAYS] = float("nan")
    return ret


def index_frame(wide: pd.DataFrame, index: str) -> pd.DataFrame:
    """dateymd, close, return, net, net_return, gross, gross_return for one index."""
    cols = {}
    for v, (level_col, ret_col) in VARIANTS.items():
        level = wide.get(ric(index, v), pd.Series(dtype=float)).dropna()
        cols[level_col] = level
        cols[ret_col] = daily_return(level)
    out = pd.DataFrame(cols).sort_index()  # union of dates
    out.insert(0, "dateymd", out.index.strftime("%Y%m%d"))
    return out.reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--start", default="1999-01-01", help="YYYY-MM-DD")
    parser.add_argument("--end", default=date.today().isoformat(), help="YYYY-MM-DD")
    parser.add_argument(
        "--indices", nargs="+", choices=list(INDICES), default=list(INDICES)
    )
    parser.add_argument("--out-dir", type=Path, default=Path("data/index_return"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args()

    load_env_file(args.env_file)
    session = open_session()
    try:
        rics = [ric(i, v) for i in args.indices for v in VARIANTS]
        wide = fetch(rics, args.start, args.end)
    finally:
        session.close()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for index in args.indices:
        df = index_frame(wide, index)
        path = args.out_dir / f"msci_{index.lower()}.csv"
        df.to_csv(path, index=False)
        first = {
            c: df.loc[df[c].notna(), "dateymd"].min() for c in ("close", "net", "gross")
        }
        print(
            f"Saved: {path} ({len(df)} rows, {df.dateymd.min()}-{df.dateymd.max()}, "
            f"first close/net/gross: {first['close']}/{first['net']}/{first['gross']})"
        )


if __name__ == "__main__":
    main()
