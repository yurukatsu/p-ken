"""NAM factor returns: RGA (AI, TVL, RVL, ai70_bd30) and MSCI EM (AI, Revision, GEMQ3).

Two definitions (see p_ken.nam_fret), each plotted as a cumulative sum from 0 with the highlight period in full colour,
same style as plot_common_fret.py:
  regression  daily one-factor regression slope on Blom scores
  q5          top-quintile mean excess return (em-market-weekly / R fret_nam_monitor;
              files with a _q5 suffix)
Run from the p-ken root:

    uv run python scripts/plot_nam_fret.py
    uv run python scripts/plot_nam_fret.py --returns ret --start 2026-04-01

By default both the return (ret, local currency) and the specific return (sret,
files with a _sret suffix) versions are written, ending at the highlight end.
"""

import argparse
from pathlib import Path

from p_ken import common_fret, nam_fret


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
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
        "--returns", nargs="+", choices=["ret", "sret"], default=["ret", "sret"]
    )
    parser.add_argument(
        "--methods",
        nargs="+",
        choices=["regression", "q5"],
        default=["regression", "q5"],
    )
    parser.add_argument(
        "--universes",
        nargs="+",
        choices=list(nam_fret.UNIVERSES),
        default=list(nam_fret.UNIVERSES),
        help="blf = RGA (daily scores), gemq = MSCI EM (month-end scores)",
    )
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
    args.out_dir.mkdir(parents=True, exist_ok=True)
    runs = [
        (u, m, r) for u in args.universes for m in args.methods for r in args.returns
    ]
    for u, method, ret_col in runs:
        if method == "q5":
            daily = nam_fret.q5_returns(u, args.start, end, ret_col=ret_col)
        else:
            daily = nam_fret.factor_returns(u, args.start, end, ret_col=ret_col)
        detail = ["Q5 Excess"] if method == "q5" else []
        detail += ["Specific Return"] if ret_col == "sret" else []
        fig = common_fret.plot_cumulative(
            daily,
            start=args.start,
            highlight=highlight,
            title=nam_fret.UNIVERSES[u] + (f" ({', '.join(detail)})" if detail else ""),
            ylabel="Q5 Excess Return (cumulative sum)"
            if method == "q5"
            else "Factor Return (cumulative sum)",
            colors=nam_fret.COLORS[u],
            size_cm=tuple(args.size_cm),
            fontsize=args.fontsize,
        )
        suffix = ("_q5" if method == "q5" else "") + (
            "_sret" if ret_col == "sret" else ""
        )
        stem = args.out_dir / f"nam_fret_{u}_{args.start.replace('-', '')}{suffix}"
        fig.savefig(f"{stem}.png")
        daily.to_csv(f"{stem}.csv", index_label="date")
        print(f"Saved: {stem}.png / .csv")
        print(f"  {daily.index.min():%Y-%m-%d} - {daily.index.max():%Y-%m-%d}")
        if highlight:
            period = daily.loc[highlight[0] : highlight[1]].sum()
            print(
                "  highlight sum: "
                + ", ".join(f"{k} {v:+.2%}" for k, v in period.items())
            )
        print("  total: " + ", ".join(f"{k} {v:+.2%}" for k, v in daily.sum().items()))


if __name__ == "__main__":
    main()
