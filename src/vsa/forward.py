"""The forward implied by put-call parity, per slice (ADR 0011).

C(K) - P(K) = u - v*K with v = df and u = df*F, so a straight line through the
call-minus-put differences gives both. Two parameters from ~90 strikes.
"""
from __future__ import annotations

from typing import NamedTuple

import numpy as np


class ImpliedForward(NamedTuple):
    u: float          # df * F, the intercept
    v: float          # df, the negated slope
    forward: float    # u / v
    n_strikes: int


_UNIDENTIFIED = (np.nan, np.nan, np.nan)


def implied_forward(strikes, call_mid, put_mid) -> ImpliedForward:
    """Least-squares (u, v) from the parity line. Needs two distinct strikes."""
    K = np.asarray(strikes, dtype=float)
    y = np.asarray(call_mid, dtype=float) - np.asarray(put_mid, dtype=float)
    ok = np.isfinite(K) & np.isfinite(y)
    K, y = K[ok], y[ok]

    if K.size < 2 or np.unique(K).size < 2:
        return ImpliedForward(*_UNIDENTIFIED, int(K.size))

    design = np.column_stack([np.ones_like(K), -K])
    (u, v), *_ = np.linalg.lstsq(design, y, rcond=None)
    forward = u / v if v != 0.0 else np.nan
    return ImpliedForward(float(u), float(v), float(forward), int(K.size))
