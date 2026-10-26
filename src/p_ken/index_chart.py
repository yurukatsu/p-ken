"""Index performance chart: rebased to 100 at a base date, with a highlighted period.

    from p_ken import index_chart
    fig = index_chart.plot_rebased(
        series=["world", "em", "rga"],
        base="2026-01-01",
        highlight=("2026-06-01", "2026-09-30"),
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
    "world": SeriesSpec("msci_world.csv", "MSCI World（先進国）"),
    "em": SeriesSpec("msci_em.csv", "MSCI EM（新興国）"),
    "acwi": SeriesSpec("msci_acwi.csv", "MSCI ACWI（全世界）"),
    "rga": SeriesSpec("rga.csv", "RGA（RGA 指数）", column="close"),
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
    highlight: tuple[str, str] | None = ("2026-06-01", "2026-09-30"),
    end: str | None = None,
    variant: str = "net",
    colors: list[str] | None = None,
    title: str | None = None,
    note: str | None = None,
    index_dir: Path = INDEX_DIR,
    figsize: tuple[float, float] = (12.8, 7.2),
) -> plt.Figure:
    """Line chart of indices rebased to 100, highlighted period drawn darker.

    series:    SERIES keys, drawn with colors[i] (default: REDS, dark -> light).
    base:      base date (value on it, or the last before it, = 100).
    highlight: (start, end) drawn in full color; elsewhere the lines are faint.
    end:       last date shown (default: highlight end, else latest data).
    variant:   MSCI column: "close" (price), "net" or "gross".
    """
    series = list(series)
    colors = list(colors or REDS)
    if len(colors) < len(series):
        raise ValueError(f"{len(series)} series but only {len(colors)} colors")
    if end is None and highlight is not None:
        end = highlight[1]
    df = rebased_frame(series, base, end, variant, index_dir)
    hs, he = (pd.Timestamp(d) for d in highlight) if highlight else (None, None)

    fig, ax = plt.subplots(figsize=figsize, dpi=200)
    fig.patch.set_facecolor("white")

    if highlight:
        ax.axvspan(hs, he, color=BAND, zorder=0, lw=0)
        ax.text(
            hs + (he - hs) / 2,
            1.0,
            f"強調期間 {hs:%Y/%m/%d}–{he:%Y/%m/%d}",
            transform=ax.get_xaxis_transform(),
            ha="center",
            va="bottom",
            fontsize=11,
            color=INK_MUTED,
        )
    ax.axhline(100, color=INK_MUTED, lw=0.8, ls="--", zorder=1)

    last_points = []
    for col, color in zip(df.columns, colors, strict=False):
        s = df[col].dropna()
        if highlight:
            inside = s[(s.index >= hs) & (s.index <= he)]
            before = s[s.index <= hs]
            after = s[s.index >= he]
            for part in (before, after):
                if len(part) > 1:
                    ax.plot(
                        part.index,
                        part,
                        color=color,
                        lw=1.6,
                        alpha=MUTED_ALPHA,
                        zorder=2,
                    )
            ax.plot(inside.index, inside, color=color, lw=2.6, zorder=3, label=col)
        else:
            ax.plot(s.index, s, color=color, lw=2.2, zorder=3, label=col)
        last_points.append((s.index[-1], s.iloc[-1], col, color))

    # direct labels at the line ends (text in ink, colored dot = identity)
    y0, y1 = ax.get_ylim()
    ys = _spread_labels([p[1] for p in last_points], min_gap=(y1 - y0) * 0.045)
    x_end = df.index.max()
    for (x, y, name, color), y_lab in zip(last_points, ys, strict=False):
        ax.scatter(
            [x], [y], s=28, color=color, zorder=4, edgecolors="white", linewidths=1
        )
        ax.annotate(
            f"{name}  {y:.1f}",
            xy=(x, y),
            xytext=(x_end + pd.Timedelta(days=4), y_lab),
            va="center",
            fontsize=11,
            color=INK,
            annotation_clip=False,
            arrowprops={
                "arrowstyle": "-",
                "color": GRID,
                "lw": 0.8,
                "shrinkA": 0,
                "shrinkB": 3,
            },
        )

    ax.set_xlim(df.index.min(), x_end)
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y/%m"))
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_MUTED, labelsize=11)
    ax.set_ylabel(
        f"指数（{pd.Timestamp(base):%Y/%m/%d} = 100）", color=INK_MUTED, fontsize=11
    )

    ax.legend(loc="upper left", frameon=False, fontsize=11, labelcolor=INK)
    first = df.index.min()
    ax.set_title(
        title or f"主要指数の推移（{first:%Y/%m/%d} = 100）",
        loc="left",
        fontsize=16,
        color=INK,
        pad=28,
    )
    variant_note = {
        "close": "価格指数",
        "net": "配当込み（ネット）",
        "gross": "配当込み（グロス）",
    }
    msci = [k for k in series if SERIES[k].column is None]
    default_note = (
        f"MSCI は USD 建て・{variant_note.get(variant, variant)}。" if msci else ""
    ) + f"期間 {first:%Y/%m/%d}–{x_end:%Y/%m/%d}。"
    fig.text(0.01, 0.01, note or default_note, fontsize=9, color=INK_MUTED)
    fig.subplots_adjust(left=0.07, right=0.80, top=0.88, bottom=0.08)
    return fig
