from datetime import datetime, timezone

import pytest

from conftest import FORWARD_USD, INDEX_USD, SNAPSHOT_TS, api_row, snapshot
from vsa.normalise import normalise_snapshot


def only(record) -> dict:
    return normalise_snapshot(record).rows[0]


def test_coin_prices_are_converted_at_the_expiry_forward():
    row = only(snapshot([api_row(bid_price=0.1, ask_price=0.2)]))
    assert row["bid_usd"] == pytest.approx(0.1 * FORWARD_USD)
    assert row["ask_usd"] == pytest.approx(0.2 * FORWARD_USD)


def test_put_call_parity_holds_in_usd():
    # An inverse option pays max(S-K,0)/S coin, so in coin terms
    # C - P = (F - K)/F. Converting at the forward is precisely what turns that
    # into the standard C - P = F - K, on which every price-space bound rests.
    strike, put_coin = 80_000.0, 0.05
    call_coin = put_coin + (FORWARD_USD - strike) / FORWARD_USD
    call, put = normalise_snapshot(snapshot([
        api_row(instrument_name="BTC-8SEP26-80000-C", mark_price=call_coin),
        api_row(instrument_name="BTC-8SEP26-80000-P", mark_price=put_coin),
    ])).rows
    assert call["mark_usd"] - put["mark_usd"] == pytest.approx(FORWARD_USD - strike)


def test_both_reference_levels_are_recorded():
    row = only(snapshot())
    assert row["forward_usd"] == pytest.approx(FORWARD_USD)
    assert row["index_usd"] == pytest.approx(INDEX_USD)  # cash rate, kept for audit


def test_mid_is_the_midpoint_of_the_two_sides():
    row = only(snapshot([api_row(bid_price=0.1, ask_price=0.2)]))
    assert row["mid_usd"] == pytest.approx(0.15 * FORWARD_USD)


def test_mid_is_missing_when_the_book_is_one_sided():
    row = only(snapshot([api_row(bid_price=None, ask_price=0.2)]))
    assert row["bid_usd"] is None
    assert row["mid_usd"] is None


def test_tenor_is_years_from_the_snapshot_to_expiry():
    # snapshot 2026-09-07T20:00Z, expiry 2026-09-08T08:00Z -> 12 hours
    row = only(snapshot())
    assert row["tenor_years"] == pytest.approx(0.5 / 365.0)


def test_mark_iv_is_stored_as_a_fraction_not_a_percentage():
    row = only(snapshot([api_row(mark_iv=54.07)]))
    assert row["mark_iv"] == pytest.approx(0.5407)


def test_every_row_carries_the_snapshot_key_and_its_latency():
    row = only(snapshot(latency=0.25))
    assert row["currency"] == "BTC"
    assert row["snapshot_ts"] == SNAPSHOT_TS
    assert row["latency_s"] == pytest.approx(0.25)


def test_unparseable_instruments_are_dropped_and_reported():
    result = normalise_snapshot(
        snapshot([api_row(), api_row(instrument_name="BTC-PERPETUAL")])
    )
    assert len(result.rows) == 1
    assert result.skipped == ["BTC-PERPETUAL"]


def test_strike_and_expiry_come_from_the_instrument_name():
    row = only(snapshot([api_row(instrument_name="BTC-26MAR27-120000-P")]))
    assert row["strike_usd"] == 120_000.0
    assert row["option_type"] == "P"
    assert row["expiry_ts"] == datetime(2027, 3, 26, 8, 0, tzinfo=timezone.utc)
