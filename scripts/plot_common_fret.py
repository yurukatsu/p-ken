"""Common factor returns by factor type for the MSCI EM and RGA universes.

Daily one-factor regression slopes on core exposures (see p_ken.common_fret),
averaged by the type in exposures/fc_list.csv, plotted as a cumulative sum from
0 with the highlight period drawn in full colour. Run from the p-ken root:

    uv run python scripts/plot_common_fret.py
    uv run python scripts/plot_common_fret.py --universes blf --start 2026-04-01

Each PNG is rendered at its size on the slide (default 24.8 x 7.4 cm, half of a
4:3 template slide; 300 dpi). Also writes the daily factor and type returns as CSV.
"""

import argparse
from pathlib import Path

from p_ken import common_fret


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--universes",
        nargs="+",
        choices=list(common_fret.UNIVERSES),
        default=list(common_fret.UNIVERSES),
        help="gemq = MSCI EM, blf = RGA",
    )
    parser.add_argument(
        "--start", default="2026-01-01", help="cumulative sum starts at 0 here"
    )
    parser.add_argument(
        "--end",
        default=None,
        help="last date (default: highlight end, else latest data)",
    )
    parser.add_argument(
        "--highlight",
        nargs=2,
        metavar=("START", "END"),
        default=["2026-07-01", "2026-09-30"],
    )
    parser.add_argument("--no-highlight", action="store_true")
    parser.add_argument(
        "--size-cm",
        nargs=2,
        type=float,
        metavar=("W", "H"),
        default=list(common_fret.SLIDE_UPPER_HALF_CM),
    )
    parser.add_argument("--fontsize", type=float, default=8, help="pt on the slide")
    parser.add_argument("--out-dir", type=Path, default=Path("output/figures"))
    args = parser.parse_args()

    highlight = None if args.no_highlight else tuple(args.highlight)
    end = args.end or (highlight[1] if highlight else None)
    # same colour for the same type in every chart
    all_types = {}
    for u in common_fret.UNIVERSES:
        all_types.update(dict.fromkeys(common_fret.factor_list(u).type))
    all_types.pop("Seasonality", None)  # not in the core files
    colors = common_fret.type_colors(list(all_types))

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for u in args.universes:
        daily = common_fret.factor_returns(u, args.start, end)
        by_type = common_fret.type_returns(daily, u)
        fig = common_fret.plot_cumulative(
            by_type,
            start=args.start,
            highlight=highlight,
            title=common_fret.UNIVERSES[u],
            colors=colors,
            size_cm=tuple(args.size_cm),
            fontsize=args.fontsize,
        )
        stem = args.out_dir / f"common_fret_{u}_{args.start.replace('-', '')}"
        fig.savefig(f"{stem}.png")
        daily.to_csv(f"{stem}_factors.csv", index_label="date")
        by_type.to_csv(f"{stem}_types.csv", index_label="date")
        print(f"Saved: {stem}.png / _factors.csv / _types.csv")
        print(
            f"  {daily.index.min():%Y-%m-%d} - {daily.index.max():%Y-%m-%d}, {daily.shape[1]} factors"
        )
        if highlight:
            period = by_type.loc[highlight[0] : highlight[1]].sum()
            print(
                "  highlight sum: "
                + ", ".join(f"{k} {v:+.2%}" for k, v in period.items())
            )


if __name__ == "__main__":
    main()
