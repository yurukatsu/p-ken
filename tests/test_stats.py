import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm

from p_ken import stats


def test_blom_formula_and_missing():
    x = pd.Series([3.0, np.nan, 1.0, 2.0])
    z = stats.blom(x)
    n = 3  # NaN is not counted
    expected = norm.ppf((np.array([3, 1, 2]) - 3 / 8) / (n + 1 / 4))
    assert np.isnan(z.iloc[1])
    np.testing.assert_allclose(z.dropna().to_numpy(), expected)
    np.testing.assert_allclose(z.dropna().sum(), 0, atol=1e-12)  # symmetric


def test_blom_is_rank_based():
    x = pd.Series(np.random.default_rng(0).normal(size=50))
    pd.testing.assert_series_equal(stats.blom(x), stats.blom(np.exp(x)))


def test_blom_r_equals_blom_without_ties_at_top():
    x = pd.Series([0.5, 2.0, 1.0, 1.0, 3.0])
    np.testing.assert_allclose(stats.blom_r(x), stats.blom(x))


def test_ntile_matches_dplyr():
    # dplyr::ntile(1:10, 3) -> 1 1 1 1 2 2 2 3 3 3 (larger groups first)
    got = stats.ntile(pd.Series(range(1, 11)), 3).astype(int).tolist()
    assert got == [1, 1, 1, 1, 2, 2, 2, 3, 3, 3]
    assert stats.ntile(pd.Series([np.nan, 1.0]), 2).isna().iloc[0]


def test_slopes_equal_ols_and_handle_missing():
    rng = np.random.default_rng(1)
    z = pd.DataFrame({"a": rng.normal(size=40), "b": rng.normal(size=40)})
    y = 0.3 * z.a.to_numpy() + rng.normal(scale=0.1, size=40)
    z.loc[:4, "b"] = np.nan
    b = stats.slopes(z, y)
    assert b["a"] == pytest.approx(np.polyfit(z.a, y, 1)[0])
    ok = z.b.notna()
    assert b["b"] == pytest.approx(np.polyfit(z.b[ok], y[ok], 1)[0])


def test_slope_ignores_a_common_shift_and_is_a_zero_cost_portfolio():
    rng = np.random.default_rng(2)
    z = pd.DataFrame({"f": rng.normal(size=30)})
    y = rng.normal(size=30)
    b = stats.slopes(z, y)["f"]
    assert stats.slopes(z, y + 0.05)["f"] == pytest.approx(b)  # market move -> intercept
    zc = z.f - z.f.mean()
    w = zc / (zc**2).sum()
    assert w.sum() == pytest.approx(0, abs=1e-12)  # long-short
    assert (w * z.f).sum() == pytest.approx(1)  # unit exposure
    assert (w * y).sum() == pytest.approx(b)


def test_slopes_need_variation_and_observations():
    z = pd.DataFrame({"const": [1.0] * 5, "few": [1.0, 2.0] + [np.nan] * 3})
    b = stats.slopes(z, np.arange(5.0))
    assert np.isnan(b["const"]) and np.isnan(b["few"])


def test_period_return_and_rebase():
    idx = pd.to_datetime(["2026-06-29", "2026-06-30", "2026-07-15", "2026-09-30", "2026-10-01"])
    s = pd.Series([90.0, 100.0, 105.0, 110.0, 120.0], index=idx)
    assert stats.period_return(s, "2026-07-01", "2026-09-30") == pytest.approx(0.10)
    r = stats.rebase(s, "2026-07-01")
    assert r.iloc[0] == pytest.approx(100.0) and r.index[0] == pd.Timestamp("2026-06-30")
