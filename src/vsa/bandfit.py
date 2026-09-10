"""Every slice's no-arbitrage program, run and cached.

The LPs take minutes over the full dataset, so results are written to parquet
and analyse.py reads them back rather than re-solving.
"""
from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import duckdb
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from vsa import noarb
from vsa.convexity import TICK_COIN
from vsa.forward import implied_forward
from vsa.load import PARQUET_DIR
from vsa.slices import BANDS, iter_slices, paired_mids

CACHE_DIR = PARQUET_DIR.parent / "bandfit"

SCHEMA = pa.schema([
    ("currency", pa.string()),
    ("snapshot_ts", pa.timestamp("us", tz="UTC")),
    ("expiry_ts", pa.timestamp("us", tz="UTC")),
    ("basis", pa.string()),
    ("tenor_years", pa.float64()),
    ("n_call", pa.int32()),
    ("n_put", pa.int32()),
    ("t_usd", pa.float64()),
    ("t_ticks", pa.float64()),
    ("forward_usd", pa.float64()),
    ("df", pa.float64()),
    ("status", pa.string()),
    ("binding", pa.string()),
])


def _mid_forwards(con, currency):
    """Parity forward per slice, always from mid, so the tick does not move with basis."""
    return {
        (s.currency, s.snapshot_ts, s.expiry_ts): implied_forward(*paired_mids(s))
        for s in iter_slices(con, "mid", currency=currency)
    }


def run(con: duckdb.DuckDBPyConnection, basis: str, *, currency: str | None = None) -> pa.Table:
    """One row per slice: how far the band would have to widen, and why."""
    forwards = _mid_forwards(con, currency)
    rows = []
    for sl in iter_slices(con, basis, currency=currency):
        sol = noarb.feasibility(sl)
        fwd = forwards[(sl.currency, sl.snapshot_ts, sl.expiry_ts)]
        # Parity forward, so the tick does not move with basis. convexity.py
        # scales by the quotes' forward_usd instead, so the two tick counts
        # differ by the parity basis (~1e-5 relative) and are not interchangeable.
        tick = TICK_COIN * fwd.forward
        rows.append({
            "currency": sl.currency,
            "snapshot_ts": sl.snapshot_ts,
            "expiry_ts": sl.expiry_ts,
            "basis": basis,
            "tenor_years": sl.tenor_years,
            "n_call": int(sl.call_k.size),
            "n_put": int(sl.put_k.size),
            "t_usd": sol.t,
            "t_ticks": sol.t / tick if np.isfinite(tick) and tick else np.nan,
            "forward_usd": fwd.forward,
            "df": fwd.v,
            "status": sol.status,
            "binding": ",".join(sol.binding),
        })
    return pa.Table.from_pylist(rows, schema=SCHEMA)


def cached(
    con: duckdb.DuckDBPyConnection, basis: str, *, force: bool = False,
    cache_dir: Path | None = None,
) -> pa.Table:
    """Read the basis from parquet, computing it once if it is not there yet.

    `cache_dir` follows the caller's dataset. CACHE_DIR is bound to the default
    PARQUET_DIR, so a run against a different --parquet-dir would otherwise read
    back a cache built from other data and report the two side by side.
    """
    path = Path(cache_dir or CACHE_DIR) / f"{basis}.parquet"
    if path.exists() and not force:
        return pq.read_table(path)
    table = run(con, basis)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)
    return table


def materialise(
    con: duckdb.DuckDBPyConnection, bases=tuple(BANDS), *, force: bool = False,
    cache_dir: Path | None = None,
) -> None:
    """Expose every basis as the DuckDB view `bandfit`."""
    con.register("_bandfit", pa.concat_tables(
        [cached(con, b, force=force, cache_dir=cache_dir) for b in bases]))
    con.execute("CREATE OR REPLACE VIEW bandfit AS SELECT * FROM _bandfit")


class BandHeadline(NamedTuple):
    basis: str
    n_slices: int
    n_clean: int          # t* = 0: the band admits an arbitrage-free surface
    clean_share: float
    median_ticks: float   # over the slices that do not
    p90_ticks: float
    n_unsolved: int
    n_no_tick: int         # violating slices with no parity forward to scale by


CLEAN_TOL_USD = 1e-6


def headline(con: duckdb.DuckDBPyConnection, *, currency: str | None = None) -> list[BandHeadline]:
    """Share of slices whose band admits a clean surface, per basis (ADR 0010).

    The clean test is on `t_usd`, not on ticks: a slice with no paired
    call/put strikes has no parity forward, so its tick is nan while its t*
    is still well-defined. Such slices stay in the primary share and are
    reported separately (`n_no_tick`) rather than silently dropped from the
    tick severity distribution.
    """
    only = f"AND currency = '{currency}'" if currency else ""
    rows = con.sql(f"""
        WITH s AS (
            SELECT basis, status, t_ticks,
                   t_usd <= {CLEAN_TOL_USD} AS is_clean,
                   isfinite(t_ticks) AS has_tick
            FROM bandfit WHERE 1 = 1 {only}
        )
        SELECT basis,
               count(*) FILTER (WHERE status = 'ok') AS n_slices,
               count(*) FILTER (WHERE status = 'ok' AND is_clean) AS n_clean,
               median(t_ticks) FILTER (WHERE status = 'ok' AND NOT is_clean AND isfinite(t_ticks)),
               quantile_cont(t_ticks, 0.9) FILTER (WHERE status = 'ok' AND NOT is_clean AND isfinite(t_ticks)),
               count(*) FILTER (WHERE status <> 'ok') AS n_unsolved,
               count(*) FILTER (WHERE status = 'ok' AND NOT is_clean AND NOT has_tick) AS n_no_tick
        FROM s GROUP BY basis ORDER BY basis
    """).fetchall()
    return [
        BandHeadline(
            basis=b, n_slices=n, n_clean=clean,
            clean_share=clean / n if n else 0.0,
            median_ticks=med if med is not None else 0.0,
            p90_ticks=p90 if p90 is not None else 0.0,
            n_unsolved=unsolved,
            n_no_tick=no_tick,
        )
        for b, n, clean, med, p90, unsolved, no_tick in rows
    ]
