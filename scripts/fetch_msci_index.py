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

Credentials: LSEG_APP_KEY, LSEG_USERNAME, LSEG_PASSWORD, taken from the
environment or from --env-file (default: .env; existing env vars win).

Output (long format), default data/index_return/msci.csv:
    dateymd, index, variant, ric, close, return
  index:   EM / ACWI / World
  variant: price / net / gross (price = price return index, net / gross =
           total return with net / gross dividends reinvested)
  close:   daily closing index level (TR.PriceClose)
  return:  daily simple return of close; NaN for the first row and when the
           previous value is more than MAX_GAP_DAYS earlier (LSEG history before
           ~2007 has gaps / monthly-only values for some series)
"""

import argparse
import os
from datetime import date, timedelta
from pathlib import Path

import lseg.data as ld
import pandas as pd

INDICES = {"EM": "MIEF", "ACWI": "MIWD", "World": "MIWO"}
VARIANTS = {"price": "P", "net": "N", "gross": "G"}
RICS = {
    f".{code}00000{v}US": (name, variant)
    for name, code in INDICES.items()
    for variant, v in VARIANTS.items()
}
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


def fetch(start: str, end: str) -> pd.DataFrame:
    """Wide frame: index = date, columns = RIC."""
    frames = []
    s, e = date.fromisoformat(start), date.fromisoformat(end)
    while s <= e:
        nxt = s.replace(year=s.year + CHUNK_YEARS)
        chunk_end = min(nxt - timedelta(days=1), e)
        df = ld.get_history(
            universe=list(RICS),
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
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args()

    load_env_file(args.env_file)
    session = open_session()
    try:
        wide = fetch(args.start, args.end)
    finally:
        session.close()
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
