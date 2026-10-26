"""Daily common factor returns from core exposures, aggregated by factor type.

Method (follows fret_em_daily / exp_em):
  1. exposures: core factors at the previous month end (exposures/core/{ym}),
     limited to the universe; values <= -100 are missing. Per factor:
     rank -> (rank - 3/8) / (n + 1/4) -> normal quantile, missing -> 0.
  2. each day (rtn/{ym} = daily USD returns of the month after ym): drop
     |ret| >= 100 %, re-rank each factor's score within the day's sample the
     same way, and regress the return on it (one factor at a time, with an
     intercept). The slope is that factor's return for the day.
     With ret_col="sret" the specific return is used instead of the return.
  3. type return = equal-weight mean of its factors' returns (fc_list.csv).

    from p_ken import common_fret
    daily = common_fret.factor_returns("gemq", start="2026-01-01")
    by_type = common_fret.type_returns(daily, "gemq")
    fig = common_fret.plot_cumulative(by_type, start="2026-01-01",
                                      highlight=("2026-07-01", "2026-09-30"))

Returns are in decimals (the source returns are in percent).
"""

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from scipy.stats import norm

from p_ken import io
from p_ken.index_chart import (
    BAND,
    CM,
    GRID,
    INK,
    INK_MUTED,
    MUTED_ALPHA,
    NEGATIVE,
    POSITIVE,
    SLIDE_UPPER_HALF_CM,
    PercentTicks,
)

DATA_ROOT = Path("data")
UNIVERSES = {"gemq": "MSCI EM Universe", "blf": "RGA Universe"}
MISSING_BELOW = -100  # exposures <= this are missing (sentinel -999999998)
MAX_ABS_RET = 100  # percent; larger daily returns are dropped

# Categorical palette (dataviz reference, validated for adjacent lines);
# types beyond 8 and "Other" use grey.
CATEGORICAL = [
    "#2a78d6",
    "#eb6834",
    "#1baf7a",
    "#eda100",
    "#e87ba4",
    "#008300",
    "#6250d6",
    "#e34948",
]
OTHER_COLOR = "#8a8a8a"


def blom(df: pd.DataFrame) -> pd.DataFrame:
    """Per column: rank -> (rank - 3/8) / (n + 1/4) -> normal quantile (NaN kept)."""
    rk = df.rank(method="average")
    n = df.notna().sum()
    return pd.DataFrame(
        norm.ppf((rk - 3 / 8) / (n + 1 / 4)), index=df.index, columns=df.columns
    )


def factor_list(universe: str = "gemq") -> pd.DataFrame:
    """variable, type (from exposures/fc_list.csv)."""
    return io.load_core_list(DATA_ROOT / universe)


def exposures(universe: str, ym: str, factors: list[str]) -> pd.DataFrame:
    """Normal scores (index = bid, columns = factors) at ym end, missing -> 0."""
    data_dir = DATA_ROOT / universe
    bids = io.load_unv(ym, data_dir).bid
    core = io.load_core(ym, data_dir).set_index("bid")
    core = core.reindex(bids.drop_duplicates())
    cols = [f for f in factors if f in core.columns]
    x = core[cols].astype(float)
    x = x.mask(x <= MISSING_BELOW)
    return blom(x).fillna(0.0)


def _day_slopes(s: pd.DataFrame, y: np.ndarray) -> np.ndarray:
    """Slope of y on each column of s (with intercept)."""
    x = s.to_numpy(float)
    xc = x - x.mean(axis=0)
    yc = y - y.mean()
    sxx = (xc**2).sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(sxx > 0, xc.T @ yc / sxx, np.nan)


