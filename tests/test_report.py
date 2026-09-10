"""The report is the deliverable, so its numbers are checked like any other."""
from conftest import quotes_con, surface
from vsa.report import render

CONVEX = {90_000: 4000.0, 91_000: 3200.0, 92_000: 2500.0, 93_000: 1900.0, 94_000: 1400.0}


def test_reports_the_headline_and_the_per_bucket_table():
    rows = surface({**CONVEX, 92_000: 2700.0}, half_spread=100.0)
    rows += surface(CONVEX, half_spread=100.0, currency="ETH")

    text = render(quotes_con(rows))

    assert "1 of 3 butterflies" in text      # mid violations, BTC
    assert "100.0% of it is spread illusion" in text
    assert "ETH" in text and "0-7d" in text


def test_reports_how_much_spread_an_apparent_violation_would_need_you_to_capture():
    text = render(quotes_con(surface({**CONVEX, 92_000: 2700.0}, half_spread=100.0)))

    assert "spread an apparent violation would need you to capture" in text
    assert "median 25.0%" in text


def test_reports_capture_required_cut_by_each_observable():
    text = render(quotes_con(surface({**CONVEX, 92_000: 2700.0}, half_spread=100.0)))

    assert "capture required by slice" in text
    assert "tenor" in text and "moneyness" in text and "spread" in text
    assert "1.05-1.25" in text     # the body sits at 92k against a ~79.5k forward


def test_reports_collective_consistency_and_the_no_tick_column():
    text = render(quotes_con(surface({**CONVEX, 92_000: 2700.0}, half_spread=100.0)))

    assert "Collective consistency of the quoted surface" in text
    assert "no tick" in text      # header column for violations with no parity forward
