"""Every slice's no-arbitrage program, run and cached.

The LPs take minutes over the full dataset, so results are written to parquet
and analyse.py reads them back rather than re-solving.
"""
from __future__ import annotations

from pathlib import Path

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


def cached(con: duckdb.DuckDBPyConnection, basis: str, *, force: bool = False) -> pa.Table:
    """Read the basis from parquet, computing it once if it is not there yet."""
    path = Path(CACHE_DIR) / f"{basis}.parquet"
    if path.exists() and not force:
        return pq.read_table(path)
    table = run(con, basis)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)
    return table


def materialise(
    con: duckdb.DuckDBPyConnection, bases=tuple(BANDS), *, force: bool = False
) -> None:
    """Expose every basis as the DuckDB view `bandfit`."""
    con.register("_bandfit", pa.concat_tables([cached(con, b, force=force) for b in bases]))
    con.execute("CREATE OR REPLACE VIEW bandfit AS SELECT * FROM _bandfit")
