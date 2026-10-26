"""Horizontal bar chart of period returns with intermediate checkpoints.

    from p_ken import return_bars
    fig, table = return_bars.plot_period_bars("country", "2026-07-01", "2026-09-30")

Bar = cumulative return from the last close before `start` to `end`.
Markers = cumulative returns (same base) at the checkpoints in between
(default: month ends), e.g. 7/31 and 8/31 for a Jul-Sep period.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.legend_handler import HandlerTuple
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter

from p_ken import index_chart
from p_ken.index_chart import CM, GRID, INK, INK_MUTED, NEGATIVE, POSITIVE

INDEX_DIR = Path("data/index_return")
GROUP_FILES = {
    "country": "country_close_usd.csv",
    "em_sector": "em_sector_close_usd.csv",
}
BENCHMARK = "MSCI EM"

# Quarter of a 4:3 template slide: half the 24.8 cm content width (minus a gap)
# by the 7.4 cm upper half (see index_chart.SLIDE_UPPER_HALF_CM).
SLIDE_QUARTER_CM = (12.2, 7.4)

BAR_POS = "#a9c4ea"  # light tint of POSITIVE
BAR_NEG = "#f1aaa6"  # light tint of NEGATIVE
BAR_BENCH = "#c4c4c4"
MARKERS = [  # one per intermediate checkpoint
    {"marker": "o", "markerfacecolor": "white", "markeredgecolor": INK},
    {"marker": "D", "markerfacecolor": INK, "markeredgecolor": INK},
    {"marker": "s", "markerfacecolor": "white", "markeredgecolor": INK},
    {"marker": "^", "markerfacecolor": INK, "markeredgecolor": INK},
]


def load_closes(group: str, index_dir: Path = INDEX_DIR, benchmark: bool = True):
    """USD closes (DatetimeIndex x markets). Adds MSCI EM to countries if asked."""
    df = pd.read_csv(index_dir / GROUP_FILES[group], dtype={"dateymd": str})
    df = df.set_index(pd.to_datetime(df.pop("dateymd"), format="%Y%m%d"))
    if benchmark and BENCHMARK not in df.columns:
        em = index_chart.load_series("em", variant="close", index_dir=index_dir)
        df[BENCHMARK] = em.reindex(df.index.union(em.index))
    if not benchmark and BENCHMARK in df.columns:
        df = df.drop(columns=BENCHMARK)
    return df.sort_index()


def month_ends(start: str, end: str) -> list[pd.Timestamp]:
    """Calendar month ends from start's month through end (end itself last)."""
    ends = list(pd.date_range(start, end, freq="ME"))
    e = pd.Timestamp(end)
    if not ends or ends[-1] != e:
        ends.append(e)
    return ends


def cumulative_returns(
    close: pd.DataFrame, start: str, checkpoints: list[pd.Timestamp]
) -> pd.DataFrame:
    """Rows = markets, columns = checkpoints; return vs the last close before start."""
    filled = close.ffill()
    before = filled[filled.index < pd.Timestamp(start)]
    if before.empty:
        raise ValueError(f"no data before {start}")
    base = before.iloc[-1]
    cols = {}
    for cp in checkpoints:
        upto = filled[filled.index <= cp]
        cols[cp] = upto.iloc[-1] / base - 1
    return pd.DataFrame(cols)


def _pct(x: float) -> str:
    return f"{x:+.1%}".replace("-", "−")


