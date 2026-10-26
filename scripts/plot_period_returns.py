"""Country / MSCI EM sector bars: quarter USD return, markers at month ends.

    uv run python scripts/plot_period_returns.py
    uv run python scripts/plot_period_returns.py --groups country --checkpoints 2026-08-15

Output: period_returns_{country,em_sector}_<start>_<end>.png / .csv
(12.2 x 7.4 cm = quarter slide).
"""

from p_ken import cli, markets, report


def main() -> None:
    p = cli.parser(__doc__.split("\n")[0])
    p.add_argument(
        "--groups",
        nargs="+",
        default=list(markets.MARKET_GROUPS),
        choices=list(markets.MARKET_GROUPS),
    )
    p.add_argument("--checkpoints", nargs="*", help="marker dates (default: month ends)")
    p.add_argument("--no-benchmark", action="store_true", help="drop the MSCI EM row")
    p.add_argument("--size-cm", nargs=2, type=float, metavar=("W", "H"))
    p.add_argument("--fontsize", type=float, default=7)
    a = p.parse_args()
    kw = {"size_cm": tuple(a.size_cm)} if a.size_cm else {}
    cli.report(
        report.period_bars(
            cli.period(a),
            tuple(a.groups),
            a.checkpoints,
            not a.no_benchmark,
            a.out_dir,
            fontsize=a.fontsize,
            **kw,
        )
    )


if __name__ == "__main__":
    main()
