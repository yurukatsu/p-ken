"""Engine on synthetic data (io readers are replaced by in-memory tables)."""

import numpy as np
import pandas as pd
import pytest

from p_ken.factors import engine, sources

BIDS = [f"S{i:02d}" for i in range(20)]
DAYS = {"202606": ["20260701", "20260702"], "202607": ["20260803"]}


@pytest.fixture
def fake_returns(monkeypatch):
    rng = np.random.default_rng(3)
    x = pd.Series(rng.normal(size=len(BIDS)), index=BIDS)  # true exposure
    true_f = {"20260701": 0.01, "20260702": -0.02, "20260803": 0.005}
    rows = []
    for ym, days in DAYS.items():
        for d in days:
            r = 0.3 + 100 * true_f[d] * x  # percent; 0.3 = market move
            for b in BIDS:
                rows.append({"ym": ym, "ymd": d, "bid": b, "ret": r[b], "sret": r[b] - 0.3})
    df = pd.DataFrame(rows)
    df.loc[0, "ret"] = 150.0  # |ret| >= 100 % must be dropped
    monkeypatch.setattr(engine.io, "list_yms", lambda u, sub: list(DAYS))
    monkeypatch.setattr(
        engine.io, "load_returns", lambda u, ym: df[df.ym == ym].drop(columns="ym").copy()
    )
    return x, true_f


def test_iter_days_filters(fake_returns):
    days = list(engine.iter_days("gemq", "2026-07-02", "2026-08-31"))
    assert [d for _, d, _ in days] == ["20260702", "20260803"]
    first = next(engine.iter_days("gemq", "2026-07-01", "2026-07-01"))[2]
    assert len(first) == len(BIDS) - 1  # the 150 % row is gone


def test_regression_recovers_factor_return(fake_returns):
    x, true_f = fake_returns
    src = sources.monthly(lambda ym: x.rename("f").to_frame())
    got = engine.regression_returns("gemq", src, "2026-07-01", standardize="raw")
    for d, f in true_f.items():
        assert got.loc[pd.Timestamp(d), "f"] == pytest.approx(f)


def test_blom_regression_depends_only_on_ranks(fake_returns):
    x, _ = fake_returns
    a = engine.regression_returns(
        "gemq", sources.monthly(lambda ym: x.rename("f").to_frame()), "2026-07-01"
    )
    b = engine.regression_returns(
        "gemq", sources.monthly(lambda ym: np.exp(x).rename("f").to_frame()), "2026-07-01"
    )
    pd.testing.assert_frame_equal(a, b)


def test_quantile_top_group_excess(fake_returns):
    x, true_f = fake_returns
    src = sources.monthly(lambda ym: x.rename("f").to_frame())
    got = engine.quantile_returns("gemq", src, "2026-08-01", q=5)
    r = 0.3 + 100 * true_f["20260803"] * x
    top = x.rank() > len(x) * 4 / 5
    expected = ((r - r.mean())[top].mean()) / 100
    assert got.iloc[0, 0] == pytest.approx(expected)


def test_missing_exposure_is_dropped(fake_returns):
    x, true_f = fake_returns
    y = x.copy()
    y.iloc[:5] = -999999998  # sentinel -> missing
    got = engine.regression_returns(
        "gemq",
        sources.monthly(lambda ym: y.rename("f").to_frame()),
        "2026-08-01",
        standardize="raw",
    )
    assert got.iloc[0, 0] == pytest.approx(true_f["20260803"])
