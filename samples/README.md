# ファクターリターン サンプル

ユニバースとエクスポージャーを差し替えて `p_ken.fret.run()` を実行する例です。
すべてリポジトリのルートで実行します（データは `data/GEMQ` から相対パスで読みます）。

```sh
uv run p-ken gemq3                         # 初回のみ: GEMQ3 スコアを作成
uv run python samples/01_default.py        # AI / Revision / GEMQ3 (MSCI EM)
uv run python samples/02_custom_universe.py
uv run python samples/03_custom_exposure.py
```

| ファイル | 内容 |
|---|---|
| `01_default.py` | 既定の設定（`uv run p-ken fret` と同じ結果） |
| `02_custom_universe.py` | ユニバース変更: 中国のみ / 時価上位300 / 中国除く |
| `03_custom_exposure.py` | エクスポージャー変更: 関数で自作ファクター、パネル DataFrame、10分位 |

## `fret.run()` の引数

```python
from p_ken import fret

res = fret.run(
    universe=...,  # exp_ym -> DataFrame("bid", ...) / bid のリスト / パネル DataFrame("ym", "bid")
    exposures=...,  # exp_ym -> DataFrame("bid", ファクター列...) / パネル DataFrame("ym", "bid", ...)
    factors=None,  # {出力名: 列名} か 列名リスト。None なら数値列すべて
    months=None,  # リターン月 (YYYYMM) のリスト。None なら data/GEMQ/rtn の全月
    start=None,
    end=None,  # リターン月の範囲 (YYYYMM, 両端含む)
    n_groups=5,  # 分位数（5 なら Q1..Q5 と Q5-Q1）
    lag=1,  # ユニバース・エクスポージャーは ym - lag 月末時点
    out_dir=None,  # 指定すると CSV を保存
)
```

- リターン月 `ym` に対して、ユニバースとエクスポージャーは `ym - lag` 月のものを使います。
- 日次超過リターン = 銘柄リターン − その日のユニバース等ウェイト平均。
- エクスポージャーが NaN の銘柄は、そのファクターの分位・回帰から除外されます（超過リターンの基準には含まれます）。
- ユニバース・エクスポージャー・リターンのいずれかが無い月はスキップします。
- `returns=` を渡すと日次リターンの読み込み元も差し替えられます（`ymd, bid, ret` を返す関数、ret は % 単位。単位が違う場合は `ret_scale`）。

## 戻り値

`res` は DataFrame の dict です（`out_dir` 指定時は同名の CSV）。

| キー | 内容 |
|---|---|
| `quintile_daily` | ymd, factor, grp (Q1..Qn, Qn-Q1), ret, n |
| `regression_daily` | ymd, factor, coef, tstat, intercept, n（日次の単回帰） |
| `quintile_summary` / `regression_summary` | 年率リターン・リスク・RR・勝率 |

プロット用には `fret.cumulative(res, kind="quintile", grp="Q5-Q1")`（または `kind="regression"`）で
ファクターごとの累積系列が得られます。
