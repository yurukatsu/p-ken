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

Scripts (`scripts/`):

```sh
# MSCI EM / ACWI / World daily closing levels (USD) from LSEG
# -> data/index_return/msci_{em,acwi,world}.csv
#    columns: dateymd, close, return (price), net, net_return, gross, gross_return
# Self-contained (PEP 723): uv installs lseg-data itself.
# Credentials LSEG_APP_KEY / LSEG_USERNAME / LSEG_PASSWORD from env or --env-file (default .env)
uv run scripts/fetch_msci_index.py [--start 1999-01-01] [--end YYYY-MM-DD] [--indices EM ACWI World] [--env-file ../datastream/.env]

# EM country indices (16; Korea = KOSPI) and MSCI EM sectors (price; --sector-variant net)
# in USD from LSEG -> data/index_return/{country,em_sector}_{close,return}_usd.csv
uv run scripts/fetch_em_markets.py [--start 1999-01-01] [--groups country em_sector] [--env-file ../datastream/.env]

# Index chart rebased to 100 at --base, --highlight period drawn darker (red shades),
# sized for the upper half of a template slide (24.8 x 7.4 cm, 300 dpi; --size-cm to change).
# MSCI = price index by default (--variant net/gross for total return); labels show the
# highlight-period return (plus blue / minus red) above or below each line end
# -> output/figures/index_<series>_<base>.png / .csv  (library: p_ken.index_chart.plot_rebased)
uv run python scripts/plot_index_ytd.py --base 2026-01-01 --highlight 2026-07-01 2026-09-30 --series world em rga
```

Outputs:

- `data/gemq/exposures/nam/gemq3/{ym}.csv` — universe with `ai`, `airev`, `Gousei_3Factor`
- `data/gemq/fret/{ret,sret}/quintile_daily.csv` — Q1..Q5 and Q5-Q1 excess returns (vs universe EW)
- `data/gemq/fret/{ret,sret}/regression_daily.csv` — daily cross-sectional OLS slope per factor
- `data/gemq/fret/{ret,sret}/*_summary.csv` — annualized return / risk / RR

Note: `rescale_mean()` (QIP) ignores missing `invention_count_12m` when taking
the mean. The R version does not (`mean()` without `na.rm`), so one missing value
sets QIP to 0 for every stock; `--qip-na-strict` reproduces that.
