"""The single point where a price stops being coin-denominated (ADR 0001).

Deribit quotes option premiums in the underlying coin. Every money column
produced here ends in `_usd`, and no coin-denominated price leaves this module,
so a unit error downstream has nowhere to hide.

Premiums are converted at the **expiry forward**, not at the spot index. These
are inverse options paying max(S-K,0)/S coin, so in coin terms C - P = (F-K)/F;
multiplying by F is what yields the textbook C - P = F - K that every
price-space no-arbitrage bound assumes. Measured on the live surface, the
forward reproduces parity to 5 ppm against 855 ppm for the index, and the gap
between them is a term structure rather than a constant rescale — so the index
would leave convexity intact but bias the calendar condition. `index_usd` is
kept alongside as the cash rate, which is what the basis is measured against.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import NamedTuple

import pyarrow as pa

from vsa.instruments import parse_instrument

DAYS_PER_YEAR = 365.0  # Deribit's own convention; stated rather than assumed

SCHEMA = pa.schema([
    ("currency", pa.string()),
    ("snapshot_ts", pa.timestamp("us", tz="UTC")),
    ("instrument_name", pa.string()),
    ("expiry_ts", pa.timestamp("us", tz="UTC")),
    ("strike_usd", pa.float64()),
    ("option_type", pa.string()),
    ("tenor_years", pa.float64()),
    ("bid_usd", pa.float64()),
    ("ask_usd", pa.float64()),
    ("mid_usd", pa.float64()),
    ("mark_usd", pa.float64()),
    ("index_usd", pa.float64()),
    ("forward_usd", pa.float64()),
    ("underlying_index", pa.string()),
    ("mark_iv", pa.float64()),
    ("open_interest", pa.float64()),
    ("volume", pa.float64()),
    ("volume_usd", pa.float64()),
    ("interest_rate", pa.float64()),
    ("latency_s", pa.float64()),
])


class Normalised(NamedTuple):
    rows: list[dict]
    skipped: list[str]  # names that are not dated options; the universe churns


def _usd(coin_price: float | None, forward_usd: float) -> float | None:
    return None if coin_price is None else coin_price * forward_usd


def normalise_snapshot(record: dict) -> Normalised:
    """One recorder line -> one USD quote row per instrument on that surface."""
    snapshot_ts = datetime.fromtimestamp(record["sent_at"], timezone.utc)
    latency_s = record["received_at"] - record["sent_at"]
    currency = record["currency"]

    rows: list[dict] = []
    skipped: list[str] = []

    for q in record["result"]:
        name = q["instrument_name"]
        try:
            inst = parse_instrument(name)
        except ValueError:
            skipped.append(name)
            continue

        forward_usd = q["underlying_price"]  # the F in Black-76, and the rate
        bid_usd = _usd(q["bid_price"], forward_usd)
        ask_usd = _usd(q["ask_price"], forward_usd)
        mark_iv = q["mark_iv"]

        rows.append({
            "currency": currency,
            "snapshot_ts": snapshot_ts,
            "instrument_name": name,
            "expiry_ts": inst.expiry_ts,
            "strike_usd": inst.strike_usd,
            "option_type": inst.option_type,
            "tenor_years": (inst.expiry_ts - snapshot_ts).total_seconds()
            / (DAYS_PER_YEAR * 86_400.0),
            "bid_usd": bid_usd,
            "ask_usd": ask_usd,
            "mid_usd": None if bid_usd is None or ask_usd is None else (bid_usd + ask_usd) / 2.0,
            "mark_usd": _usd(q["mark_price"], forward_usd),
            "index_usd": q["estimated_delivery_price"],
            "forward_usd": forward_usd,
            "underlying_index": q["underlying_index"],
            "mark_iv": None if mark_iv is None else mark_iv / 100.0,  # % -> fraction
            "open_interest": q["open_interest"],
            "volume": q["volume"],
            "volume_usd": q["volume_usd"],
            "interest_rate": q["interest_rate"],
            "latency_s": latency_s,
        })

    return Normalised(rows, skipped)
