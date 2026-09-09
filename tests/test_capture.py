"""How much of the quoted spread an apparent violation would need you to capture."""
from conftest import quotes_con, surface
from vsa.convexity import capture

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
