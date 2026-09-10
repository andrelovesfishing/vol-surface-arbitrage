"""Total implied variance must not fall as tenor rises.

Expiries are compared at one instant, so this is not a cross-snapshot join
(ADR 0003). Strikes do not line up between expiries, so the far slice is
interpolated in log-moneyness over the overlap only — never extrapolated.

On the executable basis the tradeable direction sells the near expiry at its bid
and buys the far at its ask, so those are the two prices inverted.
"""
from __future__ import annotations

from typing import NamedTuple

import duckdb
import numpy as np
import pyarrow as pa

from vsa.vols import implied_vols

SCHEMA = pa.schema([
    ("currency", pa.string()),
    ("snapshot_ts", pa.timestamp("us", tz="UTC")),
    ("expiry_near", pa.timestamp("us", tz="UTC")),
    ("expiry_far", pa.timestamp("us", tz="UTC")),
    ("log_moneyness", pa.float64()),
    ("w_near", pa.float64()),
    ("w_far", pa.float64()),
    ("is_violation", pa.bool_()),
])


def total_variance(iv, tenor):
    """w = sigma^2 * T, the quantity that must not decrease."""
    return np.asarray(iv, dtype=float) ** 2 * np.asarray(tenor, dtype=float)


def _curve(rows, use_high: bool):
    """One expiry as (log-moneyness, total variance), sorted and deduped."""
    strike = rows["strike_usd"].to_numpy(float)
    k = np.log(strike / rows["forward_usd"].to_numpy(float))
    iv = rows["iv_high" if use_high else "iv_low"].to_numpy(float)
    w = total_variance(iv, rows["tenor_years"].to_numpy(float))
    ok = np.isfinite(k) & np.isfinite(w)
    k, w = k[ok], w[ok]
    order = np.argsort(k)
    k, w = k[order], w[order]
    keep = np.concatenate([[True], np.diff(k) > 0])
    return k[keep], w[keep]


def violations(
    con: duckdb.DuckDBPyConnection, basis: str, *, currency: str | None = None
) -> pa.Table:
    """One row per near-expiry strike inside the far expiry's quoted range."""
    con.register("_cal", implied_vols(con, basis, currency=currency))
    df = con.sql("""
        SELECT i.currency, i.snapshot_ts, i.expiry_ts, i.strike_usd, i.forward_usd,
               i.iv_low, i.iv_high, q.tenor_years
        FROM _cal i
        JOIN quotes q USING (currency, snapshot_ts, expiry_ts, strike_usd, option_type)
        WHERE i.status = 'ok' AND i.option_type = 'C'
        ORDER BY i.currency, i.snapshot_ts, i.expiry_ts, i.strike_usd
    """).df()

    rows = []
    for (cur, snap), group in df.groupby(["currency", "snapshot_ts"], sort=False):
        expiries = sorted(group.expiry_ts.unique())
        for near_ts, far_ts in zip(expiries, expiries[1:]):
            # Sell the near at its bid, buy the far at its ask.
            k_near, w_near = _curve(group[group.expiry_ts == near_ts], use_high=False)
            k_far, w_far = _curve(group[group.expiry_ts == far_ts], use_high=True)
            if k_near.size == 0 or k_far.size < 2:
                continue
            inside = (k_near >= k_far.min()) & (k_near <= k_far.max())
            if not inside.any():
                continue
            interp = np.interp(k_near[inside], k_far, w_far)
            for k, wn, wf in zip(k_near[inside], w_near[inside], interp):
                rows.append({
                    "currency": cur, "snapshot_ts": snap,
                    "expiry_near": near_ts, "expiry_far": far_ts,
                    "log_moneyness": float(k), "w_near": float(wn), "w_far": float(wf),
                    "is_violation": bool(wn > wf),
                })
    return pa.Table.from_pylist(rows, schema=SCHEMA)


class CalendarHeadline(NamedTuple):
    basis: str
    n_points: int
    n_violations: int
    rate: float


def headline(
    con: duckdb.DuckDBPyConnection, basis: str, *, currency: str | None = None
) -> CalendarHeadline:
    """Violation rate over every comparable point."""
    flags = violations(con, basis, currency=currency).column("is_violation").to_pylist()
    n = len(flags)
    hits = sum(flags)
    return CalendarHeadline(basis, n, hits, hits / n if n else 0.0)
