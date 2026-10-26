"""AI / Revision / GEMQ3 on the MSCI EM universe (same as `p-ken fret`).

Run from the repository root:
    uv run p-ken gemq3                # once, to build data/gemq/exposures/nam/gemq3
    uv run python samples/01_default.py
"""

from p_ken import fret

for ret_col in ["ret", "sret"]:  # total / specific returns
    res = fret.run(
        universe=fret.default_universe,  # ym -> data/gemq/universe/{ym}.csv
        exposures=fret.default_exposures,  # ai, rev, Gousei_3Factor at ym end
        factors=fret.DEFAULT_FACTORS,  # {output name: column}
        months=None,  # None = every month in data/gemq/rtn
        ret_col=ret_col,
        out_dir=f"data/gemq/fret/samples/01_default/{ret_col}",
    )
    print(f"=== {ret_col}")
    print(res["quintile_summary"].query("grp == 'Q5-Q1'").to_string(index=False))
    print(res["regression_summary"].to_string(index=False))
