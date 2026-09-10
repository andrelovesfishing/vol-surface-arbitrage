"""Our implied vol against the one Deribit publishes.

Run on the mark basis, because mark_iv is the exchange's vol for its own mark
price. A systematic gap means the published number is not the inversion of the
published price.
"""
from __future__ import annotations

from typing import NamedTuple

import duckdb

from vsa.vols import implied_vols


class Reconciliation(NamedTuple):
    n: int
    median_abs: float
    p90_abs: float
    median_signed: float   # ours minus theirs
    n_unsolved: int


def reconcile(
    con: duckdb.DuckDBPyConnection, *, currency: str | None = None
) -> Reconciliation:
    """Vol points, not percent: 0.01 is one vol point."""
    con.register("_recon", implied_vols(con, "mark", currency=currency))
    row = con.sql("""
        WITH j AS (
            SELECT i.iv_low - q.mark_iv AS gap, i.status
            FROM _recon i
            JOIN quotes q USING (currency, snapshot_ts, expiry_ts, strike_usd, option_type)
            WHERE q.mark_iv IS NOT NULL
        )
        SELECT count(*) FILTER (WHERE status = 'ok' AND gap IS NOT NULL),
               median(abs(gap)) FILTER (WHERE status = 'ok'),
               quantile_cont(abs(gap), 0.9) FILTER (WHERE status = 'ok'),
               median(gap) FILTER (WHERE status = 'ok'),
               count(*) FILTER (WHERE status <> 'ok')
        FROM j
    """).fetchone()
    return Reconciliation(*(x if x is not None else 0.0 for x in row))
