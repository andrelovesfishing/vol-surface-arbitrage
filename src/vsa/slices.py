"""One expiry's two-sided quotes at one instant, split by option type.

The unit every vol-space test operates on. Basis selects which pair of columns
becomes the band (ADR 0002); mid and mark are zero-width.
"""
from __future__ import annotations

from typing import Iterator, NamedTuple

import duckdb
import numpy as np

BANDS = {
    "executable": ("bid_usd", "ask_usd"),
    "mid": ("mid_usd", "mid_usd"),
    "mark": ("mark_usd", "mark_usd"),
}


class Slice(NamedTuple):
    currency: str
    snapshot_ts: object
    expiry_ts: object
    tenor_years: float
    call_k: np.ndarray
    call_lo: np.ndarray
    call_hi: np.ndarray
    put_k: np.ndarray
    put_lo: np.ndarray
    put_hi: np.ndarray


def _sql(basis: str, currency: str | None) -> str:
    low, high = BANDS[basis]
    only = f"AND currency = '{currency}'" if currency else ""
    return f"""
        SELECT currency, snapshot_ts, expiry_ts, tenor_years, option_type,
               strike_usd, {low} AS band_low, {high} AS band_high
        FROM quotes
        WHERE bid_usd IS NOT NULL AND ask_usd IS NOT NULL {only}
        ORDER BY currency, snapshot_ts, expiry_ts, option_type, strike_usd
    """


def iter_slices(
    con: duckdb.DuckDBPyConnection, basis: str, *, currency: str | None = None
) -> Iterator[Slice]:
    """Every (currency, snapshot, expiry) group, in key order."""
    df = con.sql(_sql(basis, currency)).df()
    if df.empty:
        return
    for (cur, snap, exp), group in df.groupby(
        ["currency", "snapshot_ts", "expiry_ts"], sort=False
    ):
        calls = group[group.option_type == "C"]
        puts = group[group.option_type == "P"]
        yield Slice(
            currency=cur,
            snapshot_ts=snap,
            expiry_ts=exp,
            tenor_years=float(group.tenor_years.iloc[0]),
            call_k=calls.strike_usd.to_numpy(float),
            call_lo=calls.band_low.to_numpy(float),
            call_hi=calls.band_high.to_numpy(float),
            put_k=puts.strike_usd.to_numpy(float),
            put_lo=puts.band_low.to_numpy(float),
            put_hi=puts.band_high.to_numpy(float),
        )


def paired_mids(sl: Slice):
    """Strikes carrying both a call and a put; parity needs both legs."""
    shared = np.intersect1d(sl.call_k, sl.put_k)
    ci = np.searchsorted(sl.call_k, shared)
    pi = np.searchsorted(sl.put_k, shared)
    call_mid = 0.5 * (sl.call_lo[ci] + sl.call_hi[ci])
    put_mid = 0.5 * (sl.put_lo[pi] + sl.put_hi[pi])
    return shared, call_mid, put_mid