def plot_period_bars(
    group: str = "country",
    start: str = "2026-07-01",
    end: str = "2026-09-30",
    checkpoints: list[str] | None = None,
    benchmark: bool = True,
    index_dir: Path = INDEX_DIR,
    size_cm: tuple[float, float] = SLIDE_QUARTER_CM,
    fontsize: float = 7,
    dpi: int = 300,
) -> tuple[plt.Figure, pd.DataFrame]:
    """Bars = return start -> end; markers = returns at the checkpoints in between.

    group:       "country" or "em_sector" (data/index_return/<group>_close_usd.csv).
    checkpoints: dates for the markers (default: month ends before `end`).
    benchmark:   include MSCI EM (grey bar) for reference.
    size_cm:     size as placed on the slide; `fontsize` is pt on the slide.
    Returns the figure and the table of cumulative returns (rows sorted).
    """
    close = load_closes(group, index_dir, benchmark)
    cps = (
        [pd.Timestamp(c) for c in checkpoints] + [pd.Timestamp(end)]
        if checkpoints
        else month_ends(start, end)
    )
    table = cumulative_returns(close, start, cps)
    final = cps[-1]
    table = table.dropna(subset=[final]).sort_values(final)  # bottom -> top
    n = len(table)

    fig, ax = plt.subplots(
        figsize=(size_cm[0] * CM, size_cm[1] * CM), dpi=dpi, layout="constrained"
    )
    fig.patch.set_facecolor("white")
    fig.get_layout_engine().set(w_pad=0.03, h_pad=0.03)

    y = range(n)
    vals = table[final]
    colors = [
        BAR_BENCH if name == BENCHMARK else (BAR_POS if v >= 0 else BAR_NEG)
        for name, v in vals.items()
    ]
    ax.barh(y, vals, height=0.62, color=colors, zorder=2)
    ax.axvline(0, color=INK_MUTED, lw=0.6, zorder=3)

    mid = cps[:-1]
    for cp, style in zip(mid, MARKERS, strict=False):
        ax.plot(
            table[cp],
            y,
            ls="none",
            markersize=fontsize * 0.55,
            markeredgewidth=0.6,
            zorder=4,
            **style,
        )

    # market names (benchmark bold) and the period return as a right-hand column
    ax.set_yticks(list(y), table.index)
    for lab in ax.get_yticklabels():
        if lab.get_text() == BENCHMARK:
            lab.set_fontweight("bold")
    for i, v in enumerate(vals):
        ax.annotate(
            _pct(v),
            xy=(1, i),
            xycoords=("axes fraction", "data"),
            xytext=(4, 0),
            textcoords="offset points",
            ha="left",
            va="center",
            fontsize=fontsize,
            fontweight="bold",
            color=POSITIVE if v >= 0 else NEGATIVE,
        )

    lo = min(0, table.min().min())
    hi = max(0, table.max().max())
    pad = (hi - lo) * 0.05
    ax.set_xlim(lo - pad, hi + pad)
    ax.set_ylim(-0.6, n - 0.4)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.0%}"))
    ax.xaxis.tick_top()
    ax.grid(axis="x", color=GRID, lw=0.5, zorder=0)
    for side in ("right", "bottom", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["top"].set_color(GRID)
    ax.tick_params(axis="x", colors=INK_MUTED, labelsize=fontsize - 1, length=0, pad=1)
    ax.tick_params(axis="y", colors=INK, labelsize=fontsize, length=0, pad=2)

    base_label = f"{pd.Timestamp(start) - pd.Timedelta(days=1):%-m/%-d}"
    handles = [
        Line2D(
            [], [], ls="none", markersize=fontsize * 0.55, markeredgewidth=0.6, **style
        )
        for style in MARKERS[: len(mid)]
    ] + [
        (
            Patch(facecolor=BAR_POS, edgecolor="none"),
            Patch(facecolor=BAR_NEG, edgecolor="none"),
        )
    ]
    labels = [f"{cp:%-m/%-d}" for cp in mid] + [f"{final:%-m/%-d}"]
    ax.legend(
        handles,
        labels,
        title=f"USD, vs {base_label}",
        title_fontproperties={"size": fontsize - 1},
        loc="lower right",
        bbox_to_anchor=(1.0, 1.04),
        ncol=len(labels) + 1,
        frameon=False,
        fontsize=fontsize - 1,
        labelcolor=INK_MUTED,
        handlelength=1.0,
        handletextpad=0.4,
        columnspacing=1.0,
        borderaxespad=0,
        handler_map={tuple: HandlerTuple(ndivide=None, pad=0)},
    )
    ax.get_legend().get_title().set_color(INK_MUTED)
    ax.get_legend()._legend_box.align = "left"

    out = table.iloc[::-1].copy()  # top -> bottom as drawn
    out.columns = [f"{c:%Y-%m-%d}" for c in out.columns]
    return fig, out
