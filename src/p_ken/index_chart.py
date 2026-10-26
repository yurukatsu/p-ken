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
import numpy as np
import pandas as pd
from matplotlib import font_manager, patheffects

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


def _line_hits(box, lines_px) -> int:
    """Pixel columns where any line passes through `box` (x0, y0, x1, y1)."""
    x0, y0, x1, y1 = box
    xs = np.arange(np.floor(x0), np.ceil(x1) + 1)
    hits = 0
    for lx, ly in lines_px:
        inside = (xs >= lx[0]) & (xs <= lx[-1])
        if not inside.any():
            continue
        y = np.interp(xs[inside], lx, ly)
        hits += int(((y >= y0) & (y <= y1)).sum())
    return hits


def _overlap(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _end_labels(fig, ax, ends, lines, fontsize: float, halo: str = "white") -> None:
    """Short name + value above or below each line end, inside the plot.

    Labels are right-aligned at the line end. Each label can sit above or below
    its end point at a few distances; every combination is scored by how much
    line passes through the boxes (hard penalties for overlapping each other or
    leaving the plot, a small one for distance) and the cleanest is used.
    Labels moved away from their end point get a thin leader line.
    """
    pt = fig.dpi / 72
    gap, inset = 2.5 * pt, 3 * pt  # from the end point: vertical / horizontal
    stroke = [patheffects.withStroke(linewidth=2.5, foreground=halo)]

    items = []
    for _x, _y, short, value, vcolor in ends:
        val = ax.text(
            0, 0, value, ha="right", fontsize=fontsize, fontweight="bold", color=vcolor
        )
        name = ax.annotate(
            short,
            xy=(0, 0),
            xycoords=val,
            xytext=(-3, 0),
            textcoords="offset points",
            ha="right",
            va="bottom",
            fontsize=fontsize,
            color=INK,
        )
        for t in (val, name):
            t.set_in_layout(False)  # inside the plot; keep them out of the layout
            t.set_path_effects(stroke)
            t.set_zorder(5)
        items.append((val, name))

    fig.canvas.draw()  # settle the layout so pixel positions are final
    to_px = ax.transData.transform
    lines_px = []
    for lx, ly in lines:
        pts = to_px(np.column_stack([lx, ly]))
        lines_px.append((pts[:, 0], pts[:, 1]))

    renderer = fig.canvas.get_renderer()
    ab = ax.bbox
    candidates = []  # per label: list of (box, anchor y px, va, shift px, hits)
    for (x, y, *_), (val, name) in zip(ends, items, strict=False):
        v, n = val.get_window_extent(renderer), name.get_window_extent(renderer)
        w, h = v.x1 - n.x0, max(v.height, n.height)
        ex, ey = to_px((mdates.date2num(x), y))
        right = ex - inset
        cands = []
        for shift in (0, 0.5 * h, h, 1.5 * h, 2 * h, 3 * h):
            lo = ey + gap + shift
            hi = ey - gap - shift
            for box, anchor, va in (
                ((right - w, lo, right, lo + h), lo, "bottom"),
                ((right - w, hi - h, right, hi), hi, "top"),
            ):
                pad = (box[0] - 1, box[1] - 1, box[2] + 1, box[3] + 1)
                hits = _line_hits(pad, lines_px)
                if box[0] < ab.x0 or box[1] < ab.y0 or box[3] > ab.y1:
                    hits += 1000
                cands.append((box, anchor, va, shift, hits))
        candidates.append(cands)

    def cost(choice) -> float:
        picked = [candidates[i][c] for i, c in enumerate(choice)]
        total = sum(c[4] * 10 + c[3] / pt * 0.2 for c in picked)
        for c1, c2 in itertools.combinations(picked, 2):
            if _overlap(c1[0], c2[0]):
                total += 10000
        return total

    best = min(itertools.product(*(range(len(c)) for c in candidates)), key=cost)
    to_data = ax.transData.inverted().transform
    for (val, name), (x, y, *_), choice, cands in zip(
        items, ends, best, candidates, strict=False
    ):
        box, anchor_y, va, shift, _hits = cands[choice]
        val.set_position(to_data((box[2], anchor_y)))
        val.set_va(va)
        name.set_va(va)
        name.xy = (0, 0) if va == "bottom" else (0, 1)
        if shift > 0:  # leader from the end point to the label's near corner
            near_y = box[1] if va == "bottom" else box[3]
            lx, ly = to_data((box[2], near_y))
            ax.plot(
                [mdates.date2num(x), lx], [y, ly], color=INK_MUTED, lw=0.5, zorder=4
            )


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
    ylabel:    y-axis title (default from variant, e.g. "Price Return (2026/01/01 = 100)").
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
    lines = []  # (x as date numbers, y) of every drawn line, for label placement
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
            lines.append((mdates.date2num(s.index), s.to_numpy()))
            r = period_return(s, hs, he)
            value, vcolor = (
                f"{r:+.1%}".replace("-", "−"),
                POSITIVE if r >= 0 else NEGATIVE,
            )
        else:
            ax.plot(s.index, s, color=color, lw=1.6, zorder=3, label=col)
            lines.append((mdates.date2num(s.index), s.to_numpy()))
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
        ends.append((s.index[-1], s.iloc[-1], short, value, vcolor))

    x_first, x_end = df.index.min(), df.index.max()
    ax.set_xlim(x_first, x_end)
    _end_labels(fig, ax, ends, lines, fontsize, halo=BAND if highlight else "white")

    # month ticks within the data range
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
        ylabel = (
            f"{YLABELS.get(variant, variant)} ({pd.Timestamp(base):%Y/%m/%d} = 100)"
        )
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
