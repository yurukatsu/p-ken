# p-ken マニュアル

新興国株式の四半期レビュー資料（`output/template/新興国市場_P検.pptx`）に貼る図を作るためのツールです。
データの取得から図の出力までをコマンドで行います。計算方法の詳細は [methodology.md](methodology.md) にあります。

## 目次

1. [できること](#1-できること)
2. [セットアップ](#2-セットアップ)
3. [四半期ごとの作業手順](#3-四半期ごとの作業手順)
4. [図ごとの説明](#4-図ごとの説明)
5. [スライドへの貼り付け位置](#5-スライドへの貼り付け位置)
6. [データの置き場所と形式](#6-データの置き場所と形式)
7. [Python から使う](#7-python-から使う)
8. [困ったとき](#8-困ったとき)
9. [開発者向け](#9-開発者向け)

---

## 1. できること

| 図 | スクリプト | スライド | サイズ |
|---|---|---|---|
| 指数の推移（MSCI World / EM / RGA、年初来、四半期を強調） | `plot_index_ytd.py` | 2 上半分 | 24.8 × 7.4 cm |
| 国別・MSCI EM セクター別の四半期リターン（月末の推移つき） | `plot_period_returns.py` | 3 左上・右上 | 12.2 × 7.4 cm |
| コモンファクターリターン（ファクタータイプ別、MSCI EM / RGA） | `plot_common_fret.py` | 4 上下 | 24.8 × 7.4 cm |
| NAM ファクターリターン（RGA：AI・TVL・RVL・合成、MSCI EM：AI・Revision・GEMQ3） | `plot_nam_fret.py` | 5・6 | 24.8 × 7.4 cm |
| 銘柄ツリーマップ（国別・セクター別・国×セクター、MSCI EM / RGA） | `plot_treemap.py` | 1 枚ずつ | 24.8 × 15.0 cm |

`scripts/make_figures.py` で全部を一度に作れます。図は **スライドに貼る大きさそのもの** で出力するので、PowerPoint では拡大・縮小せずに貼ってください（文字の大きさがスライド上の pt になります）。

各図と一緒に、図に描いた数値の CSV も出力します（スライドの本文に数字を書くときに使えます）。

## 2. セットアップ

### 必要なもの

- [uv](https://docs.astral.sh/uv/)（Python 3.13 は uv が用意します）
- LSEG Data Platform のアカウント（指数・国別・銘柄リターンの取得に使用）
- 日本語フォント（macOS ならヒラギノが自動で使われます）

### インストール

```sh
cd p-ken
uv sync
```

### LSEG の認証情報

リポジトリ直下に `.env` を作ります（git では追跡されません）。

```sh
LSEG_APP_KEY=...
LSEG_USERNAME=...
LSEG_PASSWORD=...
```

`../datastream/.env` をそのまま使う場合は、取得時に `--env-file ../datastream/.env` を付けます。

### フォルダ構成

```
p-ken/
├── config/report.toml     レポートの期間（四半期ごとに更新）
├── data/                  入力データ（git 管理外。§6）
├── output/
│   ├── figures/           出力した図と CSV（git 管理外）
│   └── template/          PowerPoint テンプレート（git 管理外）
├── scripts/               実行するスクリプト
├── src/p_ken/             計算・作図のライブラリ
├── samples/               使い方の例（実行済みノートブック）
├── notebooks/             手元での分析用（git 管理外）
├── docs/                  このマニュアルと計算方法
└── tests/                 テスト
```

## 3. 四半期ごとの作業手順

例：2026 年 10〜12 月を報告する場合。

### ① データを置く

受け取ったデータ（zip など）を展開し、`data/gemq`（MSCI EM）と `data/blf`（RGA）を差し替えます。必要なファイルは §6 を参照してください。最低限、次がそろっている必要があります。

- 期末月の `universe/{ym}.csv`（例：`202612.csv`）
- 期間のリターンを含む `rtn/{ym}.csv`（`rtn/202609.csv` = 10 月分、… `rtn/202611.csv` = 12 月分）
- エクスポージャー（`exposures/core`、MSCI EM の `exposures/nam/{ai,revision,qip}`、RGA の日次スコア）

### ② 期間を設定する

`config/report.toml` の日付を書き換えます。すべてのスクリプトがここを読みます。

```toml
[period]
ytd_start = "2026-01-01"  # 年初来の図の起点（指数 = 100、ファクターの累和 = 0）
start = "2026-10-01"      # 強調する期間（四半期）の初日
end = "2026-12-31"        # 強調する期間の最終日（= レポート基準日）
```

### ③ GEMQ3 を作る

MSCI EM の NAM ファクターで使う GEMQ3 スコアを、月末ごとに作ります。新しい月のデータが入ったら毎回実行します。

```sh
uv run python scripts/build_gemq3.py
```

### ④ LSEG から市場データを取る

```sh
uv run scripts/fetch_lseg.py all
# 認証情報を datastream から使う場合
uv run scripts/fetch_lseg.py --env-file ../datastream/.env all
```

`all` は次の 3 つを順に行います（個別にも実行できます）。

| サブコマンド | 内容 | 時間の目安 |
|---|---|---|
| `indices` | MSCI EM / ACWI / World の指数（価格・ネット・グロス） | 数十秒 |
| `markets` | 新興国 15 か国の指数と MSCI EM セクター指数（USD） | 1〜2 分 |
| `stocks` | 期末のユニバース銘柄のウェイトと四半期の USD リターン | 2 分 |

`fetch_lseg.py` は他のスクリプトと違い、`uv run scripts/...` で実行します（必要なライブラリを uv が別環境に入れます）。

RGA 指数（`data/index_return/rga.csv`）は LSEG からは取らないので、別途最新のものを置いてください。

### ⑤ 図を作る

```sh
uv run python scripts/make_figures.py
```

`output/figures/` に図（PNG）と CSV が出力されます（全部で約 1〜2 分）。図ごとに作り直すときは §4 のスクリプトを使います。

### ⑥ スライドに貼る

§5 の位置とサイズで、拡大・縮小せずに貼ります。

### ⑦（任意）チェック

```sh
uv run pytest
```

計算部分のテストと、実データでの既知の値の確認を行います。

## 4. 図ごとの説明

すべてのスクリプトで、期間は `config/report.toml` から読みます。コマンドで一時的に変えることもできます。

| 共通オプション | 意味 |
|---|---|
| `--ytd-start` / `--start` / `--end` | 期間（`YYYY-MM-DD`）。省略時は `config/report.toml` |
| `--out-dir` | 出力先。省略時は `output/figures` |
| `--size-cm W H` | 図の大きさ（cm）。別の位置に貼るとき |
| `--fontsize` | 文字の大きさ（スライド上の pt） |

ファイル名の `<ytd>` は `ytd_start`（例 `20260101`）、`<period>` は `start_end`（例 `20260701_20260930`）です。

### 4.1 指数の推移

```sh
uv run python scripts/plot_index_ytd.py
uv run python scripts/plot_index_ytd.py --variant close   # 価格指数
uv run python scripts/plot_index_ytd.py --series acwi em   # 指数を変える
```

- MSCI World・MSCI EM・RGA を `ytd_start` = 100 に指数化。四半期は濃い色、それ以外は薄い色。
- 線の右端に略称（MSCIWO / MSCIEM / RGA）と **四半期のリターン**（プラス青・マイナス赤）を、線と重ならない上下の位置に表示します。
- MSCI は配当込みのネット・トータルリターン（RGA に合わせる）。`--variant gross` でグロス、`close` で価格指数（y 軸のタイトルも変わります）。
- 出力：`index_world_em_rga_<ytd>.png` / `.csv`（指数化した値）

### 4.2 国別・セクター別の四半期リターン

```sh
uv run python scripts/plot_period_returns.py
uv run python scripts/plot_period_returns.py --checkpoints 2026-11-15   # マーカーの日を指定
```

- 棒：四半期の USD 建てリターン（前四半期末の終値 → 期末）。マーカー：各月末時点の累積リターン（○ 1 か月目、◆ 2 か月目）。
- MSCI EM を灰色の行で比較用に入れています（`--no-benchmark` で外す）。
- 国は datastream の `universe.yaml` に準拠（韓国は KOSPI、ポーランドは除外）。
- 出力：`period_returns_{country,em_sector}_<period>.png` / `.csv`

### 4.3 コモンファクターリターン

```sh
uv run python scripts/plot_common_fret.py
uv run python scripts/plot_common_fret.py --universes blf --returns ret
```

- core エクスポージャー（約 100 ファクター）の日次ファクターリターンを、fc_list のタイプごとに平均し、`ytd_start` からの累和を描きます。
- 右の数値は四半期の合計（プラス青・マイナス赤）。同じタイプは 2 つの図で同じ色です。
- `ret`（現地通貨建て）と `sret`（スペシフィックリターン）の両方を出力します。
- 出力：`common_fret_<universe>_<ytd>[_sret].png`、`..._factors.csv`（ファクター別の日次）、`..._types.csv`（タイプ別の日次）

### 4.4 NAM ファクターリターン

```sh
uv run python scripts/plot_nam_fret.py
uv run python scripts/plot_nam_fret.py --universes gemq --methods regression --returns ret
```

- MSCI EM：AI・Revision・GEMQ3（前月末のスコア）。RGA：AI・TVL・RVL・合成（ai70_bd30）（前日までの日次スコア）。
- `regression`（デフォルト、回帰の傾き）と `q5`（上位 20% の超過リターン、em-market-weekly 互換）の 2 種類 × `ret` / `sret`。
- 合成スコア（GEMQ3、ai70_bd30）は黒、AI は青で、図をまたいで色をそろえています。
- 出力：`nam_fret_<universe>_<ytd>[_q5][_sret].png` / `.csv`

### 4.5 銘柄ツリーマップ

```sh
uv run python scripts/plot_treemap.py
uv run python scripts/plot_treemap.py --groupings sector --clip 0.3
```

- セルの面積 = 期末のウェイト、色 = 四半期の USD 建てリターン（青がプラス、赤がマイナス、±20% で色が飽和。`--clip` で変更）。
- 国（LSEG の本社所在国）、GICS セクター、国 × セクターの 3 種類。見出しはウェイト加重リターンと合計ウェイト。
- 事前に `fetch_lseg.py stocks` が必要です。
- 国は本社所在国なので、本社が米国の EM 企業（AngloGold Ashanti など）は「USA」に入ります。
- 出力：`treemap_<universe>_{country,sector,country_sector}_<period>.png`

## 5. スライドへの貼り付け位置

テンプレートはスライド 27.52 × 19.05 cm（4:3）です。タイトルの下 2.8 cm から、ページ番号の手前（約 17.8 cm）までを使います。

| 図 | 左 | 上 | 幅 × 高さ |
|---|---|---|---|
| 上半分（指数の推移、ファクターリターン） | 1.36 | 2.8 | 24.8 × 7.4 |
| 下半分（ファクターリターン 2 枚目） | 1.36 | 10.4 | 24.8 × 7.4 |
| 左上（国別） | 1.36 | 2.8 | 12.2 × 7.4 |
| 右上（セクター別） | 13.96 | 2.8 | 12.2 × 7.4 |
| 全面（ツリーマップ） | 1.36 | 2.8 | 24.8 × 15.0 |

PowerPoint では「図の形式 → サイズ」で倍率が 100% になっていることを確認してください。

## 6. データの置き場所と形式

### ユニバースごと（`data/gemq` = MSCI EM、`data/blf` = RGA）

`{ym}` は月末の年月（`YYYYMM`）です。

| パス | 内容 |
|---|---|
| `universe/{ym}.csv` | 月末の構成銘柄。`bid`, `sedol`, `weight` など |
| `rtn/{ym}.csv` | **翌月** の日次リターン（%）。`universe/{ym}` の銘柄。列 `dateym`（日付 `YYYYMMDD`）, `bid`, `ret`（現地通貨建てトータル）, `sret`（スペシフィック） |
| `exposures/core/{ym}.csv` | core ファクター（−999999998 は欠損） |
| `exposures/fc_list.csv` | core ファクターのタイプ（`variable`, `type`） |

`rtn/{ym}` が **翌月** のリターンである点が重要です（例：`rtn/202606.csv` = 2026 年 7 月）。

MSCI EM のみ：

| パス | 内容 |
|---|---|
| `exposures/nam/ai/{ym}.csv` | AI スコア（月末） |
| `exposures/nam/revision/{ym}.csv` | Revision（月末） |
| `exposures/nam/qip/msci_em_{ym}.dat` | QIP（特許）（月末、タブ区切り） |
| `exposures/nam/gemq3/{ym}.csv` | GEMQ3（`build_gemq3.py` が作成） |

RGA のみ：

| パス | 内容 |
|---|---|
| `exposures/nam/ai/{YYYYMMDD}.csv` | 日次の AI スコア（`ai`, `ai70_bd30` など） |
| `exposures/nam/bigdata/{YYYYMMDD}.csv` | 日次の bigdata スコア（`tvl`, `rvl` など） |

### 市場データ（`data/index_return`）

| ファイル | 作成元 |
|---|---|
| `msci_{em,acwi,world}.csv` | `fetch_lseg.py indices` |
| `{country,em_sector}_{close,return}_usd.csv` | `fetch_lseg.py markets` |
| `stocks_{gemq,blf}_<period>.csv` | `fetch_lseg.py stocks` |
| `rga.csv` | 別途（`dateymd`, `close`, `return`） |

## 7. Python から使う

ノートブックや自分のスクリプトから、計算部分を直接使えます。例は `samples/` にあります。

```python
from p_ken import config, factors, report

period = config.load_period()

# コモンファクター（ファクター別の日次）とタイプ別
daily = factors.core_factor_returns("gemq", period.ytd_start, period.end)
by_type = factors.type_returns(daily, "gemq")

# NAM（回帰 / Q5）
nam = factors.nam_factor_returns("blf", period.ytd_start, period.end)
q5 = factors.nam_factor_returns("blf", period.ytd_start, period.end, method="q5")

# 図をまとめて
report.all_figures(period)
```

### 自分のエクスポージャーで計算する

月末ごとの表（`bid` とファクター列）を返す関数を渡します。前月末の値が翌月の各日に使われます。

```python
import pandas as pd
from p_ken import factors, io


def my_factor(ym: str) -> pd.DataFrame:
    core = io.load_core("gemq", ym)
    return core[["bid", "BP_EST", "MOM12"]]


daily = factors.regression_returns("gemq", factors.monthly(my_factor), "2026-01-01", "2026-09-30")
```

| 引数 | 内容 |
|---|---|
| `universe` | `"gemq"`（MSCI EM）/ `"blf"`（RGA） |
| `exposures` | `factors.monthly(関数)`、`factors.panel(表)`（`ym` 列つきの 1 枚の表）、`factors.daily_scores(...)` |
| `ret_col` | `"ret"`（現地通貨建て、デフォルト）/ `"sret"` |
| `stocks` | `ym -> 銘柄リスト`。サブユニバースで計算（例：中国だけ） |
| `standardize` | `"blom"`（デフォルト）/ `"zscore"` / `"raw"` |

分位版は `factors.quantile_returns(..., q=5, group=5 or "spread", breakpoints="formation" or "pooled")` です。

サンプルは実行済みのノートブックです（出力つきで保存しているので、開くだけで結果を確認できます）。

| サンプル | 内容 |
|---|---|
| `samples/01_default.ipynb` | デフォルト（MSCI EM の NAM）、四半期合計、年率の集計、グラフ、sret 版、Q5 版、RGA |
| `samples/02_custom_universe.ipynb` | `stocks=` でユニバースを絞る：中国のみ・ウェイト上位 300・中国除く |
| `samples/03_custom_exposure.ipynb` | 自作ファクター（月ごとの関数 / パネル形式）、標準化の比較、10 分位 |
| `samples/04_core_exposure.ipynb` | core ファクターの一覧、一部の計算、タイプ平均、Value の合成 |

## 8. 困ったとき

| 症状 | 対処 |
|---|---|
| `missing credentials` | `.env` を作るか `--env-file ../datastream/.env` を付ける |
| 図の日本語が □ になる | 日本語フォント（ヒラギノ、游ゴシック、Noto Sans JP など）を入れる |
| ファクターリターンが途中の月で終わる | その月の `exposures`（core や GEMQ3）か `rtn` がない。足りない月は自動で飛ばします。GEMQ3 は `build_gemq3.py` を再実行 |
| `stocks_..._<period>.csv` がない | `fetch_lseg.py stocks` を実行（期間は `config/report.toml`） |
| 図の文字が小さい／大きい | `--fontsize`。貼るときに拡大・縮小しない |
| macOS で `data/GEMQ` と `data/gemq` が混ざる | macOS は大文字小文字を区別しないので同じフォルダになります。古いデータは別名（例：`data/GEMQ_old`）に |
| ツリーマップに USA などがある | 本社所在国で分けているため（§4.5） |

## 9. 開発者向け

### コードの構成

| モジュール | 役割 |
|---|---|
| `p_ken.config` | パス、ユニバース、`config/report.toml` の期間 |
| `p_ken.io` | `data/` の読み込み |
| `p_ken.stats` | Blom、ntile、回帰の傾き、期間リターン |
| `p_ken.gemq3` | GEMQ3 スコア |
| `p_ken.factors` | ファクターリターン（`engine`：計算、`sources`：エクスポージャーの時点、`presets`：レポートの設定） |
| `p_ken.markets` | 指数・国別・銘柄データの準備 |
| `p_ken.charts` | 作図（`style`：色・サイズ・フォント、`labels`：線の端のラベル） |
| `p_ken.report` | 図を作って保存（スクリプトから呼ばれる） |
| `p_ken.cli` | スクリプト共通のオプション |

スクリプト（`scripts/`）は引数を受けて `p_ken.report` を呼ぶだけの薄いものです。`fetch_lseg.py` だけは LSEG のライブラリを別環境で使うため、単体で完結しています。

### 色の決まり

- プラス／マイナス：青 `#1f5fbf` ／ 赤 `#c62828`（色覚の違いがあっても区別しやすい組み合わせ）
- 指数の線：赤の濃淡（濃い順に World、EM、RGA）
- ファクタータイプ：決まった順の 8 色。Other は灰色
- 合成スコア：黒に近い色

### テストと整形

```sh
uv run pytest
uv run ruff check --select I --fix
uv run ruff format
uv run ruff check
```

コミット前に上を実行してください。`tests/test_report_data.py` は `data/` があるときだけ、2026 年 7〜9 月の既知の値と照合します。
