"""Loaders for the files under data/GEMQ."""

from pathlib import Path

import pandas as pd

DATA_DIR = Path("data/GEMQ")


def prev_ym(ym: str, months: int = 1) -> str:
    """Return the month `months` before `ym` (YYYYMM)."""
    y, m = int(ym[:4]), int(ym[4:])
    idx = y * 12 + (m - 1) - months
    return f"{idx // 12:04d}{idx % 12 + 1:02d}"


def list_yms(sub: str, data_dir: Path = DATA_DIR) -> list[str]:
    """Months available in a sub directory (e.g. "unv", "rtn")."""
    return sorted(p.stem[-6:] for p in (data_dir / sub).iterdir() if p.is_file())


def load_unv(ym: str, data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Universe constituents: date, sedol, bid, weight (sorted by weight desc)."""
    df = pd.read_csv(
        data_dir / "unv" / f"{ym}.csv",
        encoding="utf-8-sig",
        dtype={"sedol": str, "bid": str},
    )
    return df.drop_duplicates("sedol").reset_index(drop=True)


def load_ai(ym: str, data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """AI blom score: bid, ai."""
    df = pd.read_csv(data_dir / "scores" / "ai" / f"{ym}.csv", encoding="utf-8-sig")
    df.columns = ["bid", "ai"]
    return df


def load_revision(ym: str, data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Revision NTM (adjusted): bid, rev."""
    df = pd.read_csv(
        data_dir / "scores" / "revision" / f"{ym}.csv", encoding="utf-8-sig"
    )
    return df[["bid", "Revision_NTM_Adj"]].rename(columns={"Revision_NTM_Adj": "rev"})


def load_qip(ym: str, data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """QIP file (all columns)."""
    df = pd.read_csv(
        data_dir / "scores" / "qip" / f"msci_em_{ym}.dat",
        sep="\t",
        encoding="utf-8-sig",
        dtype={"bid": str, "ctry": str},
    )
    return df.drop_duplicates("bid").reset_index(drop=True)


def load_rtn(ym: str, data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Daily returns in percent for month `ym`: ymd, bid, ret."""
    df = pd.read_csv(
        data_dir / "rtn" / f"{ym}.csv",
        encoding="utf-8-sig",
        dtype={"dateym": str, "bid": str},
    )
    return df.rename(columns={"dateym": "ymd"})


def load_gemq3(ym: str, data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """GEMQ3 scores written by `p_ken.gemq3`."""
    return pd.read_csv(
        data_dir / "scores" / "gemq3" / f"{ym}.csv", dtype={"sedol": str, "bid": str}
    )
