# p-ken

新興国株式の四半期レビュー資料に貼る図と、ファクターリターンを作るツールです。
MSCI EM と RGA の 2 つのユニバースを扱います。

- **使い方**：[docs/manual.md](docs/manual.md)
- **計算方法（定式化）**：[docs/methodology.md](docs/methodology.md)

## 作れる図

| 図 | スクリプト |
|---|---|
| 指数の推移（MSCI World / EM / RGA、年初来、四半期を強調） | `scripts/plot_index_ytd.py` |
| 国別・MSCI EM セクター別の四半期リターン | `scripts/plot_period_returns.py` |
| コモンファクターリターン（タイプ別） | `scripts/plot_common_fret.py` |
| NAM ファクターリターン（AI、Revision、GEMQ3 / TVL、RVL、合成） | `scripts/plot_nam_fret.py` |
| 銘柄ツリーマップ（国別・セクター別・国×セクター） | `scripts/plot_treemap.py` |

図はスライドに貼る大きさ（cm）で出力するので、拡大・縮小せずに貼ります。

ファクターリターンのデフォルトは「現地通貨建てリターンを、Blom スコアに標準化したエクスポージャーで 1 ファクターずつ回帰した傾き」です。

## 四半期の作業

```sh
uv sync
# 1. data/gemq, data/blf を最新にし、config/report.toml の期間を書き換える
uv run python scripts/build_gemq3.py                          # 2. GEMQ3
uv run scripts/fetch_lseg.py --env-file ../datastream/.env all  # 3. LSEG から市場データ
uv run python scripts/make_figures.py                         # 4. 全部の図 -> output/figures
```

## 構成

```
config/report.toml   レポートの期間
scripts/             実行するスクリプト（fetch_lseg.py, build_gemq3.py, plot_*.py, make_figures.py）
src/p_ken/           ライブラリ（config, io, stats, gemq3, factors, markets, charts, report）
samples/             使い方の例（実行済みノートブック）
docs/                マニュアルと計算方法
tests/               テスト（uv run pytest）
data/, output/, notebooks/   git 管理外
```
