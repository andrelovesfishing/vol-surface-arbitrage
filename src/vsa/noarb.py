"""Does one arbitrage-free surface fit inside the whole quoted band?

Unknowns per slice are every call price, every put price, the discount factor v,
the forward product u = df*F, and a scalar band relaxation t. Every static
no-arbitrage condition is linear in those, so the question is a linear program:
minimise t. t* = 0 means the band admits an arbitrage-free surface.

Butterflies and vertical spreads are rows here rather than separate detectors;
parity with (u, v) free is the box spread, which needs no forward (ADR 0011).
"""
from __future__ import annotations

from typing import NamedTuple

import numpy as np
from scipy.optimize import linprog

from vsa.slices import Slice

MAX_RATE = 1.0  # the discount factor floor is exp(-MAX_RATE * T): generous, not tuned


class Problem(NamedTuple):
    c: np.ndarray
    A_ub: np.ndarray
    b_ub: np.ndarray
    A_eq: np.ndarray
    b_eq: np.ndarray
    bounds: list
    labels: list[str]
    n_call: int
    n_put: int


def build(sl: Slice) -> Problem:
    """The LP for one slice. Variable order: calls, puts, u, v, t."""
    nc, npu = sl.call_k.size, sl.put_k.size
    n = nc + npu + 3
    iu, iv, it = nc + npu, nc + npu + 1, nc + npu + 2

    rows: list[np.ndarray] = []
    rhs: list[float] = []
    labels: list[str] = []

    def add(label: str, b: float, terms: dict[int, float]):
        row = np.zeros(n)
        for idx, coeff in terms.items():
            row[idx] += coeff
        rows.append(row)
        rhs.append(b)
        labels.append(label)

    for offset, k, lo, hi, is_call in (
        (0, sl.call_k, sl.call_lo, sl.call_hi, True),
        (nc, sl.put_k, sl.put_lo, sl.put_hi, False),
    ):
        kind = "call" if is_call else "put"
        for i in range(k.size):
            j = offset + i
            add("band_low", -lo[i], {j: -1.0, it: -1.0})
            add("band_high", hi[i], {j: 1.0, it: -1.0})
            if is_call:
                add(f"{kind}_upper", 0.0, {j: 1.0, iu: -1.0})            # C <= u
                add(f"{kind}_lower", 0.0, {j: -1.0, iu: 1.0, iv: -k[i]})  # C >= u - v*K
            else:
                add(f"{kind}_upper", 0.0, {j: 1.0, iv: -k[i]})            # P <= v*K
                add(f"{kind}_lower", 0.0, {j: -1.0, iv: k[i], iu: -1.0})  # P >= v*K - u

        for i in range(k.size - 1):
            a, b = offset + i, offset + i + 1
            dk = float(k[i + 1] - k[i])
            if is_call:
                add(f"{kind}_monotone", 0.0, {b: 1.0, a: -1.0})           # falls in K
                add(f"{kind}_vertical", 0.0, {b: -1.0, a: 1.0, iv: -dk})  # by at most v*dK
            else:
                add(f"{kind}_monotone", 0.0, {a: 1.0, b: -1.0})           # rises in K
                add(f"{kind}_vertical", 0.0, {b: 1.0, a: -1.0, iv: -dk})

        for i in range(1, k.size - 1):
            k_lo, k_mid, k_hi = float(k[i - 1]), float(k[i]), float(k[i + 1])
            w = (k_hi - k_mid) / (k_hi - k_lo)
            add(f"{kind}_convexity", 0.0,
                {offset + i - 1: -w, offset + i: 1.0, offset + i + 1: -(1.0 - w)})

    # Parity links the two surfaces wherever both are quoted.
    shared = np.intersect1d(sl.call_k, sl.put_k)
    ci = np.searchsorted(sl.call_k, shared)
    pi = np.searchsorted(sl.put_k, shared)
    A_eq = np.zeros((shared.size, n))
    for r, (c_idx, p_idx, k) in enumerate(zip(ci, pi, shared)):
        A_eq[r, c_idx] = 1.0
        A_eq[r, nc + p_idx] = -1.0
        A_eq[r, iu] = -1.0
        A_eq[r, iv] = float(k)

    c = np.zeros(n)
    c[it] = 1.0

    bounds = [(0.0, None)] * (nc + npu)
    bounds.append((1e-9, None))                                   # u
    bounds.append((float(np.exp(-MAX_RATE * sl.tenor_years)), 1.0))  # v
    bounds.append((0.0, None))                                    # t

    return Problem(
        c=c,
        A_ub=np.array(rows) if rows else np.zeros((0, n)),
        b_ub=np.array(rhs),
        A_eq=A_eq,
        b_eq=np.zeros(shared.size),
        bounds=bounds,
        labels=labels,
        n_call=nc,
        n_put=npu,
    )


class Solution(NamedTuple):
    t: float                       # band widening needed, in USD
    u: float
    v: float
    forward: float
    status: str                    # ok | degenerate | too_few_strikes
    binding: tuple[str, ...]


_UNSOLVED = Solution(np.nan, np.nan, np.nan, np.nan, "degenerate", ())


def solve(problem: Problem, *, tol: float = 1e-7) -> Solution:
    """Minimise the band relaxation. t* = 0 means the band admits a clean surface."""
    res = linprog(
        problem.c, A_ub=problem.A_ub, b_ub=problem.b_ub,
        A_eq=problem.A_eq if problem.A_eq.size else None,
        b_eq=problem.b_eq if problem.b_eq.size else None,
        bounds=problem.bounds, method="highs",
    )
    if not res.success:
        return _UNSOLVED

    x = res.x
    iu, iv = problem.n_call + problem.n_put, problem.n_call + problem.n_put + 1
    u, v = float(x[iu]), float(x[iv])

    slack = problem.b_ub - problem.A_ub @ x
    binding = {lab for lab, s in zip(problem.labels, slack)
               if s <= tol and not lab.startswith("band_")}

    return Solution(
        t=float(x[-1]), u=u, v=v,
        forward=u / v if v else np.nan,
        status="ok", binding=tuple(sorted(binding)),
    )


def feasibility(sl: Slice, *, tol: float = 1e-7) -> Solution:
    """Convenience: build then solve. A slice needs three strikes to be convex."""
    if max(sl.call_k.size, sl.put_k.size) < 3:
        return _UNSOLVED._replace(status="too_few_strikes")
    return solve(build(sl), tol=tol)
