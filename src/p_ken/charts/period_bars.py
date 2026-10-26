"""Horizontal bars of period returns with markers for the returns at earlier checkpoints."""

import pandas as pd
from matplotlib.legend_handler import HandlerTuple
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from p_ken.charts.style import (
    GRID,
    INK,
    INK_MUTED,
    SLIDE_QUARTER_CM,
    PercentTicks,
    fmt_pct,
    new_figure,
    signed_color,
)

BAR_POS = "#a9c4ea"  # light tint of POSITIVE
BAR_NEG = "#f1aaa6"  # light tint of NEGATIVE
BAR_BENCH = "#c4c4c4"
MARKERS = [  # one per intermediate checkpoint
    {"marker": "o", "markerfacecolor": "white", "markeredgecolor": INK},
    {"marker": "D", "markerfacecolor": INK, "markeredgecolor": INK},
    {"marker": "s", "markerfacecolor": "white", "markeredgecolor": INK},
    {"marker": "^", "markerfacecolor": INK, "markeredgecolor": INK},
]


def plot_period_bars(
    table: pd.DataFrame,
    base_date: pd.Timestamp,
    benchmark: str | None = "MSCI EM",
    size_cm: tuple[float, float] = SLIDE_QUARTER_CM,
    fontsize: float = 7,
    dpi: int = 300,
):
    """table: rows = markets, columns = checkpoint dates (last = period end).

    Bar = return to the last checkpoint, markers = returns at the earlier ones
    (all from base_date). Rows are sorted by the bar; the benchmark row is grey
    with a bold name; the period return is shown right of the plot.
    """
    final = table.columns[-1]
    mid = list(table.columns[:-1])
    table = table.dropna(subset=[final]).sort_values(final)  # bottom -> top
    n = len(table)

    fig, ax = new_figure(size_cm, dpi, pad=0.03)
    y = range(n)
    vals = table[final]
    colors = [
        BAR_BENCH if name == benchmark else (BAR_POS if v >= 0 else BAR_NEG)
        for name, v in vals.items()
    ]
    ax.barh(y, vals, height=0.62, color=colors, zorder=2)
    ax.axvline(0, color=INK_MUTED, lw=0.6, zorder=3)
    marker = {"markersize": fontsize * 0.55, "markeredgewidth": 0.6}
    for cp, style in zip(mid, MARKERS, strict=False):
        ax.plot(table[cp], y, ls="none", zorder=4, **marker, **style)

    ax.set_yticks(list(y), table.index)
    for lab in ax.get_yticklabels():
        if lab.get_text() == benchmark:
            lab.set_fontweight("bold")
    for i, v in enumerate(vals):
        ax.annotate(
            fmt_pct(v),
            xy=(1, i),
            xycoords=("axes fraction", "data"),
            xytext=(4, 0),
            textcoords="offset points",
            ha="left",
            va="center",
            fontsize=fontsize,
            fontweight="bold",
            color=signed_color(v),
        )

    lo, hi = min(0, table.min().min()), max(0, table.max().max())
    pad = (hi - lo) * 0.05
    ax.set_xlim(lo - pad, hi + pad)
    ax.set_ylim(-0.6, n - 0.4)
    ax.xaxis.set_major_formatter(PercentTicks())
    ax.grid(axis="x", color=GRID, lw=0.5, zorder=0)
    for side in ("right", "top", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(axis="x", colors=INK_MUTED, labelsize=fontsize - 1, length=0, pad=1)
    ax.tick_params(axis="y", colors=INK, labelsize=fontsize, length=0, pad=2)

    title = ax.set_title(
        f"Cumulative Return from {base_date:%-m/%-d} (USD)",
        loc="left",
        fontsize=fontsize,
        color=INK,
        pad=4,
    )
    handles = [Line2D([], [], ls="none", **marker, **style) for style in MARKERS[: len(mid)]]
    handles.append(
        (Patch(facecolor=BAR_POS, edgecolor="none"), Patch(facecolor=BAR_NEG, edgecolor="none"))
    )
    ax.legend(
        handles,
        [f"{pd.Timestamp(c):%-m/%-d}" for c in [*mid, final]],
        loc="lower right",
        bbox_to_anchor=(1.0, 1.0),
        ncol=len(mid) + 2,
        frameon=False,
        fontsize=fontsize - 1,
        labelcolor=INK_MUTED,
        handlelength=1.0,
        handletextpad=0.4,
        columnspacing=1.0,
        borderaxespad=0,
        handler_map={tuple: HandlerTuple(ndivide=None, pad=0)},
    )
    # start the title at the figure's left edge (above the names) so it clears the legend
    title.set_in_layout(False)
    fig.canvas.draw()
    title.set_x((fig.bbox.x0 + 2 * fig.dpi / 72 - ax.bbox.x0) / ax.bbox.width)
    return fig
