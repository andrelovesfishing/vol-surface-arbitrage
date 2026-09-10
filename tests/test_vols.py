"""Implied vols over synthetic surfaces, one basis at a time (ADR 0002)."""
import numpy as np
import pytest

from conftest import EXPIRY_TS, SNAPSHOT_TS, quote_row, quotes_con
from vsa import black76, slices, vols

TENOR = (EXPIRY_TS - SNAPSHOT_TS).total_seconds() / (365.0 * 86_400.0)
F, DF = 80_000.0, 0.999


def parity_surface(strikes, sigma, half_spread=0.0):
    """Calls and puts from one flat vol, so parity holds exactly by construction."""
    rows = []
    for k in strikes:
        for is_call, kind in ((True, "C"), (False, "P")):
            p = float(black76.price(F, k, TENOR, sigma, DF, is_call))
            rows.append(quote_row(
                k, p - half_spread, p + half_spread,
                option_type=kind,
                instrument_name=f"BTC-8SEP26-{int(k)}-{kind}",
            ))
    return rows


STRIKES = [70_000.0, 75_000.0, 80_000.0, 85_000.0, 90_000.0]


def test_slice_splits_calls_from_puts_and_sorts_by_strike():
    con = quotes_con(parity_surface(STRIKES, 0.6, half_spread=5.0))
    got = list(slices.iter_slices(con, "executable"))
    assert len(got) == 1
    s = got[0]
    assert list(s.call_k) == sorted(STRIKES)
    assert list(s.put_k) == sorted(STRIKES)
    assert np.all(s.call_hi > s.call_lo)


def test_mid_basis_has_a_zero_width_band():
    con = quotes_con(parity_surface(STRIKES, 0.6, half_spread=5.0))
    s = next(iter(slices.iter_slices(con, "mid")))
    assert s.call_lo == pytest.approx(s.call_hi)


def test_recovers_the_vol_the_surface_was_built_from():
    con = quotes_con(parity_surface(STRIKES, 0.62))
    tab = vols.implied_vols(con, "mid").to_pydict()
    assert set(tab["status"]) == {"ok"}
    assert tab["iv_low"] == pytest.approx([0.62] * 10, rel=1e-6)
    assert tab["forward_usd"] == pytest.approx([F] * 10, rel=1e-6)


def test_executable_band_brackets_the_mid_vol():
    # Strikes close to ATM: at this tenor a wing premium can be cents, smaller
    # than a wide spread would leave for bid_usd, which stays this test near ATM.
    near_atm = [76_000.0, 78_000.0, 80_000.0, 82_000.0, 84_000.0]
    con = quotes_con(parity_surface(near_atm, 0.62, half_spread=5.0))
    tab = vols.implied_vols(con, "executable").to_pydict()
    low = np.array(tab["iv_low"])
    high = np.array(tab["iv_high"])
    assert np.all(low < 0.62) and np.all(high > 0.62)


def test_unsolvable_quote_is_flagged_not_dropped():
    rows = parity_surface(STRIKES, 0.6)
    rows.append(quote_row(  # a call quoted above the discounted forward
        95_000.0, DF * F * 1.5, DF * F * 1.6,
        option_type="C", instrument_name="BTC-8SEP26-95000-C",
    ))
    tab = vols.implied_vols(quotes_con(rows), "mid").to_pydict()
    assert tab["status"].count("no_solution") == 1
    assert len(tab["status"]) == 11


def test_materialise_exposes_an_ivs_view():
    con = quotes_con(parity_surface(STRIKES, 0.6))
    vols.materialise(con, "mid")
    assert con.sql("SELECT count(*) FROM ivs").fetchone()[0] == 10
