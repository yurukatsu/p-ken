"""Every report figure for the period in config/report.toml (or the options).

    uv run python scripts/make_figures.py
    uv run python scripts/make_figures.py --start 2026-10-01 --end 2026-12-31

Prerequisites: data/index_return from scripts/fetch_lseg.py, GEMQ3 from
scripts/build_gemq3.py. See docs/manual.md.
"""

from p_ken import cli, report


def main() -> None:
    a = cli.parser(__doc__.split("\n")[0]).parse_args()
    period = cli.period(a)
    print(f"period: YTD from {period.ytd_start}, highlight {period.start} - {period.end}")
    paths = report.all_figures(period, a.out_dir)
    print(f"{len(paths)} files written")


if __name__ == "__main__":
    main()
