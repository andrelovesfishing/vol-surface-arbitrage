from datetime import datetime, timezone

import pytest

from vsa.instruments import parse_instrument


def test_parses_a_call():
    inst = parse_instrument("BTC-8SEP26-90000-C")
    assert inst.currency == "BTC"
    assert inst.strike_usd == 90_000.0
    assert inst.option_type == "C"


def test_parses_a_put_on_another_underlying():
    inst = parse_instrument("ETH-26MAR27-4200-P")
    assert inst.currency == "ETH"
    assert inst.strike_usd == 4_200.0
    assert inst.option_type == "P"


def test_expiry_is_0800_utc_on_the_named_day():
    inst = parse_instrument("BTC-8SEP26-90000-C")
    assert inst.expiry_ts == datetime(2026, 9, 8, 8, 0, tzinfo=timezone.utc)


def test_rejects_an_instrument_that_is_not_a_dated_option():
    with pytest.raises(ValueError, match="BTC-PERPETUAL"):
        parse_instrument("BTC-PERPETUAL")
