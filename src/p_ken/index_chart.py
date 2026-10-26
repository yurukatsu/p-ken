"""Index performance chart: rebased to 100 at a base date, with a highlighted period.

    from p_ken import index_chart
    fig = index_chart.plot_rebased(
        series=["world", "em", "rga"],
        base="2026-01-01",
        highlight=("2026-07-01", "2026-09-30"),
    )

Series are looked up in SERIES (key -> file / column / label) under
data/index_return. Each series is divided by its value on the base date (or the
last value before it) and multiplied by 100.
"""

import itertools
from dataclasses import dataclass
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
from matplotlib import font_manager

INDEX_DIR = Path("data/index_return")


@dataclass(frozen=True)
class SeriesSpec:
    file: str
    label: str  # legend
    short: str  # end-of-line label
    column: str | None = None  # None = MSCI variant column (close / net / gross)


SERIES: dict[str, SeriesSpec] = {
    "world": SeriesSpec("msci_world.csv", "MSCI World Index", "MSCIWO"),
    "em": SeriesSpec("msci_em.csv", "MSCI Emerging Markets Index", "MSCIEM"),
    "acwi": SeriesSpec("msci_acwi.csv", "MSCI ACWI Index", "MSCIACWI"),
    "rga": SeriesSpec("rga.csv", "RGA Index", "RGA", column="close"),
}

# Red shades, dark -> light, assigned in the order series are given.
# Checked with the dataviz palette validator (lightness band, chroma, CVD and
# normal-vision separation pass; the lightest one is low-contrast on white, so
# lines are also labelled directly at their end).
REDS = ["#9e2121", "#df4436", "#f59487"]
MUTED_ALPHA = 0.3  # outside the highlighted period
INK = "#1f1f1f"
INK_MUTED = "#6b6b6b"
GRID = "#e6e6e6"
BAND = "#f2f2f2"
# y-axis title per MSCI variant (lines are rebased to 100 at the base date)
YLABELS = {"close": "Price Return", "net": "Net Return", "gross": "Gross Return"}
# Period return text: plus blue / minus red (CVD-safe pair, minus = 赤字).
POSITIVE = "#1f5fbf"
NEGATIVE = "#c62828"

# Figure size in cm. Default: upper half of a content slide in
# output/template/新興国市場_P検.pptx (27.52 x 19.05 cm slide; content area
# 1.36 cm side margins, from 2.8 cm below the title to the middle of the page).
SLIDE_UPPER_HALF_CM = (24.8, 7.4)
CM = 1 / 2.54

JP_FONTS = [
    "Hiragino Sans",
    "Hiragino Kaku Gothic ProN",
    "YuGothic",
    "Yu Gothic",
    "Noto Sans JP",
    "Noto Sans CJK JP",
    "IPAexGothic",
]


def _use_japanese_font() -> None:
    """Use the first installed Japanese font (macOS / Windows / Linux)."""
    installed = {f.name for f in font_manager.fontManager.ttflist}
    font = next((f for f in JP_FONTS if f in installed), None)
    if font:
        plt.rcParams["font.family"] = font


_use_japanese_font()


def load_series(
    key: str, variant: str = "close", index_dir: Path = INDEX_DIR
) -> pd.Series:
    """Level series (DatetimeIndex) for a SERIES key. variant: close / net / gross."""
    spec = SERIES[key]
    df = pd.read_csv(
        index_dir / spec.file, encoding="utf-8-sig", dtype={"dateymd": str}
    )
    s = df.set_index(pd.to_datetime(df.dateymd, format="%Y%m%d"))[
        spec.column or variant
    ]
    return s.dropna().rename(spec.label)


def rebase(s: pd.Series, base: str | pd.Timestamp, level: float = 100.0) -> pd.Series:
    """Scale so the value on `base` (or the last one before it) equals `level`."""
    base = pd.Timestamp(base)
    before = s[s.index <= base]
    if before.empty:
        raise ValueError(f"{s.name}: no value on or before {base.date()}")
    out = s[s.index >= before.index[-1]] / before.iloc[-1] * level
    return out


