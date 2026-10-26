# p-ken

GEMQ3 scores and daily factor returns (AI / Revision / GEMQ3) for MSCI EM,
ported from `get_gemq3()` and `fret_nam_monitor()` in `archive/msci_lib.R.r`.

Input data lives in `data/gemq` (not tracked). `{ym}` is a month end:

| path | content |
|---|---|
| `universe/{ym}.csv` | MSCI EM constituents at `ym` end |
| `exposures/nam/{ai,revision,qip}/` | AI, Revision NTM (adj), QIP patents at `ym` end |
| `exposures/core/{ym}.csv` | core factors (`exposures/fc_list.csv`) |
| `rtn/{ym}.csv` | daily `ret` / `sret` (%) of the **following month** for `universe/{ym}` |

```sh
uv run p-ken all                          # build GEMQ3 and factor returns
uv run p-ken gemq3 --qip-na-strict        # reproduce R NA handling in rescale_mean()
uv run p-ken fret
```

To run factor returns with a different universe or exposures, see
[`samples/`](samples/README.md) (`p_ken.fret.run()`). `notebooks/` is for local
work and is not tracked.

Outputs:

- `data/gemq/exposures/nam/gemq3/{ym}.csv` — universe with `ai`, `airev`, `Gousei_3Factor`
- `data/gemq/fret/{ret,sret}/quintile_daily.csv` — Q1..Q5 and Q5-Q1 excess returns (vs universe EW)
- `data/gemq/fret/{ret,sret}/regression_daily.csv` — daily cross-sectional OLS slope per factor
- `data/gemq/fret/{ret,sret}/*_summary.csv` — annualized return / risk / RR

Note: `rescale_mean()` (QIP) ignores missing `invention_count_12m` when taking
the mean. The R version does not (`mean()` without `na.rm`), so one missing value
sets QIP to 0 for every stock; `--qip-na-strict` reproduces that.
