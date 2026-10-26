"""Shared look of all charts: colours, fonts, slide sizes and axis helpers.

Every figure is rendered at the size it occupies on the 4:3 slide template
(output/template/新興国市場_P検.pptx, 27.52 x 19.05 cm), so font sizes are the
sizes seen on the slide. Paste the PNGs without scaling.
"""

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from matplotlib import font_manager

CM = 1 / 2.54  # inches per cm

# Slide areas (width, height in cm). Content area: 1.36 cm side margins,
# from 2.8 cm below the title to just above the page number.
SLIDE_FULL_CM = (24.8, 15.0)  # whole content area (treemaps)
SLIDE_HALF_CM = (24.8, 7.4)  # upper / lower half (line charts)
SLIDE_QUARTER_CM = (12.2, 7.4)  # upper-left / upper-right quarter (bar charts)

# Text and structure
INK = "#1f1f1f"
INK_MUTED = "#6b6b6b"
GRID = "#e6e6e6"
BAND = "#f2f2f2"  # highlighted period background
SURFACE = "#ffffff"
MUTED_ALPHA = 0.3  # lines outside the highlighted period

# Signed values: plus blue / minus red (CVD-safe pair; minus = 赤字)
POSITIVE = "#1f5fbf"
NEGATIVE = "#c62828"

# Index lines: red shades, dark -> light (validated with the dataviz palette checker)
REDS = ["#9e2121", "#df4436", "#f59487"]
# Categorical lines (factor types), fixed order; beyond 8 / "Other" use grey
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
OTHER = "#8a8a8a"
COMPOSITE = "#262626"  # composite scores (ai70_bd30, GEMQ3): near-black

JP_FONTS = [
    "Hiragino Sans",
    "Hiragino Kaku Gothic ProN",
    "YuGothic",
    "Yu Gothic",
    "Noto Sans JP",
    "Noto Sans CJK JP",
    "IPAexGothic",
]


def use_japanese_font() -> None:
    """Use the first installed Japanese font (macOS / Windows / Linux)."""
    installed = {f.name for f in font_manager.fontManager.ttflist}
    font = next((f for f in JP_FONTS if f in installed), None)
    if font:
        plt.rcParams["font.family"] = font


use_japanese_font()


def fmt_pct(x: float, decimals: int = 1) -> str:
    """'+1.2%' / '−3.4%' (true minus sign)."""
    return f"{x:+.{decimals}%}".replace("-", "−")


def signed_color(x: float) -> str:
    return POSITIVE if x >= 0 else NEGATIVE


class PercentTicks(mticker.Formatter):
    """Percent tick labels with just enough decimals for the tick spacing."""

    def __call__(self, x, pos=None):
        locs = np.asarray(self.locs)
        step = np.diff(np.sort(locs)).min() if len(locs) > 1 else 1.0
        decimals = max(0, int(np.ceil(-np.log10(step * 100) - 1e-9)))
        v = x * 100
        if abs(v) < 0.5 * 10**-decimals:
            v = 0.0  # no "-0%"
        return f"{v:.{decimals}f}%".replace("-", "−")


def new_figure(size_cm: tuple[float, float], dpi: int = 300, pad: float = 0.04):
    """Figure + axes at slide size with constrained layout."""
    fig, ax = plt.subplots(
        figsize=(size_cm[0] * CM, size_cm[1] * CM), dpi=dpi, layout="constrained"
    )
    fig.patch.set_facecolor(SURFACE)
    fig.get_layout_engine().set(w_pad=pad, h_pad=pad)
    return fig, ax


def style_time_axes(ax, fontsize: float, first: pd.Timestamp, last: pd.Timestamp) -> None:
    """Recessive grid / spines, month ticks within [first, last], small tick labels."""
    months = pd.date_range(first.to_period("M").to_timestamp(), last, freq="MS")
    months = months[months >= first]
    ax.set_xlim(first, last)
    ax.xaxis.set_major_locator(mticker.FixedLocator(mdates.date2num(months)))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y/%m"))
    ax.grid(axis="y", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_MUTED, labelsize=fontsize - 1, length=2, pad=2)


def plot_highlighted(
    ax,
    s: pd.Series,
    highlight: tuple[str, str] | None,
    color: str,
    lw: float,
    lw_muted: float,
    label: str | None = None,
) -> None:
    """Line in full colour inside the highlight period, faint outside.

    The full-colour part starts at the last point before the period so the
    line joins up.
    """
    if not highlight:
        ax.plot(s.index, s, color=color, lw=lw, zorder=3, label=label)
        return
    hs, he = (pd.Timestamp(d) for d in highlight)
    prior = s[s.index < hs]
    anchor = prior.index[-1] if len(prior) else hs
    inside = s[(s.index >= anchor) & (s.index <= he)]
    for part in (s[s.index <= anchor], s[s.index >= inside.index[-1]]):
        if len(part) > 1:
            ax.plot(part.index, part, color=color, lw=lw_muted, alpha=MUTED_ALPHA, zorder=2)
    ax.plot(inside.index, inside, color=color, lw=lw, zorder=3, label=label)
