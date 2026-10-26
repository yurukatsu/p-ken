"""Checks against the real data (skipped when data/ is not present)."""

import pytest

from p_ken import config, factors, markets
from p_ken.stats import period_return

needs_data = pytest.mark.skipif(
    not (config.DATA_ROOT / "gemq" / "rtn").exists(), reason="data/ not available"
)


@needs_data
def test_nam_msci_em_q3_2026():
    d = factors.nam_factor_returns("gemq", "2026-07-01", "2026-09-30")
    assert d.sum()["AI"] == pytest.approx(-0.0165, abs=5e-5)
    assert d.sum()["Revision"] == pytest.approx(0.0084, abs=5e-5)


@needs_data
def test_index_q3_2026():
    em = markets.load_index("em", "close")
    assert period_return(em, "2026-07-01", "2026-09-30") == pytest.approx(-0.0105, abs=5e-5)
