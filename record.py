"""Append-only recorder for Deribit option book summaries.

Polls the public `get_book_summary_by_currency` endpoint for every live BTC and
ETH option and appends the raw, unmodified response to a gzipped JSONL file.

Design notes (see docs/adr/0001 and docs/adr/0003):
  - The response body is stored verbatim. No parsing, no unit conversion, no
    field selection. Normalisation happens at load time, not here.
  - One API call returns every instrument, so all quotes in a snapshot share a
    single instant. That consistency is what makes cross-strike tests valid,
    so a snapshot is written all-or-nothing.
  - DVOL is deliberately NOT recorded: its history is retrievable after the
    fact via get_volatility_index_data, so recording it now buys nothing.

Usage:
    python record.py            # run forever, 60s interval
    python record.py --once     # single snapshot, for smoke-testing
    python record.py --interval 30
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://www.deribit.com/api/v2/public/get_book_summary_by_currency"
CURRENCIES = ("BTC", "ETH")
RAW_DIR = Path(__file__).parent / "data" / "raw"
USER_AGENT = "vol-surface-arbitrage/0.1 (research; contact via github)"

log = logging.getLogger("record")


def fetch(currency: str, timeout: float = 30.0) -> dict:
    """Fetch one currency's full option book summary.

    Returns a record wrapping the raw API result with the timestamps that
    bracket the request, so staleness can be bounded at analysis time.
    """
    url = f"{API}?currency={currency}&kind=option"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    sent = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    received = time.time()

    if "result" not in body:
        raise ValueError(f"unexpected response for {currency}: {list(body)[:5]}")

    return {
        "currency": currency,
        "sent_at": sent,
        "received_at": received,
        "schema_version": 1,
        "result": body["result"],
    }


def write_snapshot(records: list[dict]) -> Path:
    """Append a complete snapshot to the current hour's gzipped JSONL file.

    Written all-or-nothing: a partial snapshot (one currency succeeded, the
    other failed) is discarded rather than persisted, so every stored snapshot
    is internally consistent.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    hour = datetime.now(timezone.utc).strftime("%Y%m%dT%H")
    path = RAW_DIR / f"booksummary_{hour}.jsonl.gz"
    payload = b"".join(
        (json.dumps(r, separators=(",", ":")) + "\n").encode("utf-8") for r in records
    )
    with gzip.open(path, "ab", compresslevel=6) as fh:
        fh.write(payload)
    return path


def snapshot_once() -> bool:
    """Take and persist one snapshot. Returns True if it was written."""
    records = []
    for currency in CURRENCIES:
        try:
            records.append(fetch(currency))
        except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError) as exc:
            log.warning("fetch failed for %s (%s); discarding snapshot", currency, exc)
            return False

    path = write_snapshot(records)
    counts = ", ".join(f"{r['currency']}={len(r['result'])}" for r in records)
    log.info("wrote snapshot (%s) -> %s", counts, path.name)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interval", type=float, default=60.0, help="seconds between snapshots")
    parser.add_argument("--once", action="store_true", help="take a single snapshot and exit")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    if args.once:
        raise SystemExit(0 if snapshot_once() else 1)

    log.info("recording every %.0fs into %s; Ctrl-C to stop", args.interval, RAW_DIR)
    consecutive_failures = 0
    while True:
        started = time.monotonic()
        if snapshot_once():
            consecutive_failures = 0
        else:
            consecutive_failures += 1

        # Back off on sustained failure so an outage doesn't hammer the API,
        # but never exit: an unattended recorder that dies loses the dataset.
        backoff = min(2 ** consecutive_failures, 16) if consecutive_failures else 1
        elapsed = time.monotonic() - started
        time.sleep(max(0.0, args.interval * backoff - elapsed))


if __name__ == "__main__":
    main()
