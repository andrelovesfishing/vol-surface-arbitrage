"""Every slice, one basis at a time, cached to parquet."""
import numpy as np
import pytest

from conftest import EXPIRY_TS, SNAPSHOT_TS, quote_row, quotes_con
from vsa import bandfit, black76

TENOR = (EXPIRY_TS - SNAPSHOT_TS).total_seconds() / (365.0 * 86_400.0)
F, DF = 80_000.0, 0.999
STRIKES = [70_000.0, 75_000.0, 80_000.0, 85_000.0, 90_000.0]


def clean_surface(half_spread=0.0, bump=None):
    rows = []
    for k in STRIKES:
        for is_call, kind in ((True, "C"), (False, "P")):
            p = float(black76.price(F, k, TENOR, 0.6, DF, is_call))
            if bump and is_call and k == bump[0]:
                p += bump[1]
            rows.append(quote_row(
                k, p - half_spread, p + half_spread, option_type=kind,
                instrument_name=f"BTC-8SEP26-{int(k)}-{kind}",
            ))
    return rows


def test_a_clean_surface_needs_no_widening_on_any_basis():
    con = quotes_con(clean_surface(half_spread=10.0))
    for basis in ("mid", "executable"):
        tab = bandfit.run(con, basis).to_pydict()
        assert tab["status"] == ["ok"]
        assert tab["t_usd"][0] == pytest.approx(0.0, abs=1e-6)


def test_a_planted_violation_needs_widening_on_mid_but_not_on_a_wide_band():
    con = quotes_con(clean_surface(half_spread=400.0, bump=(80_000.0, 300.0)))
    mid = bandfit.run(con, "mid").to_pydict()
    ex = bandfit.run(con, "executable").to_pydict()
    assert mid["t_usd"][0] > 1e-6
    assert ex["t_usd"][0] == pytest.approx(0.0, abs=1e-6)


def test_widening_is_reported_in_ticks_against_the_implied_forward():
    con = quotes_con(clean_surface(bump=(80_000.0, 300.0)))
    row = bandfit.run(con, "mid").to_pydict()
    tick = 0.0001 * row["forward_usd"][0]
    assert row["t_ticks"][0] == pytest.approx(row["t_usd"][0] / tick, rel=1e-9)


def test_binding_constraints_are_recorded():
    # bump=(80_000, 300) only breaks parity here, an equality row that never
    # appears in `binding`; 1500 on the same strike clears the convexity
    # threshold (708.0) while staying below monotonicity (4994.1).
    con = quotes_con(clean_surface(bump=(75_000.0, 1500.0)))
    row = bandfit.run(con, "mid").to_pydict()
    assert row["status"] == ["ok"]
    assert row["t_usd"][0] == pytest.approx(573.45, abs=0.01)
    assert row["t_ticks"][0] == pytest.approx(71.42, abs=0.01)
    assert "call_convexity" in row["binding"][0]


def test_cache_is_written_then_reused(tmp_path, monkeypatch):
    monkeypatch.setattr(bandfit, "CACHE_DIR", tmp_path)
    con = quotes_con(clean_surface(half_spread=10.0))
    first = bandfit.cached(con, "mid")
    assert (tmp_path / "mid.parquet").exists()
    monkeypatch.setattr(bandfit, "run", lambda *a, **k: pytest.fail("recomputed"))
    assert bandfit.cached(con, "mid").num_rows == first.num_rows


def test_headline_counts_clean_slices_per_basis(tmp_path, monkeypatch):
    monkeypatch.setattr(bandfit, "CACHE_DIR", tmp_path)
    con = quotes_con(clean_surface(half_spread=400.0, bump=(80_000.0, 300.0)))
    bandfit.materialise(con, ("mid", "executable"))
    got = {h.basis: h for h in bandfit.headline(con)}
    assert got["executable"].clean_share == pytest.approx(1.0)
    assert got["mid"].clean_share == pytest.approx(0.0)
    assert got["mid"].median_ticks > 0


def test_unsolved_slices_are_counted_not_silently_clean(tmp_path, monkeypatch):
    monkeypatch.setattr(bandfit, "CACHE_DIR", tmp_path)
    rows = [r for r in clean_surface() if r["strike_usd"] in (70_000.0, 75_000.0)]
    con = quotes_con(rows)  # two strikes: cannot carry convexity
    bandfit.materialise(con, ("mid",))
    got = bandfit.headline(con)[0]
    assert got.n_unsolved == 1 and got.n_clean == 0
