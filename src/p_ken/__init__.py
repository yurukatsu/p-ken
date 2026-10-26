import argparse

import pandas as pd


def main() -> None:
    from p_ken import fret, gemq3

    parser = argparse.ArgumentParser(prog="p-ken")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_g = sub.add_parser("gemq3", help="build GEMQ3 scores -> data/GEMQ/scores/gemq3")
    p_a = sub.add_parser("all", help="gemq3 then fret")
    for p in (p_g, p_a):
        p.add_argument(
            "--qip-na-strict",
            action="store_true",
            help="reproduce R: any missing QIP value sets QIP to 0 for all stocks",
        )
    sub.add_parser("fret", help="daily factor returns -> data/GEMQ/fret")
    args = parser.parse_args()

    if args.cmd in ("gemq3", "all"):
        yms = gemq3.build_all(qip_na_rm=not args.qip_na_strict)
        print(f"GEMQ3: {len(yms)} months {yms[0]}-{yms[-1]}")
    if args.cmd in ("fret", "all"):
        res = fret.run_all()
        with pd.option_context("display.width", 200, "display.precision", 4):
            print(res["quintile_summary"].to_string(index=False))
            print(res["regression_summary"].to_string(index=False))
