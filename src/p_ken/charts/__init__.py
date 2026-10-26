"""Slide-sized charts. Data preparation lives in p_ken.markets / p_ken.factors."""

from p_ken.charts.cumulative import category_colors, plot_cumulative
from p_ken.charts.index_line import plot_rebased
from p_ken.charts.period_bars import plot_period_bars
from p_ken.charts.style import SLIDE_FULL_CM, SLIDE_HALF_CM, SLIDE_QUARTER_CM
from p_ken.charts.treemap import plot_treemap

__all__ = [
    "SLIDE_FULL_CM",
    "SLIDE_HALF_CM",
    "SLIDE_QUARTER_CM",
    "category_colors",
    "plot_cumulative",
    "plot_period_bars",
    "plot_rebased",
    "plot_treemap",
]
