"""Black-76: European options on a forward, priced and inverted by hand.

Written rather than imported (ADR 0005). `scipy.special.erf` is a special
function, not an option pricer, so it is not the thing being avoided.
"""
from __future__ import annotations

import numpy as np
from scipy.special import erf

_SQRT2 = np.sqrt(2.0)
_INV_SQRT_2PI = 1.0 / np.sqrt(2.0 * np.pi)


def _cdf(x: np.ndarray) -> np.ndarray:
    return 0.5 * (1.0 + erf(x / _SQRT2))


def _pdf(x: np.ndarray) -> np.ndarray:
    return _INV_SQRT_2PI * np.exp(-0.5 * x * x)


def _d1_d2(F, K, T, sigma):
    """Returns (d1, d2, sigma*sqrt(T)); the last is zero where the option is degenerate."""
    vol_t = sigma * np.sqrt(T)
    with np.errstate(divide="ignore", invalid="ignore"):
        d1 = (np.log(F / K) + 0.5 * vol_t * vol_t) / vol_t
    return d1, d1 - vol_t, vol_t


def price(forward, strike, tenor, sigma, df, is_call) -> np.ndarray:
    """Discounted Black-76 price. Every argument broadcasts."""
    F, K, T, s, d = np.broadcast_arrays(
        *(np.asarray(x, dtype=float) for x in (forward, strike, tenor, sigma, df))
    )
    call_flag = np.asarray(is_call, dtype=bool)
    d1, d2, vol_t = _d1_d2(F, K, T, s)

    call = d * (F * _cdf(d1) - K * _cdf(d2))
    put = d * (K * _cdf(-d2) - F * _cdf(-d1))
    out = np.where(call_flag, call, put)

    # Zero variance leaves d1 undefined; the price is the discounted intrinsic.
    intrinsic = d * np.where(call_flag, np.maximum(F - K, 0.0), np.maximum(K - F, 0.0))
    return np.where(vol_t > 0.0, out, intrinsic)[()]


def vega(forward, strike, tenor, sigma, df) -> np.ndarray:
    """dPrice/dSigma. Identical for calls and puts, and zero at zero variance."""
    F, K, T, s, d = np.broadcast_arrays(
        *(np.asarray(x, dtype=float) for x in (forward, strike, tenor, sigma, df))
    )
    d1, _, vol_t = _d1_d2(F, K, T, s)
    out = d * F * _pdf(d1) * np.sqrt(T)
    return np.where(vol_t > 0.0, out, 0.0)[()]


NO_ARB_TOL = 1e-12
_NEWTON_STEPS = 24
_BISECT_STEPS = 80
_CONV_REL = 1e-10


def _bounds(F, K, d, call_flag):
    """The prices an option can have: discounted intrinsic up to the discounted forward."""
    lo = d * np.where(call_flag, np.maximum(F - K, 0.0), np.maximum(K - F, 0.0))
    hi = d * np.where(call_flag, F, K)
    return lo, hi


def implied_vol(target, forward, strike, tenor, df, is_call, *, lo=1e-6, hi=5.0):
    """Sigma reproducing `target`, or nan where no sigma can.

    Newton on vega converges in a handful of steps near the money. Where vega has
    collapsed Newton stalls, so those points alone are finished by bisection on
    the bracket, which cannot fail on a monotone function.
    """
    p, F, K, T, d = np.broadcast_arrays(
        *(np.asarray(x, dtype=float) for x in (target, forward, strike, tenor, df))
    )
    call_flag = np.broadcast_to(np.asarray(is_call, dtype=bool), p.shape)

    p_lo, p_hi = _bounds(F, K, d, call_flag)
    live = (p >= p_lo - NO_ARB_TOL) & (p <= p_hi + NO_ARB_TOL) & (T > 0.0)

    if not live.any():
        return np.full(p.shape, np.nan, dtype=float)[()]

    # Brenner-Subrahmanyam gives a start already close at the money.
    with np.errstate(divide="ignore", invalid="ignore"):
        guess = np.sqrt(2.0 * np.pi / np.where(T > 0, T, 1.0)) * p / (d * F)
    x = np.clip(np.where(np.isfinite(guess), guess, 0.5), lo, hi)

    for _ in range(_NEWTON_STEPS):
        err = price(F, K, T, x, d, call_flag) - p
        v = vega(F, K, T, x, d)
        # np.where would evaluate err / v everywhere before selecting, so a
        # denormal vega overflows even though the guard discards the result.
        step = np.divide(err, v, out=np.zeros_like(err), where=v > 1e-12)
        x = np.clip(x - step, lo, hi)

    # Bisection finishes only the points Newton left stalled; it costs nothing elsewhere.
    stalled = ~(np.abs(price(F, K, T, x, d, call_flag) - p) <= _CONV_REL * np.maximum(np.abs(p), 1e-300))
    if stalled.any():
        a = np.full(p.shape, lo)
        b = np.full(p.shape, hi)
        for _ in range(_BISECT_STEPS):
            m = 0.5 * (a + b)
            too_cheap = price(F, K, T, m, d, call_flag) < p
            a = np.where(too_cheap, m, a)
            b = np.where(too_cheap, b, m)
        x = np.where(stalled, 0.5 * (a + b), x)

    return np.where(live, x, np.nan)[()]
