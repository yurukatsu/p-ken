"""Readers for the local data under data/.

Universe folders (data/gemq = MSCI EM, data/blf = RGA). {ym} = YYYYMM month end:
    universe/{ym}.csv                     constituents and weights at ym end
    rtn/{ym}.csv                          daily returns (%) in the month AFTER ym
                                          for the stocks of universe/{ym}:
                                          ret = local-currency total, sret = specific
    exposures/core/{ym}.csv               core factors; exposures/fc_list.csv = types
gemq only:
    exposures/nam/{ai,revision,qip}/      month-end NAM scores
    exposures/nam/gemq3/{ym}.csv          GEMQ3 (written by p_ken.gemq3)
blf only:
    exposures/nam/{ai,bigdata}/{ymd}.csv  daily NAM score files
Market data (from scripts/fetch_lseg.py), data/index_return:
    msci_{em,acwi,world}.csv, rga.csv, {country,em_sector}_{close,return}_usd.csv,
    stocks_<universe>_<start>_<end>.csv
"""

from functools import cache
from pathlib import Path

import numpy as np
import pandas as pd

from p_ken.config import INDEX_DIR, universe_dir

NA_SENTINEL = -999999998  # core files use values <= this for missing


# --- dates ------------------------------------------------------------------


def prev_ym(ym: str, months: int = 1) -> str:
    """The month `months` before `ym` (YYYYMM)."""
    y, m = int(ym[:4]), int(ym[4:])
    idx = y * 12 + (m - 1) - months
    return f"{idx // 12:04d}{idx % 12 + 1:02d}"


def list_yms(universe: str, sub: str) -> list[str]:
    """Months (YYYYMM) with a file in data/<universe>/<sub>, sorted."""
    folder = universe_dir(universe) / sub
    return sorted(p.stem[-6:] for p in folder.iterdir() if p.is_file() and p.stem[-6:].isdigit())


# --- universe and returns ------------------------------------------------------


def load_universe(universe: str, ym: str) -> pd.DataFrame:
    """Constituents at ym end: bid, sedol, weight, ... (file order = weight desc)."""
    df = pd.read_csv(
        universe_dir(universe) / "universe" / f"{ym}.csv",
        encoding="utf-8-sig",
        dtype={"sedol": str, "bid": str},
    )
    return df.drop_duplicates("sedol").reset_index(drop=True)


def load_returns(universe: str, ym: str) -> pd.DataFrame:
    """Daily returns (%) in the month after ym for universe/{ym}: ymd, bid, ret, sret."""
    df = pd.read_csv(
        universe_dir(universe) / "rtn" / f"{ym}.csv",
        encoding="utf-8-sig",
        dtype={"dateym": str, "bid": str},
    )
    return df.rename(columns={"dateym": "ymd"})


# --- exposures -------------------------------------------------------------------


def load_core(universe: str, ym: str) -> pd.DataFrame:
    """Core factor exposures: bid + factor columns (missing sentinel -> NaN)."""
    df = pd.read_csv(
        universe_dir(universe) / "exposures" / "core" / f"{ym}.csv",
        encoding="utf-8-sig",
        dtype={"BID": str, "GID": str, "SEDOL": str, "CUSIP": str},
    )
    df = df.drop(columns=["DATE", "GID", "SEDOL", "CUSIP"], errors="ignore")
    df = df.rename(columns={"BID": "bid"})
    df["bid"] = df["bid"].str.strip()
    num = df.columns.drop("bid")
    df[num] = df[num].mask(df[num] <= NA_SENTINEL, np.nan)
    return df.drop_duplicates("bid").reset_index(drop=True)


def load_core_list(universe: str) -> pd.DataFrame:
    """Core factor names and types: variable, type."""
    return pd.read_csv(universe_dir(universe) / "exposures" / "fc_list.csv", encoding="utf-8-sig")


def _nam(universe: str, name: str) -> Path:
    return universe_dir(universe) / "exposures" / "nam" / name


def load_ai(ym: str, universe: str = "gemq") -> pd.DataFrame:
    """Month-end AI blom score: bid, ai."""
    df = pd.read_csv(_nam(universe, "ai") / f"{ym}.csv", encoding="utf-8-sig")
    df.columns = ["bid", "ai"]
    return df


def load_revision(ym: str, universe: str = "gemq") -> pd.DataFrame:
    """Month-end Revision NTM (adjusted): bid, rev."""
    df = pd.read_csv(_nam(universe, "revision") / f"{ym}.csv", encoding="utf-8-sig")
    return df[["bid", "Revision_NTM_Adj"]].rename(columns={"Revision_NTM_Adj": "rev"})


def load_qip(ym: str, universe: str = "gemq") -> pd.DataFrame:
    """Month-end QIP patent data (all columns)."""
    df = pd.read_csv(
        _nam(universe, "qip") / f"msci_em_{ym}.dat",
        sep="\t",
        encoding="utf-8-sig",
        dtype={"bid": str, "ctry": str},
    )
    return df.drop_duplicates("bid").reset_index(drop=True)


def gemq3_dir(universe: str = "gemq") -> Path:
    return _nam(universe, "gemq3")


def load_gemq3(ym: str, universe: str = "gemq") -> pd.DataFrame:
    """GEMQ3 scores written by p_ken.gemq3 (universe + ai, airev, Gousei_3Factor)."""
    return pd.read_csv(gemq3_dir(universe) / f"{ym}.csv", dtype={"sedol": str, "bid": str})


@cache
def score_dates(kind: str, universe: str = "blf") -> list[str]:
    """Dates (YYYYMMDD) of the daily score files exposures/nam/<kind>/, sorted."""
    return sorted(p.stem for p in _nam(universe, kind).glob("*.csv") if p.stem.isdigit())


@cache
def load_scores(kind: str, ymd: str, universe: str = "blf") -> pd.DataFrame:
    """One daily score file (index = bid). kind: "ai" or "bigdata"."""
    df = pd.read_csv(_nam(universe, kind) / f"{ymd}.csv", encoding="utf-8-sig", dtype={"bid": str})
    return df.dropna(subset=["bid"]).drop_duplicates("bid").set_index("bid")


# --- market data (LSEG) --------------------------------------------------------------


def load_index_file(name: str) -> pd.DataFrame:
    """data/index_return/<name>.csv with a DatetimeIndex (from the dateymd column)."""
    df = pd.read_csv(INDEX_DIR / f"{name}.csv", encoding="utf-8-sig", dtype={"dateymd": str})
    return df.set_index(pd.to_datetime(df.pop("dateymd"), format="%Y%m%d")).sort_index()


def load_stock_returns(universe: str, tag: str) -> pd.DataFrame:
    """Per-stock weights and period returns: stocks_<universe>_<tag>.csv."""
    return pd.read_csv(INDEX_DIR / f"stocks_{universe}_{tag}.csv", dtype={"sedol": str})
