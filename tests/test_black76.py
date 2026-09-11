"""Black-76 against vollib, which is used only as an oracle (ADR 0005)."""
import warnings

import numpy as np
import pytest
from vollib.black import black

from vsa import black76

# (forward, strike, tenor, sigma) spanning ITM, ATM and both wings
GRID = [
    (100.0, 95.0, 0.5, 0.40),
    (100.0, 100.0, 0.5, 0.40),
    (100.0, 130.0, 0.05, 0.90),
    (79_459.55, 60_000.0, 0.00137, 0.55),
    (79_459.55, 200_000.0, 1.5, 1.20),
]


@pytest.mark.parametrize("F,K,T,sigma", GRID)
@pytest.mark.parametrize("is_call", [True, False])
def test_price_matches_oracle(F, K, T, sigma, is_call):
    r = 0.03
    df = np.exp(-r * T)
    ours = black76.price(F, K, T, sigma, df, is_call)
    theirs = black(  # vollib: (flag, F, K, t, r, sigma), returns discounted
        "c" if is_call else "p", F, K, T, r, sigma
    )
    assert ours == pytest.approx(theirs, rel=1e-12, abs=1e-10)


def test_parity_holds_exactly():
    F, K, T, sigma, df = 79_459.55, 90_000.0, 0.25, 0.6, 0.995
    c = black76.price(F, K, T, sigma, df, True)
    p = black76.price(F, K, T, sigma, df, False)
    assert c - p == pytest.approx(df * (F - K), rel=1e-12)


def test_zero_vol_is_discounted_intrinsic():
    F, K, T, df = 100.0, 95.0, 0.5, 0.99
    assert black76.price(F, K, T, 0.0, df, True) == pytest.approx(df * 5.0)
    assert black76.price(F, K, T, 0.0, df, False) == pytest.approx(0.0)


def test_price_broadcasts_over_arrays():
    K = np.array([90.0, 100.0, 110.0])
    out = black76.price(100.0, K, 0.5, 0.4, 0.99, np.array([True, True, False]))
    assert out.shape == (3,)
    assert np.all(np.diff(out[:2]) < 0)  # calls fall as strike rises


def test_vega_matches_a_finite_difference():
    F, K, T, sigma, df = 100.0, 105.0, 0.75, 0.35, 0.98
    h = 1e-6
    up = black76.price(F, K, T, sigma + h, df, True)
    dn = black76.price(F, K, T, sigma - h, df, True)
    assert black76.vega(F, K, T, sigma, df) == pytest.approx((up - dn) / (2 * h), rel=1e-6)


def test_inversion_round_trips():
    F, K, T, df = 79_459.55, 85_000.0, 0.25, 0.995
    for sigma in (0.05, 0.4, 1.2, 3.0):
        p = black76.price(F, K, T, sigma, df, True)
        assert black76.implied_vol(p, F, K, T, df, True) == pytest.approx(sigma, rel=1e-8)


# Deep in the money at 12 hours, vega is ~0: the price pins down sigma only weakly,
# so that point is checked in price space rather than in vol space.
INVERT_GRID = [g for g in GRID if g != (79_459.55, 60_000.0, 0.00137, 0.55)]


@pytest.mark.parametrize("F,K,T,sigma", INVERT_GRID)
@pytest.mark.parametrize("is_call", [True, False])
def test_inversion_matches_oracle(F, K, T, sigma, is_call):
    from vollib.black.implied_volatility import implied_volatility as oracle_iv

    r = 0.03
    df = np.exp(-r * T)
    p = black76.price(F, K, T, sigma, df, is_call)
    ours = black76.implied_vol(p, F, K, T, df, is_call)
    theirs = oracle_iv(p, F, K, r, T, "c" if is_call else "p")  # note: (r, t) order
    assert ours == pytest.approx(theirs, rel=1e-8)


@pytest.mark.parametrize("F,K,T,sigma", GRID)
@pytest.mark.parametrize("is_call", [True, False])
def test_inversion_reproduces_the_price_everywhere(F, K, T, sigma, is_call):
    df = np.exp(-0.03 * T)
    p = black76.price(F, K, T, sigma, df, is_call)
    back = black76.price(F, K, T, black76.implied_vol(p, F, K, T, df, is_call), df, is_call)
    assert back == pytest.approx(p, rel=1e-8, abs=1e-10)


def test_price_below_intrinsic_has_no_implied_vol():
    F, K, T, df = 100.0, 90.0, 0.5, 0.99
    assert np.isnan(black76.implied_vol(df * 9.0, F, K, T, df, True))


def test_price_above_the_forward_has_no_implied_vol():
    F, K, T, df = 100.0, 90.0, 0.5, 0.99
    assert np.isnan(black76.implied_vol(df * 100.5, F, K, T, df, True))


def test_deep_wing_inverts_where_vega_collapses():
    # Vega is ~0 here, so Newton alone cannot land it; bisection must.
    F, K, T, df, sigma = 79_459.55, 150_000.0, 0.02, 1.0, 0.9
    p = black76.price(F, K, T, sigma, df, True)
    assert black76.implied_vol(p, F, K, T, df, True) == pytest.approx(sigma, rel=1e-6)


def test_inversion_is_vectorised():
    F, T, df = 100.0, 0.5, 0.99
    K = np.array([80.0, 100.0, 120.0])
    sigma = np.array([0.3, 0.5, 0.8])
    p = black76.price(F, K, T, sigma, df, True)
    got = black76.implied_vol(p, F, K, T, df, True)
    assert got == pytest.approx(sigma, rel=1e-8)


def test_a_denormal_vega_does_not_overflow():
    """Newton divides by vega. Far enough into the wing vega goes denormal, and
    evaluating err / v before applying the guard overflows to inf."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        black76.implied_vol(1913.0, 80_000.0, 794_794.4, 0.01, 0.999, True)
