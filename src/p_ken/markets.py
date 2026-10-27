"""Market data for the charts: indices, country / sector indices and stocks (USD).

All files come from scripts/fetch_lseg.py (data/index_return) except rga.csv.
"""

import re
from dataclasses import dataclass

import pandas as pd

from p_ken import io
from p_ken.stats import rebase


@dataclass(frozen=True)
class IndexSeries:
    file: str  # data/index_return/<file>.csv
    label: str  # legend
    short: str  # end-of-line label
    column: str | None = None  # None = MSCI variant column (close / net / gross)


INDEX_SERIES = {
    "world": IndexSeries("msci_world", "MSCI World Index", "MSCIWO"),
    "em": IndexSeries("msci_em", "MSCI Emerging Markets Index", "MSCIEM"),
    "acwi": IndexSeries("msci_acwi", "MSCI ACWI Index", "MSCIACWI"),
    "rga": IndexSeries("rga", "RGA Index", "RGA", column="close"),  # total return level
}
# MSCI variant -> y-axis title
VARIANT_LABEL = {"close": "Price Return", "net": "Net Return", "gross": "Gross Return"}


def load_index(key: str, variant: str = "close") -> pd.Series:
    """Index level (USD) named by its label. variant: close (price) / net / gross."""
    spec = INDEX_SERIES[key]
    return io.load_index_file(spec.file)[spec.column or variant].dropna().rename(spec.label)


def rebased_indices(
    keys: list[str], base: str, end: str | None = None, variant: str = "close"
) -> pd.DataFrame:
    """Index levels rebased to 100 at `base`, one column per label, up to `end`."""
    df = pd.concat([rebase(load_index(k, variant), base) for k in keys], axis=1).sort_index()
    return df if end is None else df[df.index <= pd.Timestamp(end)]


# --- country / MSCI EM sector indices -------------------------------------------------

MARKET_GROUPS = {"country": "country_close_usd", "em_sector": "em_sector_close_usd"}
BENCHMARK = "MSCI EM"


def load_market_closes(group: str, benchmark: bool = True) -> pd.DataFrame:
    """USD closes (date x market). Adds the MSCI EM price index to countries if asked."""
    df = io.load_index_file(MARKET_GROUPS[group])
    if benchmark and BENCHMARK not in df.columns:
        em = load_index("em", "close")
        df[BENCHMARK] = em.reindex(df.index.union(em.index))
    if not benchmark and BENCHMARK in df.columns:
        df = df.drop(columns=BENCHMARK)
    return df.sort_index()


def month_ends(start: str, end: str) -> list[pd.Timestamp]:
    """Calendar month ends from start's month through end (end itself last)."""
    ends = list(pd.date_range(start, end, freq="ME"))
    if not ends or ends[-1] != pd.Timestamp(end):
        ends.append(pd.Timestamp(end))
    return ends


def checkpoint_returns(close: pd.DataFrame, start: str, checkpoints: list) -> pd.DataFrame:
    """Rows = markets, columns = checkpoints: return from the last close before start."""
    filled = close.ffill()
    before = filled[filled.index < pd.Timestamp(start)]
    if before.empty:
        raise ValueError(f"no data before {start}")
    base = before.iloc[-1]
    return pd.DataFrame(
        {
            pd.Timestamp(cp): filled[filled.index <= pd.Timestamp(cp)].iloc[-1] / base - 1
            for cp in checkpoints
        }
    )


def base_date(close: pd.DataFrame, start: str) -> pd.Timestamp:
    """Last date with data before start (the base of period returns)."""
    return close.index[close.index < pd.Timestamp(start)].max()


# --- stocks -------------------------------------------------------------------------------

COUNTRY_SHORT = {
    "Korea; Republic (S. Korea)": "Korea",
    "United Arab Emirates": "UAE",
    "United States of America": "USA",
    "United Kingdom": "UK",
    "Czech Republic": "Czechia",
}
_NAME_SUFFIXES = re.compile(
    r"[,.]?\s+(Co\.?,?\s*Ltd\.?|Ltd\.?|Limited|Inc\.?|Corp\.?|Corporation|PLC|PJSC|SAB de CV|"
    r"S\.?A\.?B?\.?|SA|AG|NV|Tbk PT|PT|Bhd|Berhad|PCL|Public Co|Holdings?|Group|Co)$",
    re.IGNORECASE,
)


def short_name(name: str) -> str:
    """Drop trailing company suffixes (Ltd, Corp, SA, ...) for cell labels."""
    if not isinstance(name, str):
        return ""
    prev = None
    while prev != name:
        prev, name = name, _NAME_SUFFIXES.sub("", name).strip()
    return name


def load_stocks(universe: str, tag: str) -> pd.DataFrame:
    """Stock weights and period returns with tidy country names and cell labels.

    tag: "<start>_<end>" as in Period.tag. Country = LSEG headquarters country.
    """
    df = io.load_stock_returns(universe, tag)
    df["country"] = df["country"].fillna("Other").replace(COUNTRY_SHORT)
    df["sector"] = df["sector"].fillna("Other")
    df["label"] = df["name"].map(short_name).where(df["name"].notna(), df["bid"])
    return df
