"""Common (core) factor returns by factor type, MSCI EM and RGA universes.

    uv run python scripts/plot_common_fret.py
    uv run python scripts/plot_common_fret.py --universes blf --returns ret

Output: common_fret_<universe>_<ytd_start>[_sret].png, _factors.csv, _types.csv
(24.8 x 7.4 cm = half slide).
"""

from p_ken import cli, config, report


def main() -> None:
    p = cli.parser(__doc__.split("\n")[0])
    p.add_argument(
        "--universes",
        nargs="+",
        default=list(config.UNIVERSES),
        choices=list(config.UNIVERSES),
        help="gemq = MSCI EM, blf = RGA",
    )
    p.add_argument(
        "--returns",
        nargs="+",
        default=["ret", "sret"],
        choices=["ret", "sret"],
        help="ret = local-currency return, sret = specific return",
    )
    p.add_argument("--size-cm", nargs=2, type=float, metavar=("W", "H"))
    p.add_argument("--fontsize", type=float, default=8)
    a = p.parse_args()
    kw = {"size_cm": tuple(a.size_cm)} if a.size_cm else {}
    cli.report(
        report.common_factor_charts(
            cli.period(a),
            tuple(a.universes),
            tuple(a.returns),
            a.out_dir,
            fontsize=a.fontsize,
            **kw,
        )
    )


if __name__ == "__main__":
    main()
