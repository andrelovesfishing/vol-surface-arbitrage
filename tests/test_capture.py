"""How much of the quoted spread an apparent violation would need you to capture."""
from datetime import datetime, timezone

from conftest import quotes_con, surface
from vsa.convexity import capture, capture_profile

CONVEX = {90_000: 4000.0, 91_000: 3200.0, 92_000: 2500.0, 93_000: 1900.0, 94_000: 1400.0}
SPREAD_ILLUSION = {**CONVEX, 92_000: 2700.0}  # the 91/92/93 body is $150 too cheap on mid


def test_capture_required_is_the_violation_as_a_share_of_the_package_spread():
    # Uniform strikes: w = 0.5, so the package pays 0.5h + 0.5h + h = 2h = $200.
    # The mid violation is $150, leaving $50 of spread to cross: 50/200 = 0.25.
    con = quotes_con(surface(SPREAD_ILLUSION, half_spread=100.0))

    result = capture(con)

    assert result.n == 1
    assert result.median == 0.25


def test_only_butterflies_that_violate_on_mid_are_measured():
    # The population is the apparent arbitrage; a convex surface has none.
    con = quotes_con(surface(CONVEX, half_spread=100.0))

    assert capture(con).n == 0


def test_a_wider_spread_demands_more_capture_for_the_same_violation():
    # $150 of violation inside a $1000 package spread leaves $850 to cross.
    narrow = capture(quotes_con(surface(SPREAD_ILLUSION, half_spread=100.0)))
    wide = capture(quotes_con(surface(SPREAD_ILLUSION, half_spread=500.0)))

    assert wide.median == 0.85
    assert wide.median > narrow.median


LOW_STRIKE_ILLUSION = {70_000: 4000.0, 71_000: 3200.0, 72_000: 2700.0,
                       73_000: 1900.0, 74_000: 1400.0}
LATER_EXPIRY = datetime(2026, 10, 23, 8, tzinfo=timezone.utc)


def profile(con, by) -> dict:
    return {r[0]: (r[1], r[2]) for r in capture_profile(con, by=by).fetchall()}


def two_slices(**over) -> list[dict]:
    """Two surfaces, one violation each, needing 25% and 85% capture respectively."""
    rows = surface(SPREAD_ILLUSION, half_spread=100.0)
    return rows + surface(half_spread=500.0, expiry_ts=LATER_EXPIRY,
                          tenor_years=45 / 365, **over)


def test_capture_is_profiled_across_tenor_buckets():
    con = quotes_con(two_slices(mids=SPREAD_ILLUSION))

    assert profile(con, "tenor") == {"0-7d": (1, 0.25), "30-90d": (1, 0.85)}


def test_capture_is_profiled_across_package_spread_measured_in_ticks():
    # Half-spreads of $100 and $500 make packages of $200 and $1000, and a tick
    # is 0.0001 * the forward, so roughly 25 and 126 ticks.
    con = quotes_con(two_slices(mids=SPREAD_ILLUSION))

    assert profile(con, "spread") == {"20-100t": (1, 0.25), "100t+": (1, 0.85)}


def test_capture_is_profiled_across_moneyness():
    # Bodies at 92k and 72k against a forward of ~79.5k: 1.16 and 0.91.
    con = quotes_con(two_slices(mids=LOW_STRIKE_ILLUSION))

    assert profile(con, "moneyness") == {"0.8-0.95": (1, 0.85), "1.05-1.25": (1, 0.25)}