def rebased_frame(
    series: list[str],
    base: str,
    end: str | None = None,
    variant: str = "close",
    index_dir: Path = INDEX_DIR,
) -> pd.DataFrame:
    """Rebased levels, one column per series (label), from base to end."""
    cols = [rebase(load_series(k, variant, index_dir), base) for k in series]
    df = pd.concat(cols, axis=1).sort_index()
    if end is not None:
        df = df[df.index <= pd.Timestamp(end)]
    return df


def period_return(s: pd.Series, start: str, end: str) -> float:
    """Return from the last value before `start` to the last value on/before `end`."""
    s = s.dropna()
    before = s[s.index < pd.Timestamp(start)]
    upto = s[s.index <= pd.Timestamp(end)]
    if before.empty or upto.empty:
        return float("nan")
    return upto.iloc[-1] / before.iloc[-1] - 1


def period_returns(df: pd.DataFrame, start: str, end: str) -> pd.Series:
    """period_return for every column of a level / rebased frame."""
    return pd.Series({c: period_return(df[c], start, end) for c in df.columns})


def _spread_labels(ys: list[float], min_gap: float) -> list[float]:
    """Nudge label y positions apart so they do not overlap."""
    order = sorted(range(len(ys)), key=lambda i: ys[i])
    out = list(ys)
    for a, b in itertools.pairwise(order):
        if out[b] - out[a] < min_gap:
            out[b] = out[a] + min_gap
    return out


def _end_labels(fig, ax, ends, x_end, h_in: float, fontsize: float) -> None:
    """Short name + value just right of the line ends, inside the plot.

    Labels are spread vertically so they do not overlap, joined to their line
    end by a thin leader, and the x-axis is extended just enough to fit them.
    """
    y0, y1 = ax.get_ylim()
    min_gap = (y1 - y0) * (fontsize * 1.35 / 72) / (h_in * 0.75)
    ys = _spread_labels([e[1] for e in ends], min_gap=min_gap)
    items = []
    for (x, y, short, value, vcolor), y_lab in zip(ends, ys, strict=False):
        name = ax.text(x_end, y_lab, short, va="center", fontsize=fontsize, color=INK)
        val = ax.annotate(
            value,
            xy=(1, 0.5),
            xycoords=name,
            xytext=(3, 0),
            textcoords="offset points",
            va="center",
            fontsize=fontsize,
            fontweight="bold",
            color=vcolor,
        )
        (leader,) = ax.plot([], [], color=GRID, lw=0.6, zorder=1)
        items.append((x, y, y_lab, name, val, leader))

    gap_pt, pad_pt = 6, 4
    for _ in range(3):
        fig.canvas.draw()
        to_px = ax.transData.transform
        a, b = ax.get_xlim()
        x_end_px = to_px((mdates.date2num(x_end), 0))[0]
        x_lab = ax.transData.inverted().transform(
            (x_end_px + gap_pt * fig.dpi / 72, 0)
        )[0]
        for x, y, y_lab, name, _val, leader in items:
            name.set_x(x_lab)
            leader.set_data([mdates.date2num(x), x_lab], [y, y_lab])
        fig.canvas.draw()
        right_px = (
            max(it[4].get_window_extent().x1 for it in items) + pad_pt * fig.dpi / 72
        )
        width_px = right_px - x_end_px
        axes_w = ax.bbox.width
        if abs(right_px - ax.bbox.x1) < 1:
            return
        x_end_num = mdates.date2num(x_end)
        ax.set_xlim(a, a + (x_end_num - a) * axes_w / (axes_w - width_px))


