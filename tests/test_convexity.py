"""The convexity detector, validated on surfaces whose answer is known."""
from conftest import quotes_con, surface
from vsa.convexity import butterflies

# Second differences are +100 at every strike: convex, with room to plant a
# violation without disturbing its neighbours.
CONVEX = {90_000: 4000.0, 91_000: 3200.0, 92_000: 2500.0, 93_000: 1900.0, 94_000: 1400.0}


def bodies(rel) -> list[float]:
    """The middle strike of every butterfly the detector flags."""
    return [r[0] for r in rel.filter("is_violation").select("k_body").order("k_body").fetchall()]


def test_clean_surface_has_no_violations():
    con = quotes_con(surface(CONVEX))
    assert bodies(butterflies(con, "mid")) == []


def test_finds_a_planted_violation_and_only_that_one():
    con = quotes_con(surface({**CONVEX, 92_000: 2700.0}))  # body overpriced by 200
    assert bodies(butterflies(con, "mid")) == [92_000.0]


def test_weights_legs_by_strike_spacing_not_equal_differences():
    # Convex on a 2000/4000 grid, but (1, -2, 1) differencing would call it a
    # violation: 4000 - 2*2800 + 1000 = -600.
    con = quotes_con(surface({90_000: 4000.0, 92_000: 2800.0, 96_000: 1000.0}))
    assert bodies(butterflies(con, "mid")) == []


def test_ignores_a_violation_smaller_than_one_tick():
    con = quotes_con(surface({**CONVEX, 92_000: 2554.0}))  # cost -$4 against a ~$8 tick
    assert bodies(butterflies(con, "mid")) == []


def test_reports_that_same_violation_once_the_floor_is_removed():
    con = quotes_con(surface({**CONVEX, 92_000: 2554.0}))
    assert bodies(butterflies(con, "mid", min_ticks=0.0)) == [92_000.0]


def test_executable_prices_erase_a_mid_violation():
    # Wings must be bought at the ask and the body sold at the bid, which costs
    # the full spread twice over: the $150 mid violation becomes a $50 credit.
    con = quotes_con(surface({**CONVEX, 92_000: 2700.0}, half_spread=100.0))
    assert bodies(butterflies(con, "mid")) == [92_000.0]
    assert bodies(butterflies(con, "executable")) == []


def test_legs_never_span_snapshots_expiries_or_option_types():
    from datetime import datetime, timezone

    from conftest import EXPIRY_TS, SNAPSHOT_TS

    later_snapshot = datetime(2026, 9, 7, 21, tzinfo=timezone.utc)
    later_expiry = datetime(2026, 9, 12, 8, tzinfo=timezone.utc)
    clean = {90_000: 4000.0, 91_000: 3200.0, 92_000: 2500.0}
    violating = {**clean, 91_000: 3400.0}

    rows = []
    for snap in (SNAPSHOT_TS, later_snapshot):
        for expiry in (EXPIRY_TS, later_expiry):
            for kind in ("C", "P"):
                mids = violating if (snap, expiry, kind) == (later_snapshot, later_expiry, "P") else clean
                rows += surface(mids, snapshot_ts=snap, expiry_ts=expiry, option_type=kind)

    flies = butterflies(quotes_con(rows), "mid")
    assert flies.aggregate("count(*)").fetchone()[0] == 8  # one per group, never across
    assert flies.filter("is_violation").aggregate(
        "count(*), any_value(option_type), any_value(expiry_ts)"
    ).fetchone() == (1, "P", later_expiry)


def test_a_one_sided_quote_leaves_the_universe_and_its_neighbours_become_adjacent():
    from conftest import quote_row

    rows = surface({90_000: 4000.0, 92_000: 2500.0, 93_000: 1900.0})
    rows.append(quote_row(91_000, None, 3300.0))  # ask only: cannot be sold

    flies = butterflies(quotes_con(rows), "mid")
    assert flies.select("k_low, k_body, k_high").fetchall() == [(90_000.0, 92_000.0, 93_000.0)]
