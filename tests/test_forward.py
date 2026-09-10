"""The forward is backed out of parity, not taken from the exchange (ADR 0011)."""
import numpy as np
import pytest

from vsa.forward import implied_forward


def test_recovers_a_known_forward_and_discount_factor():
    F, df = 79_459.55, 0.9971
    K = np.array([60_000.0, 70_000.0, 80_000.0, 90_000.0, 100_000.0])
    diff = df * (F - K)  # C - P under parity
    got = implied_forward(K, diff, np.zeros_like(K))
    assert got.v == pytest.approx(df, rel=1e-12)
    assert got.forward == pytest.approx(F, rel=1e-12)
    assert got.n_strikes == 5


def test_uses_the_difference_not_the_levels():
    F, df = 100.0, 0.99
    K = np.array([90.0, 100.0, 110.0])
    puts = np.array([1.0, 5.0, 14.0])
    calls = puts + df * (F - K)
    got = implied_forward(K, calls, puts)
    assert got.forward == pytest.approx(F, rel=1e-12)


def test_least_squares_absorbs_quote_noise():
    F, df = 100.0, 0.99
    K = np.linspace(80.0, 120.0, 9)
    noise = np.array([0.01, -0.01, 0.02, -0.02, 0.0, 0.01, -0.01, 0.02, -0.02])
    got = implied_forward(K, df * (F - K) + noise, np.zeros_like(K))
    assert got.forward == pytest.approx(F, rel=1e-3)


def test_one_strike_cannot_identify_two_parameters():
    got = implied_forward(np.array([100.0]), np.array([1.0]), np.array([0.0]))
    assert np.isnan(got.forward) and got.n_strikes == 1
