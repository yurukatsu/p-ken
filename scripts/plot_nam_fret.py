"""NAM factor returns: MSCI EM (AI, Revision, GEMQ3) and RGA (AI, TVL, RVL, ai70_bd30).

    uv run python scripts/plot_nam_fret.py
    uv run python scripts/plot_nam_fret.py --universes gemq --methods regression

methods: regression = slope on Blom exposure (default), q5 = top-quintile excess.
Output: nam_fret_<universe>_<ytd_start>[_q5][_sret].png / .csv (half slide).
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
        "--methods", nargs="+", default=["regression", "q5"], choices=["regression", "q5"]
    )
    p.add_argument("--returns", nargs="+", default=["ret", "sret"], choices=["ret", "sret"])
    p.add_argument("--size-cm", nargs=2, type=float, metavar=("W", "H"))
    p.add_argument("--fontsize", type=float, default=8)
    a = p.parse_args()
    kw = {"size_cm": tuple(a.size_cm)} if a.size_cm else {}
    cli.report(
        report.nam_factor_charts(
            cli.period(a),
            tuple(a.universes),
            tuple(a.methods),
            tuple(a.returns),
            a.out_dir,
            fontsize=a.fontsize,
            **kw,
        )
    )


if __name__ == "__main__":
    main()
