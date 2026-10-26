"""Treemaps of MSCI EM / RGA stocks: area = weight, colour = period return (USD).

Needs data/index_return/stocks_<universe>_<start>_<end>.csv from
scripts/fetch_stock_returns.py (weights + LSEG returns). Run from the p-ken root:

    uv run scripts/fetch_stock_returns.py          # once (LSEG)
    uv run python scripts/plot_treemap.py
    uv run python scripts/plot_treemap.py --group sector --clip 0.3

Each PNG is rendered at its size on the slide (default 24.8 x 15.0 cm: a whole
content slide of the 4:3 template; 300 dpi), so paste it unscaled.
"""

import argparse
from pathlib import Path

import pandas as pd

from p_ken import treemap

TITLES = {"gemq": "MSCI EM Universe", "blf": "RGA Universe"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--universes", nargs="+", choices=list(TITLES), default=list(TITLES)
    )
    parser.add_argument("--start", default="2026-07-01")
    parser.add_argument("--end", default="2026-09-30")
    parser.add_argument("--group", choices=["country", "sector"], default="country")
    parser.add_argument(
        "--clip", type=float, default=0.2, help="colour saturates at +-clip"
    )
    parser.add_argument(
        "--size-cm",
        nargs=2,
        type=float,
        metavar=("W", "H"),
        default=list(treemap.SLIDE_FULL_CM),
    )
    parser.add_argument("--fontsize", type=float, default=8, help="pt on the slide")
    parser.add_argument("--out-dir", type=Path, default=Path("output/figures"))
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    base = pd.Timestamp(args.start) - pd.Timedelta(days=1)
    end = pd.Timestamp(args.end)
    for u in args.universes:
        stocks = treemap.load_stocks(u, args.start, args.end)
        base_date = pd.to_datetime(stocks["base_date"]).min()
        subtitle = (
            f"Size = weight ({end:%-m/%-d}), Colour = return "
            f"{(base_date if pd.notna(base_date) else base):%-m/%-d}–{end:%-m/%-d} (USD)"
        )
        fig = treemap.plot_treemap(
            stocks,
            args.group,
            title=TITLES[u],
            subtitle=subtitle,
            clip=args.clip,
            size_cm=tuple(args.size_cm),
            fontsize=args.fontsize,
        )
        period = f"{args.start.replace('-', '')}_{args.end.replace('-', '')}"
        path = args.out_dir / f"treemap_{u}_{args.group}_{period}.png"
        fig.savefig(path)
        print(f"Saved: {path}")


if __name__ == "__main__":
    main()
