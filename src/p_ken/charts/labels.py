"""Direct labels at the end of lines.

in_plot_labels   short name + value just above or below each line end, inside
                 the plot (best above/below and distance chosen by search)
right_labels     name + value in a column right of the plot, spread apart
"""

import itertools

import matplotlib.dates as mdates
import numpy as np
from matplotlib import patheffects

from p_ken.charts.style import INK, INK_MUTED, fmt_pct, signed_color


def _line_hits(box, lines_px) -> int:
    """Pixel columns where any line passes through box (x0, y0, x1, y1)."""
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


def in_plot_labels(fig, ax, ends, lines, fontsize: float, halo: str = "white") -> None:
    """ends: [(x, y, short name, value text, value colour)]; lines: [(x num, y)].

    Labels are right-aligned at the line end. Each can sit above or below its
    end point at a few distances; every combination is scored by how much line
    passes through the boxes (hard penalties for overlapping each other or
    leaving the plot, a small one for distance) and the cleanest is used.
    Labels moved away from their end point get a thin leader line.
    """
    pt = fig.dpi / 72
    gap, inset = 2.5 * pt, 3 * pt  # from the end point: vertical / horizontal
    stroke = [patheffects.withStroke(linewidth=2.5, foreground=halo)]

    items = []
    for _x, _y, short, value, vcolor in ends:
        val = ax.text(0, 0, value, ha="right", fontsize=fontsize, fontweight="bold", color=vcolor)
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
            t.set_in_layout(False)
            t.set_path_effects(stroke)
            t.set_zorder(5)
        items.append((val, name))

    fig.canvas.draw()  # settle the layout so pixel positions are final
    to_px = ax.transData.transform
    lines_px = [tuple(to_px(np.column_stack([lx, ly])).T) for lx, ly in lines]

    renderer = fig.canvas.get_renderer()
    ab = ax.bbox
    candidates = []  # per label: [(box, anchor y px, va, shift px, hits)]
    for (x, y, *_), (val, name) in zip(ends, items, strict=True):
        v, n = val.get_window_extent(renderer), name.get_window_extent(renderer)
        w, h = v.x1 - n.x0, max(v.height, n.height)
        ex, ey = to_px((mdates.date2num(x), y))
        right = ex - inset
        cands = []
        for shift in (0, 0.5 * h, h, 1.5 * h, 2 * h, 3 * h):
            lo, hi = ey + gap + shift, ey - gap - shift
            for box, anchor, va in (
                ((right - w, lo, right, lo + h), lo, "bottom"),
                ((right - w, hi - h, right, hi), hi, "top"),
            ):
                hits = _line_hits((box[0] - 1, box[1] - 1, box[2] + 1, box[3] + 1), lines_px)
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
    for (val, name), (x, y, *_), choice, cands in zip(items, ends, best, candidates, strict=True):
        box, anchor_y, va, shift, _ = cands[choice]
        val.set_position(to_data((box[2], anchor_y)))
        val.set_va(va)
        name.set_va(va)
        name.xy = (0, 0) if va == "bottom" else (0, 1)
        if shift > 0:  # leader from the end point to the label's near corner
            near_y = box[1] if va == "bottom" else box[3]
            lx, ly = to_data((box[2], near_y))
            ax.plot([mdates.date2num(x), lx], [y, ly], color=INK_MUTED, lw=0.5, zorder=4)


def _spread(ys: list[float], min_gap: float) -> list[float]:
    """Spread positions at least min_gap apart, centred on the originals."""
    order = np.argsort(ys)
    pos = np.array(ys, float)[order]
    for _ in range(200):
        moved = False
        for i in range(1, len(pos)):
            gap = pos[i] - pos[i - 1]
            if gap < min_gap:
                push = (min_gap - gap) / 2
                pos[i - 1] -= push
                pos[i] += push
                moved = True
        if not moved:
            break
    out = np.empty_like(pos)
    out[order] = pos
    return out.tolist()


def right_labels(ax, ends, fontsize: float, height_in: float) -> None:
    """ends: [(x, y, name, value, line colour)]; value shown signed and coloured."""
    y0, y1 = ax.get_ylim()
    min_gap = (y1 - y0) * (fontsize * 1.3 / 72) / (height_in * 0.78)
    ys = _spread([e[1] for e in ends], min_gap)
    for (x, y, name, value, color), y_lab in zip(ends, ys, strict=True):
        ax.scatter([x], [y], s=8, color=color, zorder=4, clip_on=False, linewidths=0)
        at = {"xytext": (1.012, y_lab), "textcoords": ("axes fraction", "data")}
        ax.annotate(
            "",
            xy=(x, y),
            **at,
            annotation_clip=False,
            arrowprops={"arrowstyle": "-", "color": color, "lw": 0.5, "shrinkA": 0, "shrinkB": 0},
        )
        name_t = ax.annotate(
            name, xy=(x, y), **at, va="center", fontsize=fontsize, color=INK, annotation_clip=False
        )
        ax.annotate(
            fmt_pct(value),
            xy=(1, 0.5),
            xycoords=name_t,
            xytext=(3, 0),
            textcoords="offset points",
            va="center",
            fontsize=fontsize,
            fontweight="bold",
            color=signed_color(value),
        )
