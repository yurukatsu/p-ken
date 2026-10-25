# p-ken

GEMQ3 scores and daily factor returns (AI / Revision / GEMQ3) for MSCI EM,
ported from `get_gemq3()` and `fret_nam_monitor()` in `archive/msci_lib.R.r`.

Input data lives in `data/GEMQ` (not tracked): `unv`, `rtn`, `scores/{ai,revision,qip}`.

```sh
uv run p-ken all                          # build GEMQ3 and factor returns
uv run p-ken gemq3 --qip-rescale ratio    # choose the rescale_mean() variant
uv run p-ken fret
```

Outputs:

- `data/GEMQ/scores/gemq3/{ym}.csv` — universe with `ai`, `airev`, `Gousei_3Factor`
- `data/GEMQ/fret/quintile_daily.csv` — Q1..Q5 and Q5-Q1 excess returns (vs universe EW)
- `data/GEMQ/fret/regression_daily.csv` — daily cross-sectional OLS slope per factor
- `data/GEMQ/fret/*_summary.csv` — annualized return / risk / RR

Note: `rescale_mean()` is not defined in the R library. The candidates are in
`src/p_ken/gemq3.py` (`RESCALE_METHODS`); the default `blom_shift` is provisional.
