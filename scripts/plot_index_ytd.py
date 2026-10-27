"""Index line chart: MSCI World / EM / RGA rebased to 100, the quarter highlighted.

    uv run python scripts/plot_index_ytd.py
    uv run python scripts/plot_index_ytd.py --series acwi em --variant close

Output: index_<series>_<ytd_start>.png / .csv (24.8 x 7.4 cm = half slide).
"""

from p_ken import cli, markets, report


def main() -> None:
    p = cli.parser(__doc__.split("\n")[0])
    p.add_argument(
        "--series",
        nargs="+",
        default=["world", "em", "rga"],
        choices=list(markets.INDEX_SERIES),
        help="drawing order = dark -> light red",
    )
    p.add_argument(
        "--variant",
        default="net",
        choices=list(markets.VARIANT_LABEL),
        help="MSCI series: net (default) / gross = total return, close = price index",
    )
    p.add_argument("--size-cm", nargs=2, type=float, metavar=("W", "H"))
    p.add_argument("--fontsize", type=float, default=9)
    a = p.parse_args()
    kw = {"size_cm": tuple(a.size_cm)} if a.size_cm else {}
    cli.report(
        report.index_chart(
            cli.period(a), tuple(a.series), a.variant, a.out_dir, fontsize=a.fontsize, **kw
        )
    )


if __name__ == "__main__":
    main()
