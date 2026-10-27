"""Build and save every report figure (PNG + CSV of the plotted numbers).

Each function takes the report Period (config/report.toml) and writes to
out_dir (default output/figures). File names are stable so the slides can be
updated by overwriting.

    from p_ken import config, report
    paths = report.all_figures(config.load_period())
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from p_ken import charts, config, factors, markets
from p_ken.charts.style import COMPOSITE, SLIDE_FULL_CM, SLIDE_HALF_CM, SLIDE_QUARTER_CM
from p_ken.config import UNIVERSES, Period
from p_ken.stats import period_return

# Same factor, same colour across charts (blue / orange / aqua pass all-pairs
# CVD checks; composite scores in near-black).
NAM_COLORS = {
    "gemq": {"AI": "#2a78d6", "Revision": "#eb6834", "GEMQ3": COMPOSITE},
    "blf": {
        "AI": "#2a78d6",
        "TVL": "#eb6834",
        "RVL": "#1baf7a",
        "Composite (ai70_bd30)": COMPOSITE,
    },
}
TREEMAP_GROUPINGS = {
    "country": ["country"],
    "sector": ["sector"],
    "country_sector": ["country", "sector"],
}


def _out(out_dir: Path | None) -> Path:
    out = Path(out_dir) if out_dir else config.figures_dir()
    out.mkdir(parents=True, exist_ok=True)
    return out


def _save(fig, path: Path) -> Path:
    fig.savefig(path)
    plt.close(fig)
    return path


def _ymd(date: str) -> str:
    return date.replace("-", "")


# --- 1. index line chart (slide 2, upper half) ------------------------------------------


def index_chart(
    period: Period,
    series: tuple[str, ...] = ("world", "em", "rga"),
    variant: str = "net",
    out_dir: Path | None = None,
    size_cm=SLIDE_HALF_CM,
    fontsize: float = 9,
) -> list[Path]:
    """MSCI World / EM / RGA rebased to 100 at ytd_start, highlight = the quarter."""
    out = _out(out_dir)
    levels = markets.rebased_indices(list(series), period.ytd_start, period.end, variant)
    short = {markets.INDEX_SERIES[k].label: markets.INDEX_SERIES[k].short for k in series}
    ylabel = f"{markets.VARIANT_LABEL[variant]} ({pd.Timestamp(period.ytd_start):%Y/%m/%d} = 100)"
    fig = charts.plot_rebased(
        levels, short, period.highlight, ylabel, size_cm=size_cm, fontsize=fontsize
    )
    stem = out / f"index_{'_'.join(series)}_{_ymd(period.ytd_start)}"
    levels.round(4).to_csv(f"{stem}.csv", index_label="date")
    print(
        "  quarter: "
        + ", ".join(
            f"{c} {period_return(levels[c], *period.highlight):+.2%}" for c in levels.columns
        )
    )
    return [_save(fig, stem.with_suffix(".png")), stem.with_suffix(".csv")]


# --- 2. country / sector period bars (slide 3, upper quarters) ------------------------------


def period_bars(
    period: Period,
    groups: tuple[str, ...] = ("country", "em_sector"),
    checkpoints: list[str] | None = None,
    benchmark: bool = True,
    out_dir: Path | None = None,
    size_cm=SLIDE_QUARTER_CM,
    fontsize: float = 7,
) -> list[Path]:
    """Quarter USD returns per country / MSCI EM sector, markers at month ends."""
    out = _out(out_dir)
    cps = (
        [*checkpoints, period.end] if checkpoints else markets.month_ends(period.start, period.end)
    )
    paths = []
    for group in groups:
        close = markets.load_market_closes(group, benchmark)
        table = markets.checkpoint_returns(close, period.start, cps)
        fig = charts.plot_period_bars(
            table,
            markets.base_date(close, period.start),
            benchmark=markets.BENCHMARK if benchmark else None,
            size_cm=size_cm,
            fontsize=fontsize,
        )
        stem = out / f"period_returns_{group}_{period.tag}"
        shown = table.dropna(subset=[table.columns[-1]]).sort_values(
            table.columns[-1], ascending=False
        )
        shown.set_axis([f"{c:%Y-%m-%d}" for c in shown.columns], axis=1).round(6).to_csv(
            f"{stem}.csv", index_label="market"
        )
        paths += [_save(fig, stem.with_suffix(".png")), stem.with_suffix(".csv")]
    return paths


# --- 3. common (core) factor returns by type (slide 4) --------------------------------------


def common_factor_charts(
    period: Period,
    universes: tuple[str, ...] = tuple(UNIVERSES),
    returns: tuple[str, ...] = ("ret", "sret"),
    out_dir: Path | None = None,
    size_cm=SLIDE_HALF_CM,
    fontsize: float = 8,
) -> list[Path]:
    """Core factor returns averaged by fc_list type, cumulative sum from ytd_start."""
    out = _out(out_dir)
    types: dict[str, None] = {}
    for u in UNIVERSES:  # same colour for the same type in every chart
        types.update(dict.fromkeys(factors.core_factor_list(u).type))
    types.pop("Seasonality", None)  # not in the core files
    colors = charts.category_colors(list(types))
    paths = []
    for u in universes:
        for rc in returns:
            daily = factors.core_factor_returns(u, period.ytd_start, period.end, rc)
            by_type = factors.type_returns(daily, u)
            title = UNIVERSES[u] + (" (Specific Return)" if rc == "sret" else "")
            fig = charts.plot_cumulative(
                by_type,
                period.ytd_start,
                period.highlight,
                title,
                colors,
                size_cm=size_cm,
                fontsize=fontsize,
            )
            stem = (
                out / f"common_fret_{u}_{_ymd(period.ytd_start)}{'_sret' if rc == 'sret' else ''}"
            )
            daily.to_csv(f"{stem}_factors.csv", index_label="date")
            by_type.to_csv(f"{stem}_types.csv", index_label="date")
            paths += [_save(fig, stem.with_suffix(".png")), Path(f"{stem}_types.csv")]
    return paths


# --- 4. NAM factor returns (slides 5, 6) ---------------------------------------------------------


def nam_factor_charts(
    period: Period,
    universes: tuple[str, ...] = tuple(UNIVERSES),
    methods: tuple[str, ...] = ("regression", "q5"),
    returns: tuple[str, ...] = ("ret", "sret"),
    out_dir: Path | None = None,
    size_cm=SLIDE_HALF_CM,
    fontsize: float = 8,
) -> list[Path]:
    """NAM factor returns (regression slope, or Q5 excess), cumulative sum from ytd_start."""
    out = _out(out_dir)
    paths = []
    for u in universes:
        for method in methods:
            for rc in returns:
                daily = factors.nam_factor_returns(u, period.ytd_start, period.end, rc, method)
                detail = (["Q5 Excess"] if method == "q5" else []) + (
                    ["Specific Return"] if rc == "sret" else []
                )
                title = UNIVERSES[u] + (f" ({', '.join(detail)})" if detail else "")
                ylabel = (
                    "Q5 Excess Return (cumulative sum)"
                    if method == "q5"
                    else "Factor Return (cumulative sum)"
                )
                fig = charts.plot_cumulative(
                    daily,
                    period.ytd_start,
                    period.highlight,
                    title,
                    NAM_COLORS[u],
                    ylabel=ylabel,
                    size_cm=size_cm,
                    fontsize=fontsize,
                )
                suffix = ("_q5" if method == "q5" else "") + ("_sret" if rc == "sret" else "")
                stem = out / f"nam_fret_{u}_{_ymd(period.ytd_start)}{suffix}"
                daily.to_csv(f"{stem}.csv", index_label="date")
                paths += [_save(fig, stem.with_suffix(".png")), stem.with_suffix(".csv")]
    return paths


# --- 5. stock treemaps (one slide each) -------------------------------------------------------------


def treemaps(
    period: Period,
    universes: tuple[str, ...] = tuple(UNIVERSES),
    groupings: tuple[str, ...] = tuple(TREEMAP_GROUPINGS),
    clip: float = 0.2,
    out_dir: Path | None = None,
    size_cm=SLIDE_FULL_CM,
    fontsize: float = 8,
) -> list[Path]:
    """Area = weight at period end, colour = USD return over the period (LSEG)."""
    out = _out(out_dir)
    paths = []
    for u in universes:
        stocks = markets.load_stocks(u, period.tag)
        base = pd.to_datetime(stocks["base_date"]).min()
        end = pd.Timestamp(period.end)
        subtitle = (
            f"Size = weight ({end:%-m/%-d}), Colour = return {base:%-m/%-d}–{end:%-m/%-d} (USD)"
        )
        for g in groupings:
            fig = charts.plot_treemap(
                stocks, TREEMAP_GROUPINGS[g], UNIVERSES[u], subtitle, clip, size_cm, fontsize
            )
            paths.append(_save(fig, out / f"treemap_{u}_{g}_{period.tag}.png"))
    return paths


def all_figures(period: Period, out_dir: Path | None = None) -> list[Path]:
    """Every figure of the report."""
    paths = []
    for name, fn in [
        ("index chart", index_chart),
        ("country / sector bars", period_bars),
        ("common factor returns", common_factor_charts),
        ("NAM factor returns", nam_factor_charts),
        ("treemaps", treemaps),
    ]:
        print(f"[{name}]")
        paths += fn(period, out_dir=out_dir)
    return paths
