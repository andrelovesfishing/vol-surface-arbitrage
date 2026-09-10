"""Black-76 against vollib, which is used only as an oracle (ADR 0005)."""
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
