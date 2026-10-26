"""Cumulative sum of daily factor returns from 0, highlighted period in full colour."""

import pandas as pd

from p_ken.charts.labels import right_labels
from p_ken.charts.style import (
    BAND,
    CATEGORICAL,
    CM,
    INK,
    INK_MUTED,
    OTHER,
    SLIDE_HALF_CM,
    PercentTicks,
    new_figure,
    plot_highlighted,
    style_time_axes,
)


def category_colors(names: list[str]) -> dict[str, str]:
    """Fixed categorical colour per name in the given order; 'Other' and beyond 8 grey."""
    colors, i = {}, 0
    for name in names:
        if name == "Other" or i >= len(CATEGORICAL):
            colors[name] = OTHER
        else:
            colors[name] = CATEGORICAL[i]
            i += 1
    return colors


def plot_cumulative(
    daily: pd.DataFrame,
    start: str,
    highlight: tuple[str, str] | None,
    title: str | None = None,
    colors: dict[str, str] | None = None,
    ylabel: str = "Factor Return (cumulative sum)",
    size_cm: tuple[float, float] = SLIDE_HALF_CM,
    fontsize: float = 8,
    dpi: int = 300,
):
    """daily: daily returns (index = date, columns = factors), decimals.

    The cumulative sum starts at 0 on the day before `start`. Lines are labelled
    on the right with their sum over the highlight period (plus blue / minus
    red), or their total without a highlight.
    """
    colors = colors or category_colors(list(daily.columns))
    zero = pd.DataFrame(
        0.0, index=[pd.Timestamp(start) - pd.Timedelta(days=1)], columns=daily.columns
    )
    cum = pd.concat([zero, daily.cumsum()])

    fig, ax = new_figure(size_cm, dpi)
    if highlight:
        hs, he = (pd.Timestamp(d) for d in highlight)
        ax.axvspan(hs, min(he, cum.index.max()), color=BAND, zorder=0, lw=0)
    ax.axhline(0, color=INK_MUTED, lw=0.6, zorder=1)

    ends = []
    for col in cum.columns:
        s = cum[col].dropna()
        plot_highlighted(ax, s, highlight, colors[col], lw=1.6, lw_muted=0.9, label=col)
        if highlight:
            value = daily.loc[(daily.index >= hs) & (daily.index <= he), col].sum()
        else:
            value = daily[col].sum()
        ends.append((s.index[-1], s.iloc[-1], col, value, colors[col]))

    style_time_axes(ax, fontsize, cum.index.min(), cum.index.max())
    ax.yaxis.set_major_formatter(PercentTicks())
    ax.set_ylabel(ylabel, color=INK_MUTED, fontsize=fontsize - 1)
    if title:
        ax.set_title(title, loc="left", fontsize=fontsize, color=INK, pad=4)
    right_labels(ax, ends, fontsize, height_in=size_cm[1] * CM)
    return fig
