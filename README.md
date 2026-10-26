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

# EM country indices (15; Korea = KOSPI, no Poland) and MSCI EM sectors (price; --sector-variant net)
# in USD from LSEG -> data/index_return/{country,em_sector}_{close,return}_usd.csv
uv run scripts/fetch_em_markets.py [--start 1999-01-01] [--groups country em_sector] [--env-file ../datastream/.env]

# Index chart rebased to 100 at --base, --highlight period drawn darker (red shades),
# sized for the upper half of a template slide (24.8 x 7.4 cm, 300 dpi; --size-cm to change).
# MSCI = price index by default (--variant net/gross for total return); labels show the
# highlight-period return (plus blue / minus red) above or below each line end
# -> output/figures/index_<series>_<base>.png / .csv  (library: p_ken.index_chart.plot_rebased)
uv run python scripts/plot_index_ytd.py --base 2026-01-01 --highlight 2026-07-01 2026-09-30 --series world em rga

# Period return bars for countries / MSCI EM sectors (USD): bar = start -> end,
# markers = month-end cumulative returns; quarter-slide size (12.2 x 7.4 cm)
# -> output/figures/period_returns_<group>_<start>_<end>.png / .csv  (library: p_ken.return_bars)
uv run python scripts/plot_period_returns.py --start 2026-07-01 --end 2026-09-30

# Common factor returns by fc_list type (core exposures, daily one-factor regression on
# Blom scores, type = mean of its factors) for MSCI EM (data/gemq) and RGA (data/blf):
# cumulative sum from 0, highlight period in full colour  (library: p_ken.common_fret)
# -> output/figures/common_fret_<universe>_<start>.png / _factors.csv / _types.csv
uv run python scripts/plot_common_fret.py --start 2026-01-01 --highlight 2026-07-01 2026-09-30  # ret and sret (_sret)

# NAM factor returns, same method / chart style:
#   RGA (data/blf): AI, TVL, RVL, ai70_bd30 from the daily score files (latest before each date)
#   MSCI EM (data/gemq): AI, Revision, GEMQ3 from the month-end files (paired with rtn/{ym})
#   two definitions (--methods): regression slope, and q5 = top-quintile mean excess return
#   (RGA: archive BLF.fret_nam_daily, CN=False; MSCI EM: R fret_nam_monitor)
# -> output/figures/nam_fret_{blf,gemq}_<start>[_q5][_sret].png / .csv  (library: p_ken.nam_fret)
uv run python scripts/plot_nam_fret.py --start 2026-01-01 --highlight 2026-07-01 2026-09-30

# Stock treemaps (MSCI EM / RGA): area = 9/30 weight, colour = USD return 6/30-9/30 from LSEG
# (SEDOL -> RIC / HQ country / GICS sector, TR.PriceClose(Curn=USD); as in ../datastream)
uv run scripts/fetch_stock_returns.py [--start 2026-07-01 --end 2026-09-30] [--env-file ../datastream/.env]
uv run python scripts/plot_treemap.py [--group country|sector] [--clip 0.2]
# -> data/index_return/stocks_<universe>_<start>_<end>.csv, output/figures/treemap_<universe>_<group>_<period>.png
```

Outputs:

- `data/gemq/exposures/nam/gemq3/{ym}.csv` — universe with `ai`, `airev`, `Gousei_3Factor`
- `data/gemq/fret/{ret,sret}/quintile_daily.csv` — Q1..Q5 and Q5-Q1 excess returns (vs universe EW)
- `data/gemq/fret/{ret,sret}/regression_daily.csv` — daily cross-sectional OLS slope per factor
- `data/gemq/fret/{ret,sret}/*_summary.csv` — annualized return / risk / RR

Note: `rescale_mean()` (QIP) ignores missing `invention_count_12m` when taking
the mean. The R version does not (`mean()` without `na.rm`), so one missing value
sets QIP to 0 for every stock; `--qip-na-strict` reproduces that.
