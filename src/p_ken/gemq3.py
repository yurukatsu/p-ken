"""GEMQ3 score, ported from get_gemq3() in archive/msci_lib.R.r.

Steps for month ym:
  1. airev = blom((ai + rev) / 2)            over all bids with ai or rev
  2. msd   = mean(airev) over China QIP bids
  3. qip   = rescale_mean(invention_count_12m, msd)   (China only)
  4. Gousei_3Factor = blom( (ai + rev + qip) / 2 )  for China QIP bids
                      blom( (ai + rev) / 2 )        otherwise
     (missing ai / rev / qip are treated as 0)
  5. join to the universe; missing scores become 0
"""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from p_ken import io


def calc_blom_score(x: pd.Series, alpha: float = 0.375) -> pd.Series:
    """Same as calc_blom_score() in msci_lib.R.r (NaN kept as NaN)."""
    rk = x.rank(method="average")
    rk_normed = (rk - alpha) / (rk.max() - 2 * alpha + 1)
    return pd.Series(norm.ppf(rk_normed), index=x.index)


def rescale_mean(x: pd.Series, mu: float, na_rm: bool = True) -> pd.Series:
    """Port of rescale_mean() (R): blom score shifted so its mean equals mu.

    R uses mean(x_scaled) without na.rm, so one missing value makes every
    result NA (QIP then becomes 0 for all stocks). na_rm=True (default)
    ignores missing values instead; na_rm=False reproduces the R behavior.
    """
    x_scaled = calc_blom_score(x)
    if not na_rm and x_scaled.isna().any():
        return pd.Series(np.nan, index=x.index)
    return x_scaled + (mu - x_scaled.mean())


def build_gemq3(
    ym: str,
    qip_na_rm: bool = True,
    data_dir: Path = io.DATA_DIR,
) -> pd.DataFrame:
    """Return the universe with ai, airev and Gousei_3Factor columns."""
    unv = io.load_unv(ym, data_dir)
    ai = io.load_ai(ym, data_dir).drop_duplicates("bid").set_index("bid")["ai"]
    rev = io.load_revision(ym, data_dir)
    rev = rev[rev.bid.isin(unv.bid)].drop_duplicates("bid").set_index("bid")["rev"]

    qip_raw = io.load_qip(ym, data_dir)
    qip_raw = qip_raw[qip_raw.ctry == "CN"].set_index("bid")["invention_count_12m"]
    chai_bid = qip_raw.index

    # 2-factor (AI + Revision)
    airev = pd.concat([ai, rev], axis=1).fillna(0.0)
    airev["airev"] = calc_blom_score((airev.ai + airev.rev) / 2)
    msd = airev.loc[airev.index.isin(chai_bid), "airev"].mean()

    # QIP adjustment
    qip = rescale_mean(qip_raw, msd, qip_na_rm).rename("qip")

    # 3-factor
    s = pd.concat([ai, qip, rev], axis=1).fillna(0.0)
    is_cn = s.index.isin(chai_bid)
    raw = np.where(is_cn, (s.ai + s.rev + s.qip) / 3 * (3 / 2), (s.ai + s.rev) / 2)
    s["Gousei_3Factor"] = calc_blom_score(pd.Series(raw, index=s.index))

    gem = (
        unv.join(ai, on="bid")
        .join(airev["airev"], on="bid")
        .join(s["Gousei_3Factor"], on="bid")
    )
    num = gem.select_dtypes("number").columns
    gem[num] = gem[num].fillna(0.0)
    return gem


def build_all(
    qip_na_rm: bool = True,
    data_dir: Path = io.DATA_DIR,
    out_dir: Path | None = None,
) -> list[str]:
    """Build GEMQ3 for every month that has universe, AI, revision and QIP data."""
    out_dir = out_dir or data_dir / "exposures" / "nam" / "gemq3"
    out_dir.mkdir(parents=True, exist_ok=True)
    have = (
        set(io.list_yms("exposures/nam/ai", data_dir))
        & set(io.list_yms("exposures/nam/revision", data_dir))
        & set(io.list_yms("exposures/nam/qip", data_dir))
    )
    done = []
    for ym in io.list_yms("universe", data_dir):
        if ym not in have or io.load_unv(ym, data_dir).empty:
            continue
        build_gemq3(ym, qip_na_rm, data_dir).to_csv(out_dir / f"{ym}.csv", index=False)
        done.append(ym)
    return done
