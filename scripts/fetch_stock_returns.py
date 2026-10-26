# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "lseg-data>=2.1.1",
#     "pandas>=2.3",
# ]
# ///
"""Fetch USD period returns of universe stocks from LSEG (for the treemaps).

Follows ../datastream (marketdata weekly report): SEDOL -> RIC / name / HQ
country / GICS sector via "{sedol}@SEDOL", then daily TR.PriceClose(Curn=USD)
in chunks. The return is from the last close before --start to the last close
on or before --end. Weights come from data/<universe>/universe/<weight-ym>.csv.
Self-contained (PEP 723). Run from the p-ken root:

    uv run scripts/fetch_stock_returns.py
    uv run scripts/fetch_stock_returns.py --universes blf --start 2026-07-01 --end 2026-09-30

Credentials: LSEG_APP_KEY, LSEG_USERNAME, LSEG_PASSWORD from the environment or
--env-file (default: .env).

Output: data/index_return/stocks_<universe>_<start>_<end>.csv with
    sedol, bid, name, ric, country, sector, weight, base_date, end_date, return
"""

import argparse
import os
import time
from datetime import date, timedelta
from pathlib import Path

import lseg.data as ld
import pandas as pd

FIELD = "TR.PriceClose(Curn=USD)"
INFO_FIELDS = {
    "TR.RIC": "ric",
    "TR.CommonName": "company",
    "TR.HeadquartersCountry": "country",  # HQ country (HK-listed Chinese firms = China)
    "TR.GICSSector": "sector",
}
CHUNK = 50
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


def _retry(fn, retries: int = 3):
    for attempt in range(retries):
        try:
            return fn()
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2**attempt)


def fetch_info(sedols: list[str]) -> pd.DataFrame:
    """sedol, ric, company, country, sector."""
    frames = []
    for i in range(0, len(sedols), CHUNK):
        universe = [f"{s}@SEDOL" for s in sedols[i : i + CHUNK]]
        frames.append(
            _retry(lambda u=universe: ld.get_data(universe=u, fields=list(INFO_FIELDS)))
        )
    df = pd.concat(frames, ignore_index=True)
    df.columns = ["sedol", *INFO_FIELDS.values()]
    df["sedol"] = df["sedol"].str.replace("@SEDOL", "", regex=False)
    return df.drop_duplicates("sedol")


def fetch_prices(rics: list[str], start: str, end: str) -> pd.DataFrame:
    """Daily USD closes, columns = RIC."""
    frames = []
    for i in range(0, len(rics), CHUNK):
        chunk = rics[i : i + CHUNK]
        df = _retry(
            lambda c=chunk: ld.get_history(
                universe=c, fields=[FIELD], start=start, end=end
            )
        )
        if len(chunk) == 1:
            df.columns = chunk
        frames.append(df)
    out = pd.concat(frames, axis=1)
    out.index = pd.to_datetime(out.index)
    out.columns.name = None
    out = out.loc[:, ~out.columns.duplicated()]
    return out.sort_index().apply(pd.to_numeric, errors="coerce")


def period_returns(prices: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    """Return from the last close before start to the last close on/before end."""
    filled = prices.ffill()
    before = filled[filled.index < pd.Timestamp(start)]
    upto = filled[filled.index <= pd.Timestamp(end)]
    return pd.DataFrame(
        {
            "base_date": before.apply(lambda s: s.last_valid_index()),
            "end_date": upto.apply(lambda s: s.last_valid_index()),
            "return": upto.iloc[-1] / before.iloc[-1] - 1,
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--universes", nargs="+", default=["gemq", "blf"])
    parser.add_argument(
        "--weight-ym", default="202609", help="universe file for weights"
    )
    parser.add_argument("--start", default="2026-07-01", help="first day of the period")
    parser.add_argument("--end", default="2026-09-30", help="last day of the period")
    parser.add_argument("--out-dir", type=Path, default=Path("data/index_return"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args()

    universes = {}
    for u in args.universes:
        df = pd.read_csv(
            Path("data") / u / "universe" / f"{args.weight_ym}.csv",
            encoding="utf-8-sig",
            dtype={"sedol": str, "bid": str},
        )
        universes[u] = df.drop_duplicates("sedol")[["sedol", "bid", "weight"]]
    sedols = sorted(set().union(*(set(d.sedol) for d in universes.values())))

    load_env_file(args.env_file)
    session = open_session()
    try:
        print(f"info for {len(sedols)} SEDOLs")
        info = fetch_info(sedols)
        rics = info["ric"].dropna().unique().tolist()
        print(f"prices for {len(rics)} RICs")
        first = date.fromisoformat(args.start) - timedelta(
            days=14
        )  # catch the base close
        prices = fetch_prices(rics, first.isoformat(), args.end)
    finally:
        session.close()

    rets = period_returns(prices, args.start, args.end)
    info = info.join(rets, on="ric")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    period = f"{args.start.replace('-', '')}_{args.end.replace('-', '')}"
    for u, w in universes.items():
        df = w.merge(info, on="sedol", how="left").rename(columns={"company": "name"})
        df = df[
            [
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
        ].sort_values("weight", ascending=False)
        path = args.out_dir / f"stocks_{u}_{period}.csv"
        df.to_csv(path, index=False)
        ok = df["return"].notna()
        print(
            f"Saved: {path} ({len(df)} stocks, return for {ok.sum()} = "
            f"{df.loc[ok, 'weight'].sum():.1%} of weight, no RIC: {df.ric.isna().sum()})"
        )


if __name__ == "__main__":
    main()
