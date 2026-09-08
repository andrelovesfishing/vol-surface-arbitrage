"""Shared builders for Deribit-shaped test data."""
from __future__ import annotations

import gzip
import json
from datetime import datetime, timezone
from pathlib import Path

INDEX_USD = 79_357.47    # USD per coin: what a coin premium converts at
FORWARD_USD = 79_459.55  # the 8SEP26 future: deliberately != index

SNAPSHOT_TS = datetime(2026, 9, 7, 20, 0, tzinfo=timezone.utc)


def api_row(**over) -> dict:
    """One instrument as get_book_summary_by_currency returns it."""
    row = {
        "instrument_name": "BTC-8SEP26-90000-C",
        "bid_price": 0.1345,
        "ask_price": 0.1400,
        "mark_price": 0.137,
        "mark_iv": 54.07,
        "underlying_price": FORWARD_USD,
        "underlying_index": "BTC-8SEP26",
        "estimated_delivery_price": INDEX_USD,
        "interest_rate": 0.0,
        "open_interest": 8.2,
        "volume": 1.5,
        "volume_usd": 120.0,
        "quote_currency": "BTC",
    }
    row.update(over)
    return row


def snapshot(rows=None, *, currency="BTC", sent_at=SNAPSHOT_TS, latency=0.12) -> dict:
    """One recorder line: a whole-currency book at a single instant."""
    sent = sent_at.timestamp()
    return {
        "currency": currency,
        "sent_at": sent,
        "received_at": sent + latency,
        "schema_version": 1,
        "result": [api_row()] if rows is None else rows,
    }


def write_raw(path: Path, snapshots: list[dict]) -> Path:
    """Append snapshots exactly as record.py does: one gzip member each."""
    for snap in snapshots:
        with gzip.open(path, "ab") as fh:
            fh.write((json.dumps(snap) + "\n").encode("utf-8"))
    return path
