"""AI / Revision / GEMQ3 on the MSCI EM universe (same as `p-ken fret`).

Run from the repository root:
    uv run p-ken gemq3                # once, to build data/GEMQ/scores/gemq3
    uv run python samples/01_default.py
"""

from p_ken import fret

res = fret.run(
    universe=fret.default_universe,  # exp_ym -> data/GEMQ/unv/{exp_ym}.csv
    exposures=fret.default_exposures,  # ai, rev, Gousei_3Factor
    factors=fret.DEFAULT_FACTORS,  # {output name: column}
    months=None,  # None = every month in data/GEMQ/rtn
    out_dir="data/GEMQ/fret/samples/01_default",
)

print(res["quintile_summary"].query("grp == 'Q5-Q1'").to_string(index=False))
print(res["regression_summary"].to_string(index=False))
