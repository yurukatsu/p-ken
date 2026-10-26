"""Treemap of stocks: cell area = weight, colour = period return.

Adapted from plot_treemap in ../datastream (marketdata). Stocks are grouped by
one or more levels (e.g. country, sector, country > sector); every group is
headed by its weight-weighted return (and, at the top level, its total weight)
when the header fits. Cells use a diverging blue (+) / red (-) scale that
saturates at +-clip; labels are sized to fit each cell.
"""

from functools import cache

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import squarify
from matplotlib.colors import LinearSegmentedColormap, Normalize, to_rgb
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Rectangle
from matplotlib.textpath import TextPath

from p_ken.charts.style import CM, INK, INK_MUTED, NEGATIVE, POSITIVE, SLIDE_FULL_CM, SURFACE

NA_FILL = "#d6d6d1"
MID = "#f0efec"  # diverging midpoint (neutral grey)
CMAP = LinearSegmentedColormap.from_list("returns", ["#8e1b1b", NEGATIVE, MID, POSITIVE, "#123f7a"])


@cache
def _text_width(text: str, fs: float, bold: bool = False) -> float:
    """Width in pt of a single line, measured with the current font (cached)."""
    prop = FontProperties(family=plt.rcParams["font.family"], weight="bold" if bold else "normal")
    return TextPath((0, 0), text, size=fs, prop=prop).get_extents().width


def _wrap(name: str, fs: float, width: float, max_lines: int = 3) -> list[str] | None:
    """Greedy word wrap of name into lines narrower than width (None if it cannot)."""
    lines, cur = [], ""
    for word in name.split():
        trial = f"{cur} {word}".strip()
        if _text_width(trial, fs) <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    if len(lines) > max_lines or any(_text_width(x, fs) > width for x in lines):
        return None
    return lines


def _ink_for(rgb) -> str:
    r, g, b = to_rgb(rgb)
    return INK if 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.5 else "white"


def _fit_label(name: str, value: str, w: float, h: float, fs_max: float, fs_min: float):
    """Largest font (and text) that fits a w x h pt cell.

    Tries the name (wrapped onto up to 3 lines) above the value, then the value alone.
    """
    if w < 8 or h < fs_min:
        return None, None
    fs = fs_max
    while fs >= fs_min:
        lines = _wrap(name, fs, w - 3) if name else None
        if lines and (len(lines) + 1) * fs * 1.15 <= h - 1 and _text_width(value, fs) <= w - 3:
            return fs, "\n".join([*lines, value])
        fits = _text_width(value, fs) <= w - 3 and fs * 1.2 <= h - 1
        if fits and (fs <= fs_max - 1.5 or not name):  # prefer a smaller font with the name
            return fs, value
        fs -= 0.5
    fs = fs_min
    if _text_width(value, fs) <= w - 3 and fs * 1.2 <= h - 1:
        return fs, value
    return None, None


SECTOR_SHORT = {
    "Information Technology": "IT",
    "Communication Services": "Comm. Svcs",
    "Consumer Discretionary": "Cons. Disc.",
    "Consumer Staples": "Cons. Staples",
    "Health Care": "Health Care",
    "Real Estate": "Real Estate",
    "Financials": "Financials",
    "Industrials": "Industrials",
    "Materials": "Materials",
    "Utilities": "Utilities",
    "Energy": "Energy",
}
GROUP_BAND = "#f2f2f2"  # background of second-level groups


