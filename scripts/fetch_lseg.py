# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "lseg-data>=2.1.1",
#     "pandas>=2.3",
# ]
# ///
"""Fetch market data from LSEG into data/index_return (self-contained, PEP 723).

Run from anywhere; uv installs lseg-data in an isolated environment:

    uv run scripts/fetch_lseg.py all                  # everything below
    uv run scripts/fetch_lseg.py indices              # MSCI EM / ACWI / World
    uv run scripts/fetch_lseg.py markets              # EM country + MSCI EM sector indices
    uv run scripts/fetch_lseg.py stocks               # stock weights + period returns
    uv run scripts/fetch_lseg.py --env-file ../datastream/.env stocks

Credentials: LSEG_APP_KEY, LSEG_USERNAME, LSEG_PASSWORD from the environment or
--env-file (default: .env at the repository root; existing env vars win).

indices  msci_{em,acwi,world}.csv
         dateymd, close, return, net, net_return, gross, gross_return
         (price / net / gross total-return index levels in USD, daily returns)
markets  {country,em_sector}_{close,return}_usd.csv   (one column per market)
         15 EM country indices (datastream universe.yaml, Korea = KOSPI, no
         Poland) converted to USD, and MSCI EM + its 11 sector price indices
stocks   stocks_<universe>_<start>_<end>.csv for data/{gemq,blf}
         sedol, bid, name, ric, country (HQ), sector (GICS), weight (universe
         file at the period end), base_date, end_date, return (USD, last close
         before start -> last close on or before end)
Returns are left blank across gaps longer than MAX_GAP_DAYS.
"""

import argparse
import os
import time
import tomllib
from datetime import date, timedelta
from pathlib import Path

import lseg.data as ld
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "index_return"
CREDENTIALS = ("LSEG_APP_KEY", "LSEG_USERNAME", "LSEG_PASSWORD")
USD_CLOSE = "TR.PriceClose(Curn=USD)"
CHUNK_YEARS = 5  # long histories are requested in pieces (row limit)
CHUNK_RICS = 50
MAX_GAP_DAYS = {"indices": 7, "markets": 10}

pd.set_option("future.no_silent_downcasting", True)  # silence a FutureWarning inside lseg

# --- universes of instruments ------------------------------------------------------------

MSCI_INDICES = {"EM": "MIEF", "ACWI": "MIWD", "World": "MIWO"}
MSCI_VARIANTS = {
    "P": ("close", "return"),
    "N": ("net", "net_return"),
    "G": ("gross", "gross_return"),
}

COUNTRIES = {  # RIC -> column (datastream universe.yaml; Korea = KOSPI, no Poland)
    ".KS11": "Korea",
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
}
EM_SECTORS = {  # MSCI EM sector code -> column; RIC = .MIEF{code}{P|N|G}US
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
STOCK_FIELDS = {
    "TR.RIC": "ric",
    "TR.CommonName": "name",
    "TR.HeadquartersCountry": "country",  # HQ country (HK-listed Chinese firms = China)
    "TR.GICSSector": "sector",
}

# --- session -------------------------------------------------------------------------------


def load_env_file(path: Path) -> None:
    """Minimal .env reader (KEY=VALUE lines). Existing env vars are kept."""
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.removeprefix("export ").strip(), value.strip().strip("'\""))


def open_session():
    missing = [k for k in CREDENTIALS if not os.environ.get(k)]
    if missing:
        raise SystemExit(f"missing credentials: {', '.join(missing)} (env or --env-file)")
    session = ld.session.platform.Definition(
        app_key=os.environ["LSEG_APP_KEY"],
        grant=ld.session.platform.GrantPassword(
            username=os.environ["LSEG_USERNAME"], password=os.environ["LSEG_PASSWORD"]
        ),
        signon_control=True,
    ).get_session()
    session.open()
    ld.session.set_default(session)
    return session


def _retry(fn, retries: int = 3):
    for attempt in range(retries):
        try:
            return fn()
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2**attempt)


# --- requests ------------------------------------------------------------------------------


