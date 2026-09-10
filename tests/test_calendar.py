"""Total variance must not fall as tenor rises, compared within one snapshot."""
from datetime import timedelta

import numpy as np
import pytest

from conftest import EXPIRY_TS, SNAPSHOT_TS, quote_row, quotes_con
from vsa import black76, calendar

FAR_EXPIRY = EXPIRY_TS + timedelta(days=1)  # adjacent, so total variance can actually fall
F, DF = 80_000.0, 0.999
STRIKES = [76_000.0, 78_000.0, 80_000.0, 82_000.0, 84_000.0]


def _tenor(expiry):
    return (expiry - SNAPSHOT_TS).total_seconds() / (365.0 * 86_400.0)


def two_expiry_surface(sigma_near, sigma_far, half_spread=0.0):
    rows = []
    for expiry, sigma in ((EXPIRY_TS, sigma_near), (FAR_EXPIRY, sigma_far)):
        t = _tenor(expiry)
        tag = "8SEP26" if expiry == EXPIRY_TS else "9SEP26"
        for k in STRIKES:
            for is_call, kind in ((True, "C"), (False, "P")):
                p = float(black76.price(F, k, t, sigma, DF, is_call))
                rows.append(quote_row(
                    k, p - half_spread, p + half_spread,
                    option_type=kind, expiry_ts=expiry, tenor_years=t,
                    instrument_name=f"BTC-{tag}-{int(k)}-{kind}",
                ))
    return rows


def test_total_variance_is_vol_squared_times_tenor():
    assert calendar.total_variance(0.5, 0.25) == pytest.approx(0.0625)


def test_a_flat_vol_surface_has_no_calendar_violation():
    con = quotes_con(two_expiry_surface(0.6, 0.6))
    got = calendar.headline(con, "mid")
    assert got.n_points > 0 and got.n_violations == 0


def test_a_falling_total_variance_is_a_violation():
    # 3x the tenor at a quarter of the vol: w_near 0.0020 against w_far 0.0004
    con = quotes_con(two_expiry_surface(1.2, 0.3))
    got = calendar.headline(con, "mid")
    assert got.n_violations == got.n_points and got.rate == pytest.approx(1.0)


def test_the_executable_basis_uses_bid_near_against_ask_far():
    # w_near 0.00166 against w_far 0.00148: a violation on mid. Widening the
    # spread prices the near leg down (bid) and the far leg up (ask), which
    # shrinks the gap and removes violations one strike at a time -- it does
    # not remove the comparable points themselves.
    tight = calendar.headline(quotes_con(two_expiry_surface(1.10, 0.60)), "executable")
    wide = calendar.headline(
        quotes_con(two_expiry_surface(1.10, 0.60, half_spread=20.0)), "executable"
    )
    assert tight.n_violations > 0
    assert wide.n_violations < tight.n_violations
    assert wide.n_points == tight.n_points


def test_comparisons_never_extrapolate_beyond_the_overlap():
    rows = [r for r in two_expiry_surface(0.6, 0.6)
            if not (r["expiry_ts"] == FAR_EXPIRY and r["strike_usd"] in (82_000.0, 84_000.0))]
    tab = calendar.violations(quotes_con(rows), "mid").to_pydict()
    near_far = np.array(tab["log_moneyness"])
    assert near_far.max() <= 1e-6  # the far slice now stops at 80k, so k <= 0


def wide_wing_surface(half_spread=300.0, strikes=(70_000.0, 80_000.0, 90_000.0),
                       sigma_near=1.10, sigma_far=0.60):
    """Wide enough at the wings that iv inversion fails there (status='no_solution')."""
    rows = []
    for expiry, sigma in ((EXPIRY_TS, sigma_near), (FAR_EXPIRY, sigma_far)):
        t = _tenor(expiry)
        tag = "8SEP26" if expiry == EXPIRY_TS else "9SEP26"
        for k in strikes:
            for is_call, kind in ((True, "C"), (False, "P")):
                p = float(black76.price(F, k, t, sigma, DF, is_call))
                rows.append(quote_row(
                    k, p - half_spread, p + half_spread,
                    option_type=kind, expiry_ts=expiry, tenor_years=t,
                    instrument_name=f"BTC-{tag}-{int(k)}-{kind}",
                ))
    return rows


def test_headline_counts_unsolved_quotes_rather_than_dropping_them():
    # half_spread=300 on the 70k/80k/90k wings makes them un-invertible; only
    # the 80k strike survives per expiry.
    got = calendar.headline(quotes_con(wide_wing_surface()), "executable")
    assert got.n_unsolved > 0
    assert got.n_points == 0 and got.n_violations == 0 and got.rate == 0.0


def test_headline_counts_pairs_skipped_for_too_few_solvable_strikes():
    # Same fixture: with only one solvable strike per expiry, the far curve
    # has fewer than two points, so the pair is skipped rather than compared.
    got = calendar.headline(quotes_con(wide_wing_surface()), "executable")
    assert got.n_skipped_pairs > 0
    assert got.n_points == 0 and got.n_violations == 0 and got.rate == 0.0
