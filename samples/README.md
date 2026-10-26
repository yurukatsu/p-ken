# サンプル

`p_ken.factors` でユニバースやエクスポージャーを差し替えてファクターリターンを計算する例です。
どこからでも実行できます（データはリポジトリの `data/` を読みます）。

```sh
uv run python scripts/build_gemq3.py      # 初回のみ（MSCI EM の GEMQ3）
uv run python samples/01_default.py
uv run python samples/02_custom_universe.py
uv run python samples/03_custom_exposure.py
uv run python samples/04_core_exposure.py
```

| ファイル | 内容 |
|---|---|
| `01_default.py` | デフォルトの計算（MSCI EM の AI / Revision / GEMQ3、ret と sret）と年率の集計 |
| `02_custom_universe.py` | `stocks=` でユニバースを絞る：中国のみ / 時価上位 300 / 中国除く |
| `03_custom_exposure.py` | 自作ファクター（月末の表を返す関数）、10 分位（`quantile_returns`）、パネル形式の表 |
| `04_core_exposure.py` | core ファクターの一部、Value の合成ファクター |

引数の詳細は [docs/manual.md §7](../docs/manual.md#7-python-から使う)、計算式は [docs/methodology.md](../docs/methodology.md) を参照してください。
