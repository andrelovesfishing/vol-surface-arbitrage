"""Deribit instrument names.

`BTC-8SEP26-90000-C` is the only place the API states an option's strike and
expiry, so every downstream group-by depends on parsing it correctly.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache

_NAME = re.compile(
    r"^(?P<currency>[A-Z]+)-(?P<day>\d{1,2})(?P<month>[A-Z]{3})(?P<year>\d{2})"
    r"-(?P<strike>\d+(?:\.\d+)?)-(?P<kind>[CP])$"
)
_MONTHS = {m: i for i, m in enumerate(
    "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split(), start=1)}

EXPIRY_HOUR_UTC = 8  # Deribit options expire at 08:00 UTC


@dataclass(frozen=True, slots=True)
class Instrument:
    currency: str
    expiry_ts: datetime
    strike_usd: float
    option_type: str  # "C" or "P"


@lru_cache(maxsize=None)
def parse_instrument(name: str) -> Instrument:
    """Cached: ~1,800 distinct names recur across millions of quote rows."""
    m = _NAME.match(name)
    if m is None or m["month"] not in _MONTHS:
        raise ValueError(f"not a dated option: {name}")
    return Instrument(
        currency=m["currency"],
        expiry_ts=datetime(
            2000 + int(m["year"]), _MONTHS[m["month"]], int(m["day"]),
            EXPIRY_HOUR_UTC, tzinfo=timezone.utc,
        ),
        strike_usd=float(m["strike"]),
        option_type=m["kind"],
    )
