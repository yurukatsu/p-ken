import argparse

import pandas as pd


def main() -> None:
    from p_ken import fret, gemq3

    parser = argparse.ArgumentParser(prog="p-ken")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_g = sub.add_parser("gemq3", help="build GEMQ3 scores -> data/GEMQ/scores/gemq3")
    p_g.add_argument(
        "--qip-rescale",
        choices=sorted(gemq3.RESCALE_METHODS),
        default=gemq3.DEFAULT_QIP_RESCALE,
        help="implementation of rescale_mean() used for QIP",
    )
    sub.add_parser("fret", help="daily factor returns -> data/GEMQ/fret")
    p_a = sub.add_parser("all", help="gemq3 then fret")
    p_a.add_argument(
        "--qip-rescale",
        choices=sorted(gemq3.RESCALE_METHODS),
        default=gemq3.DEFAULT_QIP_RESCALE,
    )
    args = parser.parse_args()

    if args.cmd in ("gemq3", "all"):
        yms = gemq3.build_all(args.qip_rescale)
        print(f"GEMQ3 ({args.qip_rescale}): {len(yms)} months {yms[0]}-{yms[-1]}")
    if args.cmd in ("fret", "all"):
        res = fret.run_all()
        with pd.option_context("display.width", 200, "display.precision", 4):
            print(res["quintile_summary"].to_string(index=False))
            print(res["regression_summary"].to_string(index=False))