def plot_rebased(
    series: list[str] = ("world", "em", "rga"),
    base: str = "2026-01-01",
    highlight: tuple[str, str] | None = ("2026-07-01", "2026-09-30"),
    end: str | None = None,
    variant: str = "close",
    colors: list[str] | None = None,
    title: str | None = None,
    ylabel: str | None = None,
    index_dir: Path = INDEX_DIR,
    size_cm: tuple[float, float] = SLIDE_UPPER_HALF_CM,
    fontsize: float = 9,
    dpi: int = 300,
) -> plt.Figure:
    """Line chart of indices rebased to 100, highlighted period drawn darker.

    series:    SERIES keys, drawn with colors[i] (default: REDS, dark -> light).
    base:      base date (value on it, or the last before it, = 100).
    highlight: (start, end) drawn in full color; elsewhere the lines are faint.
               The end labels show each series' return over this period
               (last value before start -> last value on/before end).
    end:       last date shown (default: highlight end, else latest data).
    variant:   MSCI column: "close" (price index, default), "net" or "gross".
    title:     optional title (none by default).
    ylabel:    y-axis title (default from variant: "Price Return", ...).
    size_cm:   figure size as placed on the slide (width, height in cm), so
               `fontsize` (pt) is the size it appears at. Paste without scaling.
    """
    series = list(series)
    colors = list(colors or REDS)
    if len(colors) < len(series):
        raise ValueError(f"{len(series)} series but only {len(colors)} colors")
    if end is None and highlight is not None:
        end = highlight[1]
    df = rebased_frame(series, base, end, variant, index_dir)
    hs, he = (pd.Timestamp(d) for d in highlight) if highlight else (None, None)
    small = fontsize - 1

    w_in, h_in = size_cm[0] * CM, size_cm[1] * CM
    fig, ax = plt.subplots(figsize=(w_in, h_in), dpi=dpi, layout="constrained")
    fig.patch.set_facecolor("white")
    fig.get_layout_engine().set(w_pad=0.04, h_pad=0.04)

    if highlight:
        ax.axvspan(hs, he, color=BAND, zorder=0, lw=0)
    ax.axhline(100, color=INK_MUTED, lw=0.6, ls="--", zorder=1)

    ends = []  # (x, y, short name, value text, value color)
    for key, col, color in zip(series, df.columns, colors, strict=False):
        s = df[col].dropna()
        short = SERIES[key].short
        if highlight:
            # dark part starts at the last point before the period so it joins up
            prior = s[s.index < hs]
            anchor = prior.index[-1] if len(prior) else hs
            before = s[s.index <= anchor]
            inside = s[(s.index >= anchor) & (s.index <= he)]
            after = s[s.index >= he]
            for part in (before, after):
                if len(part) > 1:
                    ax.plot(
                        part.index,
                        part,
                        color=color,
                        lw=1.0,
                        alpha=MUTED_ALPHA,
                        zorder=2,
                    )
            ax.plot(inside.index, inside, color=color, lw=1.8, zorder=3, label=col)
            r = period_return(s, hs, he)
            value, vcolor = (
                f"{r:+.1%}".replace("-", "−"),
                POSITIVE if r >= 0 else NEGATIVE,
            )
        else:
            ax.plot(s.index, s, color=color, lw=1.6, zorder=3, label=col)
            value, vcolor = f"{s.iloc[-1]:.1f}", INK
        ax.scatter(
            [s.index[-1]],
            [s.iloc[-1]],
            s=12,
            color=color,
            zorder=4,
            edgecolors="white",
            linewidths=0.6,
        )
        ends.append((s.index[-1], s.iloc[-1], short, value, vcolor))

    x_first, x_end = df.index.min(), df.index.max()
    ax.set_xlim(x_first, x_end)
    _end_labels(fig, ax, ends, x_end, h_in, fontsize)

    # month ticks only where there is data (not in the label area)
    months = pd.date_range(x_first.to_period("M").to_timestamp(), x_end, freq="MS")
    ax.xaxis.set_major_locator(mticker.FixedLocator(mdates.date2num(months)))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y/%m"))
    ax.grid(axis="y", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_MUTED, labelsize=small, length=2, pad=2)
    if ylabel is None:
        ylabel = YLABELS.get(variant, variant)
    ax.set_ylabel(ylabel, color=INK_MUTED, fontsize=small)
    # legend in one row above the plot, so it never covers the lines
    ax.legend(
        loc="lower left",
        bbox_to_anchor=(0, 1.0),
        ncol=len(series),
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
