"""Our solver against Deribit's published mark_iv."""
import numpy as np
import pytest

from conftest import EXPIRY_TS, SNAPSHOT_TS, quote_row, quotes_con
from vsa import black76
from vsa.reconcile import reconcile

TENOR = (EXPIRY_TS - SNAPSHOT_TS).total_seconds() / (365.0 * 86_400.0)
F, DF = 80_000.0, 0.999
STRIKES = [70_000.0, 75_000.0, 80_000.0, 85_000.0, 90_000.0]


def surface_with_mark_iv(sigma, published):
    rows = []
    for k in STRIKES:
        for is_call, kind in ((True, "C"), (False, "P")):
            p = float(black76.price(F, k, TENOR, sigma, DF, is_call))
            rows.append(quote_row(
                k, p, p, option_type=kind, mark_usd=p, mark_iv=published,
                instrument_name=f"BTC-8SEP26-{int(k)}-{kind}",
            ))
    return rows


def test_perfect_agreement_when_the_exchange_is_consistent():
    got = reconcile(quotes_con(surface_with_mark_iv(0.62, 0.62)))
    assert got.n == 10
    assert got.median_abs == pytest.approx(0.0, abs=1e-6)
    assert got.n_unsolved == 0


def test_a_systematic_gap_is_measured_and_signed():
    got = reconcile(quotes_con(surface_with_mark_iv(0.62, 0.60)))
    assert got.median_signed == pytest.approx(0.02, abs=1e-6)
    assert got.median_abs == pytest.approx(0.02, abs=1e-6)


def test_quotes_without_a_published_iv_are_excluded_not_counted_as_agreement():
    got = reconcile(quotes_con(surface_with_mark_iv(0.62, None)))
    assert got.n == 0
