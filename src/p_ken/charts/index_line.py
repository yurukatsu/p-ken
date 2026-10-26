"""Indices rebased to 100, highlighted period in full colour, period returns at the line ends."""

import matplotlib.dates as mdates
import pandas as pd

from p_ken.charts.labels import in_plot_labels
from p_ken.charts.style import (
    BAND,
    INK,
    INK_MUTED,
    REDS,
    SLIDE_HALF_CM,
    fmt_pct,
    new_figure,
    plot_highlighted,
    signed_color,
    style_time_axes,
)
from p_ken.stats import period_return


def plot_rebased(
    levels: pd.DataFrame,
    short_names: dict[str, str],
    highlight: tuple[str, str] | None,
    ylabel: str,
    colors: list[str] | None = None,
    title: str | None = None,
    size_cm: tuple[float, float] = SLIDE_HALF_CM,
    fontsize: float = 9,
    dpi: int = 300,
):
    """levels: rebased index levels (columns = legend labels), e.g. markets.rebased_indices.

    Lines are drawn in colors[i] (default REDS, dark -> light); inside the
    highlight period they are full colour, faint elsewhere. Each line end is
    labelled with short_names[label] and its return over the highlight period
    (last value before start -> last value on or before end), placed above or
    below the end point inside the plot.
    """
    colors = list(colors or REDS)
    if len(colors) < levels.shape[1]:
        raise ValueError(f"{levels.shape[1]} series but only {len(colors)} colors")
    fig, ax = new_figure(size_cm, dpi)
    if highlight:
        ax.axvspan(*(pd.Timestamp(d) for d in highlight), color=BAND, zorder=0, lw=0)
    ax.axhline(100, color=INK_MUTED, lw=0.6, ls="--", zorder=1)

    ends, lines = [], []
    for col, color in zip(levels.columns, colors, strict=False):
        s = levels[col].dropna()
        plot_highlighted(ax, s, highlight, color, lw=1.8, lw_muted=1.0, label=col)
        lines.append((mdates.date2num(s.index), s.to_numpy()))
        if highlight:
            r = period_return(s, *highlight)
            value, vcolor = fmt_pct(r), signed_color(r)
        else:
            value, vcolor = f"{s.iloc[-1]:.1f}", INK
        ax.scatter(
            [s.index[-1]],
            [s.iloc[-1]],
            s=12,
            color=color,
            zorder=4,
            edgecolors="white",
            linewidths=0.6,
            clip_on=False,
        )
        ends.append((s.index[-1], s.iloc[-1], short_names.get(col, col), value, vcolor))

    style_time_axes(ax, fontsize, levels.index.min(), levels.index.max())
    in_plot_labels(fig, ax, ends, lines, fontsize, halo=BAND if highlight else "white")
    ax.set_ylabel(ylabel, color=INK_MUTED, fontsize=fontsize - 1)
    ax.legend(  # one row above the plot, never over the lines
        loc="lower left",
        bbox_to_anchor=(0, 1.0),
        ncol=levels.shape[1],
        frameon=False,
        fontsize=fontsize,
        labelcolor=INK,
        handlelength=1.6,
        borderaxespad=0.2,
        columnspacing=1.6,
    )
    if title:
        fig.suptitle(title, x=0.01, ha="left", fontsize=fontsize + 3, color=INK)
    return fig
