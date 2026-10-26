# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "lseg-data>=2.1.1",
#     "pandas>=2.3",
# ]
# ///
"""Fetch daily USD index levels for EM countries and MSCI EM sectors from LSEG.

Universe follows ../datastream/configs/universe.yaml (countries, sectors), with
Korea = KOSPI (.KS11) instead of KOSPI 100. Self-contained (PEP 723). Run from
the p-ken root:

    uv run scripts/fetch_em_markets.py
    uv run scripts/fetch_em_markets.py --start 2025-12-01 --groups country
    uv run scripts/fetch_em_markets.py --sector-variant net

Credentials: LSEG_APP_KEY, LSEG_USERNAME, LSEG_PASSWORD from the environment or
--env-file (default: .env; existing env vars win).

Output in --out-dir (default data/index_return), one column per market:
    country_close_usd.csv    country_return_usd.csv
    em_sector_close_usd.csv  em_sector_return_usd.csv
  close:  daily close in USD (TR.PriceClose(Curn=USD); local index converted at
          that day's FX). Country indices are price indices; sectors are MSCI EM
          sector price indices (--sector-variant net for net total return).
  return: daily simple return of close, from the previous available close of the
          same market (local holidays are blank); NaN across gaps > MAX_GAP_DAYS.
"""

import argparse
import os
from datetime import date, timedelta
from pathlib import Path

import lseg.data as ld
import pandas as pd

FIELD = "TR.PriceClose(Curn=USD)"

# RIC -> column name
COUNTRIES = {
    ".KS11": "Korea",  # KOSPI (datastream uses KOSPI 100: .KS100)
    ".CSI300": "China",
    ".HSI": "Hong Kong",
    ".TWII": "Taiwan",
    ".PSI": "Philippines",
    ".SETI": "Thailand",
    ".JKSE": "Indonesia",
    ".KLSE": "Malaysia",
    ".BSESN": "India",
    ".XU100": "Turkey",
    ".FTFADGI": "UAE",
    ".TASI": "Saudi Arabia",
    ".JALSH": "South Africa",
    ".MXX": "Mexico",
    ".BVSP": "Brazil",
    ".WIG": "Poland",
}

# MSCI EM sector code -> column name; RIC = .MIEF{code}{P|N}US
SECTORS = {
    "00000": "MSCI EM",
    "0EN00": "Energy",
    "0MT00": "Materials",
    "0IN00": "Industrials",
    "0CD00": "Consumer Discretionary",
    "0CS00": "Consumer Staples",
    "0HC00": "Health Care",
    "0FN00": "Financials",
    "0IT00": "Information Technology",
    "0TC00": "Communication Services",
    "0UT00": "Utilities",
    "0RS00": "Real Estate",
}
SECTOR_VARIANTS = {"price": "P", "net": "N", "gross": "G"}

CHUNK_YEARS = 5  # split long ranges to stay under the per-request row limit
MAX_GAP_DAYS = 10
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
    """Wide frame of USD closes: index = date, columns = RIC."""
    frames = []
    s, e = date.fromisoformat(start), date.fromisoformat(end)
    while s <= e:
        nxt = s.replace(year=s.year + CHUNK_YEARS)
        chunk_end = min(nxt - timedelta(days=1), e)
        df = ld.get_history(
            universe=rics,
            fields=[FIELD],
            start=s.isoformat(),
            end=chunk_end.isoformat(),
            interval="1D",
        )
        if len(rics) == 1:  # a single RIC comes back with the field name as column
            df.columns = rics
        frames.append(df)
        s = nxt
    wide = pd.concat(frames)
    wide.index = pd.to_datetime(wide.index)
    wide.columns.name = None
    wide = wide[~wide.index.duplicated(keep="last")].sort_index()
    wide = wide.apply(pd.to_numeric, errors="coerce")
    return wide.reindex(columns=rics).dropna(how="all")


def daily_returns(close: pd.DataFrame) -> pd.DataFrame:
    """Per column: return vs the previous available close; NaN across long gaps."""
    out = {}
    for col in close.columns:
        s = close[col].dropna()
        r = s.pct_change()
        r[s.index.to_series().diff().dt.days > MAX_GAP_DAYS] = float("nan")
        out[col] = r
    return pd.DataFrame(out).reindex(close.index)


def save(close: pd.DataFrame, out_dir: Path, stem: str) -> None:
    ret = daily_returns(close)
    for kind, df in (("close", close), ("return", ret)):
        df = df.copy()
        df.insert(0, "dateymd", df.index.strftime("%Y%m%d"))
        path = out_dir / f"{stem}_{kind}_usd.csv"
        df.to_csv(path, index=False)
        print(
            f"Saved: {path} ({len(df)} rows, {df.dateymd.iloc[0]}-{df.dateymd.iloc[-1]})"
        )
    first = close.apply(lambda s: s.first_valid_index())
    last = close.apply(lambda s: s.last_valid_index())
    print(pd.DataFrame({"first": first.dt.date, "last": last.dt.date}).to_string())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--start", default="1999-01-01", help="YYYY-MM-DD")
    parser.add_argument("--end", default=date.today().isoformat(), help="YYYY-MM-DD")
    parser.add_argument(
        "--groups",
        nargs="+",
        choices=["country", "em_sector"],
        default=["country", "em_sector"],
    )
    parser.add_argument(
        "--sector-variant", choices=list(SECTOR_VARIANTS), default="price"
    )
    parser.add_argument("--out-dir", type=Path, default=Path("data/index_return"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args()

    v = SECTOR_VARIANTS[args.sector_variant]
    groups = {
        "country": COUNTRIES,
        "em_sector": {f".MIEF{code}{v}US": name for code, name in SECTORS.items()},
    }

    load_env_file(args.env_file)
    session = open_session()
    try:
        closes = {
            g: fetch(list(groups[g]), args.start, args.end).rename(columns=groups[g])
            for g in args.groups
        }
    finally:
        session.close()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for g, close in closes.items():
        save(close, args.out_dir, g)


if __name__ == "__main__":
    main()
