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
