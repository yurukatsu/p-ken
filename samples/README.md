# サンプル

`p_ken.factors` でファクターリターンを計算する例です。**実行済みのノートブック**として保存しているので、
開くだけで各セルの出力（表とグラフ）を確認できます。

| ノートブック | 内容 |
|---|---|
| [01_default.ipynb](01_default.ipynb) | デフォルトの計算（MSCI EM の AI / Revision / GEMQ3）、四半期合計、年率の集計、グラフ、sret 版、Q5 版、RGA |
| [02_custom_universe.ipynb](02_custom_universe.ipynb) | `stocks=` でユニバースを絞る：中国のみ / ウェイト上位 300 / 中国除く |
| [03_custom_exposure.ipynb](03_custom_exposure.ipynb) | 自作ファクター（月ごとの関数 / パネル形式）、標準化の比較、10 分位 |
| [04_core_exposure.ipynb](04_core_exposure.ipynb) | core ファクターの一覧、一部の計算、タイプ平均、Value の合成 |

期間は各ノートブック冒頭の `START` / `END` / `Q_START` で指定しています（2026/01/01 – 2026/09/30、強調 7/01 – 9/30）。

## 実行し直す

データ（`data/`）を更新したら、次のコマンドで全ノートブックを実行し直して出力を保存します。

```sh
uv run python scripts/build_gemq3.py   # 初回のみ（MSCI EM の GEMQ3）
uv run jupyter nbconvert --to notebook --execute --inplace samples/*.ipynb
```

自由に試すときは、`samples/` を直接書き換えずに `notebooks/`（git 管理外）にコピーして使ってください。

引数の詳細は [docs/manual.md §7](../docs/manual.md#7-python-から使う)、計算式は [docs/methodology.md](../docs/methodology.md) を参照してください。
