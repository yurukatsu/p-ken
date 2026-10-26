"""Stock treemaps: area = weight at the period end, colour = quarter USD return (LSEG).

Needs data/index_return/stocks_<universe>_<start>_<end>.csv (fetch_lseg.py stocks).

    uv run python scripts/plot_treemap.py
    uv run python scripts/plot_treemap.py --groupings sector --clip 0.3

Output: treemap_<universe>_{country,sector,country_sector}_<start>_<end>.png
(24.8 x 15.0 cm = whole slide).
"""

from p_ken import cli, config, report


def main() -> None:
    p = cli.parser(__doc__.split("\n")[0])
    p.add_argument(
        "--universes", nargs="+", default=list(config.UNIVERSES), choices=list(config.UNIVERSES)
    )
    p.add_argument(
        "--groupings",
        nargs="+",
        default=list(report.TREEMAP_GROUPINGS),
        choices=list(report.TREEMAP_GROUPINGS),
    )
    p.add_argument("--clip", type=float, default=0.2, help="colour saturates at +-clip")
    p.add_argument("--size-cm", nargs=2, type=float, metavar=("W", "H"))
    p.add_argument("--fontsize", type=float, default=8)
    a = p.parse_args()
    kw = {"size_cm": tuple(a.size_cm)} if a.size_cm else {}
    cli.report(
        report.treemaps(
            cli.period(a),
            tuple(a.universes),
            tuple(a.groupings),
            a.clip,
            a.out_dir,
            fontsize=a.fontsize,
            **kw,
        )
    )


if __name__ == "__main__":
    main()
