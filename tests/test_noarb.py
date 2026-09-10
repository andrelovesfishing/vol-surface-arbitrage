"""The slice LP: shape, then behaviour."""
import numpy as np
import pytest

from vsa import noarb
from vsa.slices import Slice

K = np.array([90.0, 100.0, 110.0])


def make_slice(call_lo, call_hi, put_lo=None, put_hi=None, k=K, tenor=0.25):
    zeros = np.zeros_like(k)
    return Slice(
        currency="BTC", snapshot_ts=None, expiry_ts=None, tenor_years=tenor,
        call_k=k, call_lo=np.asarray(call_lo, float), call_hi=np.asarray(call_hi, float),
        put_k=k if put_lo is not None else np.array([]),
        put_lo=np.asarray(put_lo if put_lo is not None else [], float),
        put_hi=np.asarray(put_hi if put_hi is not None else [], float),
    )


def test_variable_layout_is_prices_then_u_v_t():
    p = noarb.build(make_slice([12.0, 6.0, 2.0], [13.0, 7.0, 3.0]))
    assert p.n_call == 3 and p.n_put == 0
    assert p.c.size == 3 + 0 + 3
    assert p.c[-1] == 1.0 and np.all(p.c[:-1] == 0.0)  # minimise t alone


def test_band_rows_appear_for_every_quote():
    p = noarb.build(make_slice([12.0, 6.0, 2.0], [13.0, 7.0, 3.0]))
    assert p.labels.count("band_low") == 3
    assert p.labels.count("band_high") == 3


def test_convexity_rows_use_spacing_weights():
    k = np.array([90.0, 100.0, 120.0])  # deliberately uneven
    p = noarb.build(make_slice([12.0, 6.0, 2.0], [13.0, 7.0, 3.0], k=k))
    row = p.A_ub[p.labels.index("call_convexity")]
    w = (120.0 - 100.0) / (120.0 - 90.0)
    assert row[:3] == pytest.approx([-w, 1.0, -(1.0 - w)])


def test_parity_rows_only_at_shared_strikes():
    p = noarb.build(make_slice(
        [12.0, 6.0, 2.0], [13.0, 7.0, 3.0],
        put_lo=[1.0, 5.0, 11.0], put_hi=[2.0, 6.0, 12.0],
    ))
    assert p.A_eq.shape[0] == 3
    iu, iv = p.n_call + p.n_put, p.n_call + p.n_put + 1
    assert p.A_eq[0][0] == 1.0 and p.A_eq[0][3] == -1.0
    assert p.A_eq[0][iu] == -1.0 and p.A_eq[0][iv] == pytest.approx(90.0)


def test_discount_factor_is_bounded_by_tenor():
    p = noarb.build(make_slice([12.0, 6.0, 2.0], [13.0, 7.0, 3.0], tenor=2.0))
    lo, hi = p.bounds[p.n_call + p.n_put + 1]
    assert lo == pytest.approx(np.exp(-2.0)) and hi == 1.0


def test_call_price_is_capped_by_forward_product():
    p = noarb.build(make_slice([12.0, 6.0, 2.0], [13.0, 7.0, 3.0]))
    row = p.A_ub[p.labels.index("call_upper")]
    iu = p.n_call + p.n_put
    assert row[0] == 1.0 and row[iu] == -1.0  # C <= u


def test_call_price_is_floored_by_forward_minus_discounted_strike():
    p = noarb.build(make_slice([12.0, 6.0, 2.0], [13.0, 7.0, 3.0]))
    row = p.A_ub[p.labels.index("call_lower")]
    iu, iv = p.n_call + p.n_put, p.n_call + p.n_put + 1
    assert row[0] == -1.0 and row[iu] == 1.0 and row[iv] == pytest.approx(-90.0)


def test_put_price_is_capped_by_discounted_strike():
    p = noarb.build(make_slice(
        [12.0, 6.0, 2.0], [13.0, 7.0, 3.0],
        put_lo=[1.0, 5.0, 11.0], put_hi=[2.0, 6.0, 12.0],
    ))
    row = p.A_ub[p.labels.index("put_upper")]
    j, iv = p.n_call, p.n_call + p.n_put + 1
    assert row[j] == 1.0 and row[iv] == pytest.approx(-90.0)  # P <= v*K


def test_put_price_is_floored_by_discounted_strike_minus_forward():
    p = noarb.build(make_slice(
        [12.0, 6.0, 2.0], [13.0, 7.0, 3.0],
        put_lo=[1.0, 5.0, 11.0], put_hi=[2.0, 6.0, 12.0],
    ))
    row = p.A_ub[p.labels.index("put_lower")]
    j = p.n_call
    iu, iv = p.n_call + p.n_put, p.n_call + p.n_put + 1
    assert row[j] == -1.0 and row[iv] == pytest.approx(90.0) and row[iu] == -1.0


def test_call_prices_are_non_increasing_in_strike():
    p = noarb.build(make_slice([12.0, 6.0, 2.0], [13.0, 7.0, 3.0]))
    row = p.A_ub[p.labels.index("call_monotone")]
    assert row[0] == -1.0 and row[1] == 1.0  # C_next - C_prev <= 0


def test_put_prices_are_non_decreasing_in_strike():
    p = noarb.build(make_slice(
        [12.0, 6.0, 2.0], [13.0, 7.0, 3.0],
        put_lo=[1.0, 5.0, 11.0], put_hi=[2.0, 6.0, 12.0],
    ))
    row = p.A_ub[p.labels.index("put_monotone")]
    j = p.n_call
    assert row[j] == 1.0 and row[j + 1] == -1.0  # P_prev - P_next <= 0


def test_call_vertical_spread_is_capped_by_discounted_strike_gap():
    p = noarb.build(make_slice([12.0, 6.0, 2.0], [13.0, 7.0, 3.0]))
    row = p.A_ub[p.labels.index("call_vertical")]
    iv = p.n_call + p.n_put + 1
    # C_prev - C_next <= v*dK; v's coefficient must be negative to bound the gap
    assert row[0] == 1.0 and row[1] == -1.0 and row[iv] == pytest.approx(-10.0)


def test_put_vertical_spread_is_capped_by_discounted_strike_gap():
    p = noarb.build(make_slice(
        [12.0, 6.0, 2.0], [13.0, 7.0, 3.0],
        put_lo=[1.0, 5.0, 11.0], put_hi=[2.0, 6.0, 12.0],
    ))
    row = p.A_ub[p.labels.index("put_vertical")]
    j = p.n_call
    iv = p.n_call + p.n_put + 1
    # P_next - P_prev <= v*dK; v's coefficient must be negative to bound the gap
    assert row[j] == -1.0 and row[j + 1] == 1.0 and row[iv] == pytest.approx(-10.0)
