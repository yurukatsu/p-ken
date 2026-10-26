"""Build GEMQ3 scores for every month -> data/gemq/exposures/nam/gemq3/{ym}.csv.

    uv run python scripts/build_gemq3.py
    uv run python scripts/build_gemq3.py --qip-na-strict   # reproduce R NA handling

Run again whenever new month-end AI / Revision / QIP files arrive (the NAM
factor returns for MSCI EM read these files).
"""

import argparse

from p_ken import gemq3


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument(
        "--qip-na-strict",
        action="store_true",
        help="reproduce R rescale_mean(): any missing QIP value sets QIP to 0 for all stocks",
    )
    args = p.parse_args()
    yms = gemq3.build_all(qip_na_rm=not args.qip_na_strict)
    print(f"GEMQ3: {len(yms)} months {yms[0]}-{yms[-1]} -> data/gemq/exposures/nam/gemq3/")


if __name__ == "__main__":
    main()