def history(rics: list[str], field: str, start: str, end: str) -> pd.DataFrame:
    """Daily values (date x RIC), split into CHUNK_YEARS x CHUNK_RICS requests."""
    frames = []
    for i in range(0, len(rics), CHUNK_RICS):
        chunk = rics[i : i + CHUNK_RICS]
        parts = []
        s, e = date.fromisoformat(start), date.fromisoformat(end)
        while s <= e:
            nxt = s.replace(year=s.year + CHUNK_YEARS)
            stop = min(nxt - timedelta(days=1), e)
            df = _retry(
                lambda c=chunk, a=s, b=stop: ld.get_history(
                    universe=c,
                    fields=[field],
                    start=a.isoformat(),
                    end=b.isoformat(),
                    interval="1D",
                )
            )
            if len(chunk) == 1:  # a single RIC comes back with the field name as column
                df.columns = chunk
            parts.append(df)
            s = nxt
        frames.append(pd.concat(parts))
    out = pd.concat(frames, axis=1)
    out.index = pd.to_datetime(out.index)
    out.columns.name = None
    out = out[~out.index.duplicated(keep="last")].sort_index()
    out = out.loc[:, ~out.columns.duplicated()]
    return out.apply(pd.to_numeric, errors="coerce").reindex(columns=rics)


def daily_returns(level: pd.Series, max_gap_days: int) -> pd.Series:
    """Simple return vs the previous available value; NaN across long gaps."""
    s = level.dropna()
    r = s.pct_change()
    r[s.index.to_series().diff().dt.days > max_gap_days] = float("nan")
    return r


def _write(df: pd.DataFrame, path: Path) -> None:
    df = df.copy()
    df.insert(0, "dateymd", df.index.strftime("%Y%m%d"))
    df.to_csv(path, index=False)
    print(f"Saved: {path} ({len(df)} rows, {df.dateymd.iloc[0]}-{df.dateymd.iloc[-1]})")


# --- commands ----------------------------------------------------------------------------------


def fetch_indices(start: str, end: str, out_dir: Path = OUT_DIR) -> None:
    """MSCI EM / ACWI / World price, net and gross levels in USD."""
    rics = [f".{code}00000{v}US" for code in MSCI_INDICES.values() for v in MSCI_VARIANTS]
    wide = history(rics, "TR.PriceClose", start, end)
    for name, code in MSCI_INDICES.items():
        cols = {}
        for v, (level_col, ret_col) in MSCI_VARIANTS.items():
            level = wide[f".{code}00000{v}US"].dropna()
            cols[level_col] = level
            cols[ret_col] = daily_returns(level, MAX_GAP_DAYS["indices"])
        _write(pd.DataFrame(cols).sort_index(), out_dir / f"msci_{name.lower()}.csv")


def fetch_markets(start: str, end: str, sector_variant: str = "P", out_dir: Path = OUT_DIR) -> None:
    """EM country indices and MSCI EM sector indices, closes in USD."""
    groups = {
        "country": COUNTRIES,
        "em_sector": {f".MIEF{c}{sector_variant}US": n for c, n in EM_SECTORS.items()},
    }
    for group, names in groups.items():
        close = history(list(names), USD_CLOSE, start, end).dropna(how="all").rename(columns=names)
        ret = pd.DataFrame(
            {c: daily_returns(close[c], MAX_GAP_DAYS["markets"]) for c in close.columns}
        ).reindex(close.index)
        _write(close, out_dir / f"{group}_close_usd.csv")
        _write(ret, out_dir / f"{group}_return_usd.csv")