def factor_returns(
    universe: str = "gemq",
    start: str = "2026-01-01",
    end: str | None = None,
    factors: list[str] | None = None,
    ret_col: str = "ret",
    verbose: bool = False,
) -> pd.DataFrame:
    """Daily factor returns (index = date, columns = factors), decimals.

    factors: default = every fc_list factor present in the core files.
    ret_col: "ret" (USD return) or "sret" (specific return) as the regressand.
    Months without exposures or returns are skipped.
    """
    data_dir = DATA_ROOT / universe
    factors = factors or factor_list(universe).variable.tolist()
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end) if end else None
    first_ym = io.prev_ym(f"{start_ts:%Y%m}")  # exposures for start's month
    rows = []
    for ym in io.list_yms("rtn", data_dir):
        if ym < first_ym:
            continue
        try:
            exp = exposures(universe, ym, factors)
            rtn = io.load_rtn(ym, data_dir)
        except FileNotFoundError:
            if verbose:
                print(f"skip {ym}: no exposures/returns")
            continue
        rtn = rtn[rtn.bid.isin(exp.index)].dropna(subset=[ret_col])
        rtn = rtn[rtn[ret_col].abs() < MAX_ABS_RET]
        for ymd, day in rtn.groupby("ymd"):
            d = pd.Timestamp(ymd)
            if d < start_ts or (end_ts is not None and d > end_ts):
                continue
            day = day.drop_duplicates("bid")
            s = blom(exp.loc[day.bid])
            slopes = _day_slopes(s, day[ret_col].to_numpy(float) / 100)
            rows.append(pd.Series(slopes, index=s.columns, name=d))
        if verbose:
            print(f"done {ym} (n={len(exp)})")
    if not rows:
        raise ValueError(f"no factor returns for {universe} from {start}")
    return pd.DataFrame(rows).sort_index()


def type_returns(daily: pd.DataFrame, universe: str = "gemq") -> pd.DataFrame:
    """Equal-weight mean of factor returns per type (columns in fc_list order)."""
    fl = factor_list(universe)
    fl = fl[fl.variable.isin(daily.columns)]
    order = list(dict.fromkeys(fl.type))
    out = {t: daily[fl.loc[fl.type == t, "variable"]].mean(axis=1) for t in order}
    return pd.DataFrame(out)


def type_colors(types: list[str]) -> dict[str, str]:
    """Fixed categorical colour per type in the given order; 'Other' grey."""
    colors, i = {}, 0
    for t in types:
        if t == "Other" or i >= len(CATEGORICAL):
            colors[t] = OTHER_COLOR
        else:
            colors[t] = CATEGORICAL[i]
            i += 1
    return colors


def _pct(x: float) -> str:
    return f"{x:+.1%}".replace("-", "−")


def _spread(ys: list[float], min_gap: float) -> list[float]:
    """Spread label positions at least min_gap apart, centred on the originals."""
    order = np.argsort(ys)
    pos = np.array(ys, float)[order]
    for _ in range(200):
        moved = False
        for i in range(1, len(pos)):
            gap = pos[i] - pos[i - 1]
            if gap < min_gap:
                push = (min_gap - gap) / 2
                pos[i - 1] -= push
                pos[i] += push
                moved = True
        if not moved:
            break
    out = np.empty_like(pos)
    out[order] = pos
    return out.tolist()


