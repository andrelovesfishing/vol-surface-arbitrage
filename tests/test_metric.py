"""The pre-registered primary metric (ADR 0006), on known-answer surfaces."""
from datetime import datetime, timezone

from conftest import quotes_con, surface
from vsa.convexity import headline, summarise

CONVEX = {90_000: 4000.0, 91_000: 3200.0, 92_000: 2500.0, 93_000: 1900.0, 94_000: 1400.0}
SPREAD_ILLUSION = {**CONVEX, 92_000: 2700.0}  # violates on mid, not once spreads are paid


def by_key(rel) -> dict:
    return {(r[0], r[1]): r[2:] for r in rel.fetchall()}


def test_violation_rate_is_reported_per_basis_and_tenor_bucket():
    con = quotes_con(surface(SPREAD_ILLUSION, half_spread=100.0))
    out = by_key(summarise(con))

    assert out[("mid", "0-7d")] == (3, 1, 1 / 3)
    assert out[("executable", "0-7d")] == (3, 0, 0.0)


def test_tenor_buckets_are_split_not_pooled():
    rows = surface(SPREAD_ILLUSION, half_spread=100.0, tenor_years=3 / 365)
    rows += surface(CONVEX, half_spread=100.0, tenor_years=45 / 365,
                    expiry_ts=datetime(2026, 10, 23, 8, tzinfo=timezone.utc))
    out = by_key(summarise(quotes_con(rows)))

    assert out[("mid", "0-7d")] == (3, 1, 1 / 3)
    assert out[("mid", "30-90d")] == (3, 0, 0.0)


def test_headline_is_the_share_of_apparent_arbitrage_that_is_spread_illusion():
    con = quotes_con(surface(SPREAD_ILLUSION, half_spread=100.0))
    result = headline(con)

    assert (result.mid_violations, result.executable_violations) == (1, 0)
    assert result.illusion_share == 1.0


def test_the_metric_can_be_restricted_to_one_underlying():
    # BTC and ETH are reported independently and never reconciled (README).
    rows = surface(SPREAD_ILLUSION, half_spread=100.0)
    rows += surface(CONVEX, half_spread=100.0, currency="ETH")

    assert by_key(summarise(quotes_con(rows), currency="ETH"))[("mid", "0-7d")] == (3, 0, 0.0)
    assert headline(quotes_con(rows), currency="BTC").mid_violations == 1
