"""Paths, universes and the report period.

All paths are relative to the repository root, so scripts and notebooks work
from any working directory. The report period is read from config/report.toml.
"""

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

ROOT = Path(os.environ.get("P_KEN_ROOT", Path(__file__).resolve().parents[2]))
DATA_ROOT = ROOT / "data"
INDEX_DIR = DATA_ROOT / "index_return"
CONFIG_FILE = ROOT / "config" / "report.toml"

# universe key -> display name. The key is also the folder under data/.
UNIVERSES = {"gemq": "MSCI EM Universe", "blf": "RGA Universe"}


def universe_dir(universe: str) -> Path:
    if universe not in UNIVERSES:
        raise ValueError(f"unknown universe {universe!r}: {list(UNIVERSES)}")
    return DATA_ROOT / universe


@dataclass(frozen=True)
class Period:
    """Dates of one report (YYYY-MM-DD strings)."""

    ytd_start: str  # year-to-date charts start here (index = 100, cumulative sum = 0)
    start: str  # first day of the highlighted period
    end: str  # last day of the highlighted period (report date)

    @property
    def highlight(self) -> tuple[str, str]:
        return (self.start, self.end)

    @property
    def end_ym(self) -> str:
        """YYYYMM of the report date (month-end weights / universe)."""
        return f"{pd.Timestamp(self.end):%Y%m}"

    @property
    def tag(self) -> str:
        """'20260701_20260930' - used in output file names."""
        return f"{self.start.replace('-', '')}_{self.end.replace('-', '')}"


def load_config(path: Path = CONFIG_FILE) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def load_period(path: Path = CONFIG_FILE) -> Period:
    p = load_config(path)["period"]
    return Period(ytd_start=p["ytd_start"], start=p["start"], end=p["end"])


def figures_dir(path: Path = CONFIG_FILE) -> Path:
    return ROOT / load_config(path).get("output", {}).get("figures", "output/figures")
