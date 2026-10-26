"""Loaders for the files under data/gemq.

Layout (YYYYMM = month end the file refers to):
  universe/{ym}.csv                     MSCI EM constituents at ym end
  exposures/nam/ai/{ym}.csv             AI blom score
  exposures/nam/revision/{ym}.csv       Revision NTM (adj)
  exposures/nam/qip/msci_em_{ym}.dat    QIP patents
  exposures/nam/gemq3/{ym}.csv          GEMQ3 (written by p_ken.gemq3)
  exposures/core/{ym}.csv               core factors (see exposures/fc_list.csv)
  rtn/{ym}.csv                          daily returns in the month AFTER ym
                                        for the stocks in universe/{ym}
"""

from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path("data/gemq")
NA_SENTINEL = -999999998  # core files use values <= this for missing


def prev_ym(ym: str, months: int = 1) -> str:
    """Return the month `months` before `ym` (YYYYMM)."""
    y, m = int(ym[:4]), int(ym[4:])
    idx = y * 12 + (m - 1) - months
    return f"{idx // 12:04d}{idx % 12 + 1:02d}"


def list_yms(sub: str, data_dir: Path = DATA_DIR) -> list[str]:
    """Months available in a sub directory (e.g. "universe", "rtn")."""
    return sorted(
        p.stem[-6:]
        for p in (data_dir / sub).iterdir()
        if p.is_file() and p.stem[-6:].isdigit()
    )


def load_unv(ym: str, data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Universe constituents: date, sedol, bid, weight (sorted by weight desc)."""
    df = pd.read_csv(
        data_dir / "universe" / f"{ym}.csv",
        encoding="utf-8-sig",
        dtype={"sedol": str, "bid": str},
    )
    return df.drop_duplicates("sedol").reset_index(drop=True)


def load_ai(ym: str, data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """AI blom score: bid, ai."""
    df = pd.read_csv(
        data_dir / "exposures" / "nam" / "ai" / f"{ym}.csv", encoding="utf-8-sig"
    )
    df.columns = ["bid", "ai"]
    return df


def load_revision(ym: str, data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Revision NTM (adjusted): bid, rev."""
    df = pd.read_csv(
        data_dir / "exposures" / "nam" / "revision" / f"{ym}.csv",
        encoding="utf-8-sig",
    )
    return df[["bid", "Revision_NTM_Adj"]].rename(columns={"Revision_NTM_Adj": "rev"})


def load_qip(ym: str, data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """QIP file (all columns)."""
    df = pd.read_csv(
        data_dir / "exposures" / "nam" / "qip" / f"msci_em_{ym}.dat",
        sep="\t",
        encoding="utf-8-sig",
        dtype={"bid": str, "ctry": str},
    )
    return df.drop_duplicates("bid").reset_index(drop=True)


def load_core(ym: str, data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Core factor exposures: bid + factor columns (missing sentinel -> NaN)."""
    df = pd.read_csv(
        data_dir / "exposures" / "core" / f"{ym}.csv",
        encoding="utf-8-sig",
        dtype={"BID": str, "GID": str, "SEDOL": str, "CUSIP": str},
    )
    df = df.drop(columns=["DATE", "GID", "SEDOL", "CUSIP"], errors="ignore")
    df = df.rename(columns={"BID": "bid"})
    df["bid"] = df["bid"].str.strip()
    num = df.columns.drop("bid")
    df[num] = df[num].mask(df[num] <= NA_SENTINEL, np.nan)
    return df.drop_duplicates("bid").reset_index(drop=True)


def load_core_list(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Core factor names and categories: variable, type."""
    return pd.read_csv(data_dir / "exposures" / "fc_list.csv", encoding="utf-8-sig")


def load_rtn(ym: str, data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Daily returns (percent) in the month after ym for universe/{ym}.

    Columns: ymd, bid, ret (total), sret (specific).
    """
    df = pd.read_csv(
        data_dir / "rtn" / f"{ym}.csv",
        encoding="utf-8-sig",
        dtype={"dateym": str, "bid": str},
    )
    return df.rename(columns={"dateym": "ymd"})


def load_gemq3(ym: str, data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """GEMQ3 scores written by `p_ken.gemq3`."""
    return pd.read_csv(
        data_dir / "exposures" / "nam" / "gemq3" / f"{ym}.csv",
        dtype={"sedol": str, "bid": str},
    )
