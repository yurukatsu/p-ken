"""Chart indices rebased to 100 at a base date, with a highlighted period.

Run from the p-ken root (needs data/index_return, see fetch_msci_index.py):

    uv run python scripts/plot_index_ytd.py
    uv run python scripts/plot_index_ytd.py --base 2026-01-01 \\
        --highlight 2026-06-01 2026-09-30 --series world em rga
    uv run python scripts/plot_index_ytd.py --series acwi em --variant close

Writes a PNG (2560x1440) and the rebased values as CSV to --out-dir
(default output/figures).
"""

import argparse
from pathlib import Path

from p_ken import index_chart


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--series",
        nargs="+",
        default=["world", "em", "rga"],
        choices=list(index_chart.SERIES),
        help="series in drawing order (first = darkest red)",
    )
    parser.add_argument("--base", default="2026-01-01", help="base date (= 100)")
    parser.add_argument(
        "--highlight",
        nargs=2,
        metavar=("START", "END"),
        default=["2026-06-01", "2026-09-30"],
        help="period drawn in full color",
    )
    parser.add_argument("--no-highlight", action="store_true")
    parser.add_argument(
        "--end", default=None, help="last date (default: highlight end)"
    )
    parser.add_argument("--variant", default="net", choices=["close", "net", "gross"])
    parser.add_argument(
        "--colors", nargs="+", default=None, help="hex colors per series"
    )
    parser.add_argument("--title", default=None)
    parser.add_argument("--out-dir", type=Path, default=Path("output/figures"))
    args = parser.parse_args()

    highlight = None if args.no_highlight else tuple(args.highlight)
    fig = index_chart.plot_rebased(
        series=args.series,
        base=args.base,
        highlight=highlight,
        end=args.end,
        variant=args.variant,
        colors=args.colors,
        title=args.title,
    )
    end = args.end or (highlight[1] if highlight else None)
    df = index_chart.rebased_frame(args.series, args.base, end, args.variant)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"index_{'_'.join(args.series)}_{args.base.replace('-', '')}"
    fig.savefig(args.out_dir / f"{stem}.png")
    df.round(4).to_csv(args.out_dir / f"{stem}.csv", index_label="date")
    print(f"Saved: {args.out_dir / stem}.png / .csv")
    print(df.iloc[[0, -1]].round(2).to_string())


if __name__ == "__main__":
    main()
