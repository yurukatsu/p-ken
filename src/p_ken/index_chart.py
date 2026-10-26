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
import pandas as pd
from matplotlib import font_manager

INDEX_DIR = Path("data/index_return")


@dataclass(frozen=True)
class SeriesSpec:
    file: str
    label: str
    column: str | None = None  # None = MSCI variant column (close / net / gross)


SERIES: dict[str, SeriesSpec] = {
    "world": SeriesSpec("msci_world.csv", "MSCI World Index"),
    "em": SeriesSpec("msci_em.csv", "MSCI Emerging Markets Index"),
    "acwi": SeriesSpec("msci_acwi.csv", "MSCI ACWI Index"),
    "rga": SeriesSpec("rga.csv", "RGA Index", column="close"),
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
    key: str, variant: str = "net", index_dir: Path = INDEX_DIR
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
    variant: str = "net",
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


def plot_rebased(
    series: list[str] = ("world", "em", "rga"),
    base: str = "2026-01-01",
    highlight: tuple[str, str] | None = ("2026-07-01", "2026-09-30"),
    end: str | None = None,
    variant: str = "net",
    colors: list[str] | None = None,
    title: str | None = None,
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
    variant:   MSCI column: "close" (price), "net" or "gross".
    title:     optional title (none by default).
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

    ends = []
    for col, color in zip(df.columns, colors, strict=False):
        s = df[col].dropna()
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
            text = f"{col}  {period_return(s, hs, he):+.1%}"
        else:
            ax.plot(s.index, s, color=color, lw=1.6, zorder=3, label=col)
            text = f"{col}  {s.iloc[-1]:.1f}"
        ends.append((s.index[-1], s.iloc[-1], text, color))

    ax.set_xlim(df.index.min(), df.index.max())

    # direct labels just right of the plot (text in ink, colored dot = identity);
    # the gap between labels is one text line, converted to data units
    y0, y1 = ax.get_ylim()
    line_in = fontsize * 1.3 / 72
    min_gap = (y1 - y0) * line_in / (h_in * 0.75)
    ys = _spread_labels([p[1] for p in ends], min_gap=min_gap)
    for (x, y, text, color), y_lab in zip(ends, ys, strict=False):
        ax.scatter(
            [x], [y], s=12, color=color, zorder=4, edgecolors="white", linewidths=0.6
        )
        ax.annotate(
            text,
            xy=(x, y),
            xytext=(1.012, y_lab),
            textcoords=("axes fraction", "data"),
            va="center",
            fontsize=fontsize,
            color=INK,
            annotation_clip=False,
            arrowprops={
                "arrowstyle": "-",
                "color": GRID,
                "lw": 0.6,
                "shrinkA": 0,
                "shrinkB": 2,
            },
        )

    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y/%m"))
    ax.grid(axis="y", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_MUTED, labelsize=small, length=2, pad=2)
    ax.set_ylabel(
        f"指数（{pd.Timestamp(base):%Y/%m/%d} = 100）", color=INK_MUTED, fontsize=small
    )
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