def fetch_stocks(universes: list[str], start: str, end: str, out_dir: Path = OUT_DIR) -> None:
    """Stock weights (universe file at the period end) and USD period returns."""
    end_ym = f"{date.fromisoformat(end):%Y%m}"
    weights = {}
    for u in universes:
        df = pd.read_csv(
            ROOT / "data" / u / "universe" / f"{end_ym}.csv",
            encoding="utf-8-sig",
            dtype={"sedol": str, "bid": str},
        )
        weights[u] = df.drop_duplicates("sedol")[["sedol", "bid", "weight"]]
    sedols = sorted(set().union(*(set(w.sedol) for w in weights.values())))

    print(f"info for {len(sedols)} SEDOLs")
    frames = []
    for i in range(0, len(sedols), CHUNK_RICS):
        universe = [f"{s}@SEDOL" for s in sedols[i : i + CHUNK_RICS]]
        frames.append(_retry(lambda u=universe: ld.get_data(universe=u, fields=list(STOCK_FIELDS))))
    info = pd.concat(frames, ignore_index=True)
    info.columns = ["sedol", *STOCK_FIELDS.values()]
    info["sedol"] = info["sedol"].str.replace("@SEDOL", "", regex=False)
    info = info.drop_duplicates("sedol")

    rics = info["ric"].dropna().unique().tolist()
    print(f"prices for {len(rics)} RICs")
    first = (date.fromisoformat(start) - timedelta(days=14)).isoformat()  # catch the base close
    prices = history(rics, USD_CLOSE, first, end).ffill()
    before = prices[prices.index < pd.Timestamp(start)]
    upto = prices[prices.index <= pd.Timestamp(end)]
    rets = pd.DataFrame(
        {
            "base_date": before.apply(lambda s: s.last_valid_index()),
            "end_date": upto.apply(lambda s: s.last_valid_index()),
            "return": upto.iloc[-1] / before.iloc[-1] - 1,
        }
    )
    info = info.join(rets, on="ric")

    tag = f"{start.replace('-', '')}_{end.replace('-', '')}"
    cols = [
        "sedol",
        "bid",
        "name",
        "ric",
        "country",
        "sector",
        "weight",
        "base_date",
        "end_date",
        "return",
    ]
    for u, w in weights.items():
        df = w.merge(info, on="sedol", how="left")[cols].sort_values("weight", ascending=False)
        path = out_dir / f"stocks_{u}_{tag}.csv"
        df.to_csv(path, index=False)
        ok = df["return"].notna()
        print(
            f"Saved: {path} ({len(df)} stocks, return for {ok.sum()} = "
            f"{df.loc[ok, 'weight'].sum():.1%} of weight, no RIC: {df.ric.isna().sum()})"
        )


def main() -> None:
    with open(ROOT / "config" / "report.toml", "rb") as f:
        period = tomllib.load(f)["period"]
    history_dates = {"start": "1999-01-01", "end": date.today().isoformat()}

    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR, help="default: data/index_return")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("indices", "markets"):
        p = sub.add_parser(name, help=f"{name} (full history by default)")
        p.add_argument("--start", default=history_dates["start"])
        p.add_argument("--end", default=history_dates["end"])
    sub.choices["markets"].add_argument(
        "--sector-variant", choices=["P", "N", "G"], default="P", help="P = price index"
    )
    p = sub.add_parser("stocks", help="weights + period returns (report period by default)")
    p.add_argument("--start", default=period["start"], help="default: config/report.toml")
    p.add_argument("--end", default=period["end"], help="default: config/report.toml")
    p.add_argument("--universes", nargs="+", default=["gemq", "blf"])
    sub.add_parser("all", help="indices + markets (full history) + stocks (report period)")
    args = parser.parse_args()

    if args.cmd == "all":
        jobs = [
            ("indices", history_dates),
            ("markets", history_dates),
            ("stocks", {"start": period["start"], "end": period["end"]}),
        ]
    else:
        jobs = [(args.cmd, {"start": args.start, "end": args.end})]

    load_env_file(args.env_file)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    session = open_session()
    try:
        for cmd, dates in jobs:
            print(f"[{cmd}] {dates['start']} - {dates['end']}")
            if cmd == "indices":
                fetch_indices(**dates, out_dir=args.out_dir)
            elif cmd == "markets":
                fetch_markets(
                    **dates,
                    sector_variant=getattr(args, "sector_variant", "P"),
                    out_dir=args.out_dir,
                )
            else:
                fetch_stocks(
                    getattr(args, "universes", ["gemq", "blf"]), **dates, out_dir=args.out_dir
                )
    finally:
        session.close()


if __name__ == "__main__":
    main()
