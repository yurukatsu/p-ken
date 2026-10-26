"""Bar charts of country / MSCI EM sector returns over a period (USD).

Bar = cumulative return over the period; markers = cumulative returns at each
month end inside it (e.g. 7/31, 8/31 for Jul-Sep). Run from the p-ken root
(needs data/index_return from fetch_em_markets.py and fetch_msci_index.py):

    uv run python scripts/plot_period_returns.py
    uv run python scripts/plot_period_returns.py --groups country --start 2026-04-01 --end 2026-06-30

Each PNG is rendered at its size on the slide (default 12.2 x 7.4 cm: a
quarter of the 4:3 template slide, upper left / upper right; 300 dpi), so paste
it unscaled. Also writes the cumulative returns as CSV to --out-dir.
"""

import argparse
from pathlib import Path

from p_ken import return_bars


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--groups",
        nargs="+",
        choices=list(return_bars.GROUP_FILES),
        default=list(return_bars.GROUP_FILES),
    )
    parser.add_argument("--start", default="2026-07-01", help="first day of the period")
    parser.add_argument("--end", default="2026-09-30", help="last day of the period")
    parser.add_argument(
        "--checkpoints",
        nargs="*",
        default=None,
        help="marker dates (default: month ends)",
    )
    parser.add_argument(
        "--no-benchmark", action="store_true", help="drop the MSCI EM row"
    )
    parser.add_argument(
        "--size-cm",
        nargs=2,
        type=float,
        metavar=("W", "H"),
        default=list(return_bars.SLIDE_QUARTER_CM),
    )
    parser.add_argument("--fontsize", type=float, default=7, help="pt on the slide")
    parser.add_argument("--out-dir", type=Path, default=Path("output/figures"))
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    period = f"{args.start.replace('-', '')}_{args.end.replace('-', '')}"
    for group in args.groups:
        fig, table = return_bars.plot_period_bars(
            group,
            args.start,
            args.end,
            checkpoints=args.checkpoints,
            benchmark=not args.no_benchmark,
            size_cm=tuple(args.size_cm),
            fontsize=args.fontsize,
        )
        stem = args.out_dir / f"period_returns_{group}_{period}"
        fig.savefig(f"{stem}.png")
        table.round(6).to_csv(f"{stem}.csv", index_label="market")
        print(f"Saved: {stem}.png / .csv")
        print(table.map("{:+.1%}".format).to_string())


if __name__ == "__main__":
    main()
