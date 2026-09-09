"""Shared builders for Deribit-shaped test data."""
from __future__ import annotations

import gzip
import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pyarrow as pa

from vsa.normalise import SCHEMA

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


EXPIRY_TS = datetime(2026, 9, 8, 8, tzinfo=timezone.utc)  # 12h after SNAPSHOT_TS


def quote_row(strike, bid, ask, **over) -> dict:
    """One quote as it exists *after* loading: USD, Parquet-shaped."""
    row = dict.fromkeys(SCHEMA.names)
    row.update({
        "currency": "BTC",
        "snapshot_ts": SNAPSHOT_TS,
        "instrument_name": f"BTC-8SEP26-{int(strike)}-C",
        "expiry_ts": EXPIRY_TS,
        "strike_usd": float(strike),
        "option_type": "C",
        "tenor_years": (EXPIRY_TS - SNAPSHOT_TS).total_seconds() / (365.0 * 86_400.0),
        "bid_usd": bid,
        "ask_usd": ask,
        "mid_usd": None if bid is None or ask is None else (bid + ask) / 2.0,
        "mark_usd": None if bid is None or ask is None else (bid + ask) / 2.0,
        "index_usd": INDEX_USD,
        "forward_usd": FORWARD_USD,
        "underlying_index": "BTC-8SEP26",
        "interest_rate": 0.0,
    })
    row.update(over)
    return row


def surface(mids: dict, *, half_spread: float = 0.0, **over) -> list[dict]:
    """A synthetic surface: strike -> mid price, quoted with a symmetric spread."""
    return [quote_row(k, mid - half_spread, mid + half_spread, **over) for k, mid in mids.items()]


def quotes_con(rows: list[dict]):
    """DuckDB exposing `quotes` over synthetic rows, typed exactly as the real view."""
    con = duckdb.connect()
    con.register("_synthetic", pa.Table.from_pylist(rows, schema=SCHEMA))
    con.execute("CREATE VIEW quotes AS SELECT * FROM _synthetic")
    return con
