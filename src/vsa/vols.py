"""Implied volatility per quote, on one price basis (ADR 0002).

The forward comes from parity on mid prices regardless of basis (ADR 0011), so
the band moves but its inputs do not. iv_low and iv_high are the vol-space band.
"""
from __future__ import annotations

import duckdb
import numpy as np
import pyarrow as pa

from vsa import black76
from vsa.forward import implied_forward
from vsa.slices import iter_slices, paired_mids

SCHEMA = pa.schema([
    ("currency", pa.string()),
    ("snapshot_ts", pa.timestamp("us", tz="UTC")),
    ("expiry_ts", pa.timestamp("us", tz="UTC")),
    ("strike_usd", pa.float64()),
    ("option_type", pa.string()),
    ("forward_usd", pa.float64()),
    ("df", pa.float64()),
    ("iv_low", pa.float64()),
    ("iv_high", pa.float64()),
    ("status", pa.string()),
])


def implied_vols(
    con: duckdb.DuckDBPyConnection, basis: str, *, currency: str | None = None
) -> pa.Table:
    """One row per two-sided quote: the vol band, or why there isn't one."""
    mids = {
        (s.currency, s.snapshot_ts, s.expiry_ts): s
        for s in iter_slices(con, "mid", currency=currency)
    }
    rows: list[dict] = []

    for sl in iter_slices(con, basis, currency=currency):
        fwd = implied_forward(*paired_mids(mids[(sl.currency, sl.snapshot_ts, sl.expiry_ts)]))
        for is_call, kind, k, lo, hi in (
            (True, "C", sl.call_k, sl.call_lo, sl.call_hi),
            (False, "P", sl.put_k, sl.put_lo, sl.put_hi),
        ):
            if k.size == 0:
                continue
            iv_lo = black76.implied_vol(lo, fwd.forward, k, sl.tenor_years, fwd.v, is_call)
            iv_hi = black76.implied_vol(hi, fwd.forward, k, sl.tenor_years, fwd.v, is_call)
            for j in range(k.size):
                solved = np.isfinite(iv_lo[j]) and np.isfinite(iv_hi[j])
                rows.append({
                    "currency": sl.currency,
                    "snapshot_ts": sl.snapshot_ts,
                    "expiry_ts": sl.expiry_ts,
                    "strike_usd": float(k[j]),
                    "option_type": kind,
                    "forward_usd": fwd.forward,
                    "df": fwd.v,
                    "iv_low": float(iv_lo[j]),
                    "iv_high": float(iv_hi[j]),
                    "status": "ok" if solved else
                              ("no_forward" if not np.isfinite(fwd.forward) else "no_solution"),
                })

    return pa.Table.from_pylist(rows, schema=SCHEMA)


def materialise(
    con: duckdb.DuckDBPyConnection, basis: str, *, currency: str | None = None
) -> None:
    """Expose the vol band as the DuckDB view `ivs`."""
    con.register("_ivs", implied_vols(con, basis, currency=currency))
    con.execute("CREATE OR REPLACE VIEW ivs AS SELECT * FROM _ivs")
