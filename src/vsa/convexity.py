"""The convexity condition: an option price must be convex in strike.

For strikes K1 < K2 < K3 in one expiry, write K2 = w*K1 + (1-w)*K3. Buying w of
K1 and (1-w) of K3 and selling one K2 has a payoff that is never negative, so
its cost must not be either. A negative cost is a violation.

Weighting by w rather than differencing (1, -2, 1) matters: Deribit's strike
grid is not evenly spaced, and equal weights on unequal spacing report ordinary
convex surfaces as violations.
"""
from __future__ import annotations

from typing import NamedTuple

import duckdb

TICK_COIN = 0.0001  # Deribit's option tick, quoted in coin; USD tick = tick * forward

# Which quote each leg trades at. The wings are bought, the body is sold, so
# only the executable basis distinguishes them (ADR 0002).
_BASIS = {
    "mid": ("mid_usd", "mid_usd"),
    "executable": ("ask_usd", "bid_usd"),
    "mark": ("mark_usd", "mark_usd"),
}
PRICE_BASES = tuple(_BASIS)


def butterflies(
    con: duckdb.DuckDBPyConnection,
    basis: str = "mid",
    *,
    min_ticks: float = 1.0,
    currency: str | None = None,
) -> duckdb.DuckDBPyRelation:
    """Every adjacent-strike butterfly in every snapshot, priced on one basis.

    min_ticks is the materiality floor. Each of the three quotes is rounded to
    the tick, and the position holds two contracts' worth, so rounding alone can
    fabricate up to one tick of apparent violation.
    """
    return con.sql(_butterflies_sql(basis, min_ticks, currency))


def _butterflies_sql(basis: str, min_ticks: float, currency: str | None = None) -> str:
    buy, sell = _BASIS[basis]
    only = f"AND currency = '{currency}'" if currency else ""
    return f"""
        WITH quotable AS (
            -- Two-sided quotes only, so every basis is measured on one universe
            -- and the mid-vs-executable ratio compares like with like.
            SELECT currency, snapshot_ts, expiry_ts, option_type, strike_usd,
                   tenor_years, forward_usd,
                   {buy} AS buy_usd, {sell} AS sell_usd
            FROM quotes
            WHERE bid_usd IS NOT NULL AND ask_usd IS NOT NULL {only}
        ),
        triples AS (
            -- Legs are adjacent within a single snapshot and expiry (ADR 0003).
            SELECT currency, snapshot_ts, expiry_ts, option_type, tenor_years, forward_usd,
                   lag(strike_usd) OVER w AS k_low,
                   strike_usd          AS k_body,
                   lead(strike_usd) OVER w AS k_high,
                   lag(buy_usd) OVER w AS low_usd,
                   sell_usd            AS body_usd,
                   lead(buy_usd) OVER w AS high_usd
            FROM quotable
            WINDOW w AS (
                PARTITION BY currency, snapshot_ts, expiry_ts, option_type
                ORDER BY strike_usd
            )
        ),
        priced AS (
            SELECT currency, snapshot_ts, expiry_ts, option_type, tenor_years,
                   forward_usd, k_low, k_body, k_high,
                   (k_high - k_body) / (k_high - k_low) AS w_low,
                   ((k_high - k_body) * low_usd + (k_body - k_low) * high_usd)
                       / (k_high - k_low) - body_usd AS cost_usd,
                   {TICK_COIN} * forward_usd AS tick_usd
            FROM triples
            WHERE k_low IS NOT NULL AND k_high IS NOT NULL
        )
        SELECT *, cost_usd < -{float(min_ticks)} * tick_usd AS is_violation
        FROM priced
    """


# Buckets are reported separately because spread width and tenor move together;
# pooling them would hide the effect the project is measuring.
TENOR_BUCKETS = (("0-7d", 7.0), ("7-30d", 30.0), ("30-90d", 90.0), ("90d+", None))



def _bucket_case(expr: str, buckets) -> str:
    """Map expr into labelled bands; the last band is the open-ended one."""
    return "CASE " + " ".join(
        f"WHEN {expr} < {hi} THEN '{label}'" for label, hi in buckets if hi is not None
    ) + f" ELSE '{buckets[-1][0]}' END"


def _bucket_order(column: str, buckets) -> str:
    return f"CASE {column} " + " ".join(
        f"WHEN '{label}' THEN {i}" for i, (label, _) in enumerate(buckets)
    ) + " END"


_TENOR_YEARS = tuple((label, None if d is None else d / 365.0) for label, d in TENOR_BUCKETS)
_BUCKET_SQL = _bucket_case("tenor_years", _TENOR_YEARS)
_BUCKET_ORDER = _bucket_order("tenor_bucket", TENOR_BUCKETS)


class Headline(NamedTuple):
    butterflies: int
    mid_violations: int
    executable_violations: int
    mid_rate: float
    executable_rate: float
    illusion_share: float | None  # None when there was no apparent arbitrage to lose


