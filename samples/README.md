# ファクターリターン サンプル

ユニバースとエクスポージャーを差し替えて `p_ken.fret.run()` を実行する例です。
すべてリポジトリのルートで実行します（データは `data/gemq` から相対パスで読みます）。

```sh
uv run p-ken gemq3                         # 初回のみ: GEMQ3 スコアを作成
uv run python samples/01_default.py        # AI / Revision / GEMQ3 (MSCI EM), ret と sret
uv run python samples/02_custom_universe.py
uv run python samples/03_custom_exposure.py
uv run python samples/04_core_exposure.py
```

| ファイル | 内容 |
|---|---|
| `01_default.py` | 既定の設定（`uv run p-ken fret` と同じ結果）。トータル `ret` とスペシフィック `sret` |
| `02_custom_universe.py` | ユニバース変更: 中国のみ / 時価上位300 / 中国除く |
| `03_custom_exposure.py` | エクスポージャー変更: 関数で自作ファクター、パネル DataFrame、10分位 |
| `04_core_exposure.py` | core ファクター（B/P, E/P, ROE, MOM12 など）とカテゴリ合成 |

## 時点の考え方

ファイル名 `{ym}` は月末時点です。`ym = 202608` なら

- ユニバース・エクスポージャー: 2026/08 末時点
- リターン: `rtn/202608.csv` = 2026/08 末ユニバースの **翌月（2026/09）** の日次リターン

`fret.run()` は同じ `ym` どうしを組み合わせます。

## `fret.run()` の引数

```python
from p_ken import fret

res = fret.run(
    universe=...,  # ym -> DataFrame("bid", ...) / bid のリスト / パネル DataFrame("ym", "bid")
    exposures=...,  # ym -> DataFrame("bid", ファクター列...) / パネル DataFrame("ym", "bid", ...)
    factors=None,  # {出力名: 列名} か 列名リスト。None なら数値列すべて
    months=None,  # ユニバース・エクスポージャーの月 (YYYYMM)。None なら data/gemq/rtn の全月
    start=None,
    end=None,  # その月の範囲 (YYYYMM, 両端含む)
    ret_col="ret",  # "ret"（トータル）か "sret"（スペシフィック）
    n_groups=5,  # 分位数（5 なら Q1..Q5 と Q5-Q1）
    out_dir=None,  # 指定すると CSV を保存
)
```

- 日次超過リターン = 銘柄リターン − その日のユニバース等ウェイト平均。
- エクスポージャーが NaN の銘柄は、そのファクターの分位・回帰から除外されます（超過リターンの基準には含まれます）。
- ユニバース・エクスポージャー・リターンのいずれかが無い月はスキップします。
- `returns=` を渡すとリターンの読み込み元も差し替えられます（`ym` → 翌月の `ymd, bid, ret` を返す関数、ret は % 単位。単位が違う場合は `ret_scale`）。

## 主なローダー（`p_ken.io`）

| 関数 | 内容 |
|---|---|
| `load_unv(ym)` | ユニバース（date, sedol, bid, weight） |
| `load_ai(ym)` / `load_revision(ym)` / `load_qip(ym)` | NAM エクスポージャー |
| `load_gemq3(ym)` | GEMQ3（`p-ken gemq3` の出力） |
| `load_core(ym)` / `load_core_list()` | core ファクター（-999999998 は NaN）と一覧 |
| `load_rtn(ym)` | 翌月の日次リターン（ymd, bid, ret, sret） |

## 戻り値

`res` は DataFrame の dict です（`out_dir` 指定時は同名の CSV）。

| キー | 内容 |
|---|---|
| `quintile_daily` | ymd, factor, grp (Q1..Qn, Qn-Q1), ret, n |
| `regression_daily` | ymd, factor, coef, tstat, intercept, n（日次の単回帰） |
| `quintile_summary` / `regression_summary` | 年率リターン・リスク・RR・勝率 |

プロット用には `fret.cumulative(res, kind="quintile", grp="Q5-Q1")`（または `kind="regression"`）で
ファクターごとの累積系列が得られます。