def plot_treemap(
    stocks: pd.DataFrame,
    groups: str | list[str] = "country",
    title: str | None = None,
    subtitle: str | None = None,
    clip: float = 0.2,
    size_cm: tuple[float, float] = SLIDE_FULL_CM,
    fontsize: float = 8,
    dpi: int = 300,
) -> plt.Figure:
    """Treemap grouped by `groups` (e.g. "country", "sector", ["country", "sector"]).

    Area = weight, colour = return. Each group is headed (when it fits) by its
    weight-weighted return, and top-level groups also by their total weight.
    """
    groups = [groups] if isinstance(groups, str) else list(groups)
    data = stocks[stocks["weight"] > 0].copy()
    for g in groups:
        data[g] = data[g].fillna("Other")
    norm = Normalize(-clip, clip)
    w_in, h_in = size_cm[0] * CM, size_cm[1] * CM
    fig = plt.figure(figsize=(w_in, h_in), dpi=dpi)
    fig.patch.set_facecolor(SURFACE)

    top_pt = (fontsize + 4) * 1.4 if (title or subtitle) else 2
    ax = fig.add_axes((0, 0, 1, 1 - top_pt / (h_in * 72)))
    ax.axis("off")
    W, H = w_in * 72, h_in * 72 - top_pt  # axes in pt; y grows downwards
    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)

    def rects(sizes, x, y, w, h):
        if w <= 0 or h <= 0:
            return [{"x": x, "y": y, "dx": 0, "dy": 0} for _ in sizes]
        return squarify.squarify(squarify.normalize_sizes(sizes, w, h), x, y, w, h)

    def weighted(df):
        v = df.dropna(subset=["return"])
        return (v.weight * v["return"]).sum() / v.weight.sum() if len(v) else np.nan

    def draw_leaves(df, x, y, w, h):
        df = df.sort_values("weight", ascending=False)
        for (_, row), c in zip(df.iterrows(), rects(df.weight.tolist(), x, y, w, h), strict=True):
            v = row["return"]
            fill = CMAP(norm(v)) if pd.notna(v) else NA_FILL
            ax.add_patch(
                Rectangle(
                    (c["x"], c["y"]),
                    c["dx"],
                    c["dy"],
                    facecolor=fill,
                    edgecolor=SURFACE,
                    lw=0.4,
                )
            )
            value = f"{v:+.1%}".replace("-", "−") if pd.notna(v) else "n/a"
            fs, label = _fit_label(
                str(row["label"]), value, c["dx"], c["dy"], fontsize, fontsize - 2.5
            )
            if label:
                ax.text(
                    c["x"] + c["dx"] / 2,
                    c["y"] + c["dy"] / 2,
                    label,
                    ha="center",
                    va="center",
                    fontsize=fs,
                    linespacing=1.1,
                    color=_ink_for(fill),
                )

    def draw_level(df, level, x, y, w, h):
        if level == len(groups):
            draw_leaves(df, x, y, w, h)
            return
        col, top = groups[level], level == 0
        fs = fontsize if top else fontsize - 1
        header_h, pad = (fs * 1.6, 1.0) if top else (fs * 1.45, 0.8)
        sizes = df.groupby(col).weight.sum().sort_values(ascending=False)
        for name, r in zip(sizes.index, rects(sizes.tolist(), x, y, w, h), strict=True):
            sub = df[df[col] == name]
            gx, gy = r["x"] + pad, r["y"] + pad
            gw, gh = r["dx"] - 2 * pad, r["dy"] - 2 * pad
            ax.add_patch(
                Rectangle(
                    (r["x"], r["y"]),
                    r["dx"],
                    r["dy"],
                    facecolor=SURFACE if top else GROUP_BAND,
                    edgecolor=INK_MUTED if top else "#c8c8c8",
                    lw=0.8 if top else 0.5,
                )
            )
            ret = f"{weighted(sub):+.1%}".replace("-", "−")
            short = SECTOR_SHORT.get(name, name) if col == "sector" else name
            options = [f"{name}  {ret}", f"{short}  {ret}", str(short)]
            if top:
                options.insert(0, f"{name}  {ret} (w {sub.weight.sum():.1%})")
            text = next((t for t in options if _text_width(t, fs, bold=top) < gw - 3), None)
            if text and gh > header_h * 2.2:
                ax.text(
                    gx + 1.5,
                    gy + header_h / 2,
                    text,
                    va="center",
                    fontsize=fs,
                    fontweight="bold" if top else "normal",
                    color=INK,
                )
                gy, gh = gy + header_h, gh - header_h
            draw_level(sub, level + 1, gx, gy, gw, gh)

    draw_level(data, 0, 0, 0, W, H)

    # header row: title / subtitle on the left, colour scale on the right
    if title or subtitle:
        y = 1 - (top_pt / 2) / (h_in * 72)
        x = 0.003
        if title:
            t = fig.text(x, y, title, va="center", fontsize=fontsize + 1, color=INK)
            fig.canvas.draw()
            x = t.get_window_extent().x1 / fig.bbox.width + 0.01
        if subtitle:
            fig.text(x, y, subtitle, va="center", fontsize=fontsize - 1, color=INK_MUTED)
        steps = np.linspace(-clip, clip, 9)
        sw, sh = 0.022, (fontsize * 0.9) / (h_in * 72)
        lx = 1 - 0.005 - len(steps) * sw - 0.03
        for i, v in enumerate(steps):
            fig.patches.append(
                Rectangle(
                    (lx + i * sw, y - sh / 2),
                    sw,
                    sh,
                    transform=fig.transFigure,
                    facecolor=CMAP(norm(v)),
                    edgecolor=SURFACE,
                    lw=0.4,
                )
            )
        for v, xpos, ha in ((-clip, lx, "right"), (clip, lx + len(steps) * sw, "left")):
            fig.text(
                xpos + (-0.003 if ha == "right" else 0.003),
                y,
                f"{v:+.0%}".replace("-", "−"),
                ha=ha,
                va="center",
                fontsize=fontsize - 1,
                color=INK_MUTED,
            )
    return fig