def summarise(
    con: duckdb.DuckDBPyConnection,
    *,
    bases: tuple[str, ...] = PRICE_BASES,
    min_ticks: float = 1.0,
    currency: str | None = None,
) -> duckdb.DuckDBPyRelation:
    """The primary metric: violation rate per price basis per tenor bucket."""
    counted = " UNION ALL ".join(
        f"""SELECT '{basis}' AS basis, {_BUCKET_SQL} AS tenor_bucket,
                   count(*) AS n_butterflies,
                   sum(is_violation::int) AS n_violations
            FROM ({_butterflies_sql(basis, min_ticks, currency)}) GROUP BY ALL"""
        for basis in bases
    )
    order = " ".join(f"WHEN '{b}' THEN {i}" for i, b in enumerate(bases))
    return con.sql(f"""
        SELECT basis, tenor_bucket, n_butterflies, n_violations,
               n_violations / n_butterflies AS violation_rate
        FROM ({counted})
        ORDER BY CASE basis {order} END, {_BUCKET_ORDER}
    """)


def headline(
    con: duckdb.DuckDBPyConnection, *, min_ticks: float = 1.0, currency: str | None = None
) -> Headline:
    """Mid vs executable over the whole dataset, and the gap between them.

    illusion_share is the project's headline number: the fraction of apparent
    arbitrage that exists only because mid prices cannot be traded.
    """
    totals = {
        basis: con.sql(
            f"SELECT count(*), sum(is_violation::int) "
            f"FROM ({_butterflies_sql(basis, min_ticks, currency)})"
        ).fetchone()
        for basis in ("mid", "executable")
    }
    n, mid_v = totals["mid"]
    _, exec_v = totals["executable"]
    return Headline(
        butterflies=n,
        mid_violations=mid_v,
        executable_violations=exec_v,
        mid_rate=mid_v / n if n else 0.0,
        executable_rate=exec_v / n if n else 0.0,
        illusion_share=None if not mid_v else 1.0 - exec_v / mid_v,
    )


class Capture(NamedTuple):
    n: int  # mid violations measured; the population is the apparent arbitrage
    median: float
    p10: float
    p90: float


def _required_sql(min_ticks: float, currency: str | None, select: str = "") -> str:
    """Capture required, one row per butterfly that violates on mid."""
    key = "currency, snapshot_ts, expiry_ts, option_type, k_low, k_body, k_high"
    return f"""
        WITH m AS ({_butterflies_sql("mid", min_ticks, currency)}),
             e AS ({_butterflies_sql("executable", min_ticks, currency)})
        SELECT {select} e.cost_usd / (e.cost_usd - m.cost_usd) AS capture_required
        FROM m JOIN e USING ({key})
        WHERE m.is_violation AND e.cost_usd > m.cost_usd
    """


def capture(
    con: duckdb.DuckDBPyConnection, *, min_ticks: float = 1.0, currency: str | None = None
) -> Capture:
    """How much of the quoted spread an apparent violation would need you to capture.

    Paying the spread on every leg costs S = cost_executable - cost_mid, so a
    violation of D = -cost_mid becomes free money only once you trade
    1 - D/S = cost_executable/S of the way from the touch to the mid, on all
    three legs at once. Zero executable violations is exactly D < S everywhere,
    and this is that binary as a distribution.
    """
    row = con.sql(f"""
        SELECT count(*), median(capture_required),
               quantile_cont(capture_required, 0.1), quantile_cont(capture_required, 0.9)
        FROM ({_required_sql(min_ticks, currency)})
    """).fetchone()
    return Capture(*row)


MONEYNESS_BUCKETS = (("<0.8", 0.8), ("0.8-0.95", 0.95), ("0.95-1.05", 1.05),
                     ("1.05-1.25", 1.25), ("1.25+", None))
SPREAD_BUCKETS = (("<2t", 2.0), ("2-5t", 5.0), ("5-20t", 20.0), ("20-100t", 100.0),
                  ("100t+", None))

# Both legs of the join carry tick_usd and forward_usd, so those need qualifying.
PROFILE_DIMENSIONS = {
    "tenor": ("m.tenor_years", _TENOR_YEARS),
    "moneyness": ("k_body / m.forward_usd", MONEYNESS_BUCKETS),
    "spread": ("(e.cost_usd - m.cost_usd) / m.tick_usd", SPREAD_BUCKETS),
}


def capture_profile(
    con: duckdb.DuckDBPyConnection, *, by: str,
    min_ticks: float = 1.0, currency: str | None = None,
) -> duckdb.DuckDBPyRelation:
    """Capture required, cut by one observable: does any slice come closer?

    Descriptive, not pre-registered (ADR 0009). A flat profile is the point —
    it says no corner of the surface is nearer to a tradeable violation.
    """
    expr, buckets = PROFILE_DIMENSIONS[by]
    inner = _required_sql(min_ticks, currency, f"{_bucket_case(expr, buckets)} AS bucket,")
    return con.sql(f"""
        SELECT bucket, count(*) AS n_violations,
               median(capture_required) AS median_capture,
               quantile_cont(capture_required, 0.1) AS p10_capture
        FROM ({inner})
        GROUP BY bucket ORDER BY {_bucket_order("bucket", buckets)}
    """)