def plot_cumulative(
    returns: pd.DataFrame,
    start: str = "2026-01-01",
    highlight: tuple[str, str] | None = ("2026-07-01", "2026-09-30"),
    title: str | None = None,
    colors: dict[str, str] | None = None,
    size_cm: tuple[float, float] = SLIDE_UPPER_HALF_CM,
    fontsize: float = 8,
    dpi: int = 300,
    ylabel: str = "Factor Return (cumulative sum)",
) -> plt.Figure:
    """Cumulative sum of daily returns from 0, highlight period in full colour.

    Each line is labelled on the right with its sum over the highlight period
    (plus blue / minus red), or its total when there is no highlight.
    """
    colors = colors or type_colors(list(returns.columns))
    base = pd.Timestamp(start) - pd.Timedelta(days=1)
    cum = returns.cumsum()
    cum = pd.concat([pd.DataFrame(0.0, index=[base], columns=cum.columns), cum])
    hs, he = (pd.Timestamp(d) for d in highlight) if highlight else (None, None)

    w_in, h_in = size_cm[0] * CM, size_cm[1] * CM
    fig, ax = plt.subplots(figsize=(w_in, h_in), dpi=dpi, layout="constrained")
    fig.patch.set_facecolor("white")
    fig.get_layout_engine().set(w_pad=0.04, h_pad=0.04)
    if highlight:
        ax.axvspan(hs, min(he, cum.index.max()), color=BAND, zorder=0, lw=0)
    ax.axhline(0, color=INK_MUTED, lw=0.6, zorder=1)

    ends = []
    for col in cum.columns:
        s, color = cum[col].dropna(), colors[col]
        if highlight:
            prior = s[s.index < hs]
            anchor = prior.index[-1] if len(prior) else hs
            inside = s[(s.index >= anchor) & (s.index <= he)]
            for part in (s[s.index <= anchor], s[s.index >= inside.index[-1]]):
                if len(part) > 1:
                    ax.plot(
                        part.index,
                        part,
                        color=color,
                        lw=0.9,
                        alpha=MUTED_ALPHA,
                        zorder=2,
                    )
            ax.plot(inside.index, inside, color=color, lw=1.6, zorder=3, label=col)
            value = returns.loc[
                (returns.index >= hs) & (returns.index <= he), col
            ].sum()
        else:
            ax.plot(s.index, s, color=color, lw=1.4, zorder=3, label=col)
            value = returns[col].sum()
        ends.append((s.index[-1], s.iloc[-1], col, value, color))

    x_first, x_end = cum.index.min(), cum.index.max()
    ax.set_xlim(x_first, x_end)
    months = pd.date_range(
        f"{x_first + pd.Timedelta(days=1):%Y-%m}-01", x_end, freq="MS"
    )
    ax.xaxis.set_major_locator(mticker.FixedLocator(mdates.date2num(months)))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y/%m"))
    ax.yaxis.set_major_formatter(PercentTicks())
    ax.grid(axis="y", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    small = fontsize - 1
    ax.tick_params(colors=INK_MUTED, labelsize=small, length=2, pad=2)
    ax.set_ylabel(ylabel, color=INK_MUTED, fontsize=small)
    if title:
        ax.set_title(title, loc="left", fontsize=fontsize, color=INK, pad=4)

    # right-hand labels: type name + period value, spread to avoid overlap
    y0, y1 = ax.get_ylim()
    min_gap = (y1 - y0) * (fontsize * 1.3 / 72) / (h_in * 0.78)
    ys = _spread([e[1] for e in ends], min_gap)
    for (x, y, name, value, color), y_lab in zip(ends, ys, strict=False):
        ax.scatter([x], [y], s=8, color=color, zorder=4, clip_on=False, linewidths=0)
        label_xy = {"xytext": (1.012, y_lab), "textcoords": ("axes fraction", "data")}
        ax.annotate(  # leader from the line end to the label
            "",
            xy=(x, y),
            **label_xy,
            annotation_clip=False,
            arrowprops={
                "arrowstyle": "-",
                "color": color,
                "lw": 0.5,
                "shrinkA": 0,
                "shrinkB": 0,
            },
        )
        name_t = ax.annotate(
            name,
            xy=(x, y),
            **label_xy,
            va="center",
            fontsize=fontsize,
            color=INK,
            annotation_clip=False,
        )
        ax.annotate(
            _pct(value),
            xy=(1, 0.5),
            xycoords=name_t,
            xytext=(3, 0),
            textcoords="offset points",
            va="center",
            fontsize=fontsize,
            fontweight="bold",
            color=POSITIVE if value >= 0 else NEGATIVE,
        )
    return fig
