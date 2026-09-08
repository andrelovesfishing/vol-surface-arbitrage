"""Health check for the recorder. Run any time: python check.py

Answers one question: is the dataset being collected correctly right now?
"""
from __future__ import annotations

import glob
import gzip
import json
import time
from datetime import datetime, timezone
from pathlib import Path

RAW = Path(__file__).parent / "data" / "raw"


def main() -> None:
    files = sorted(glob.glob(str(RAW / "*.jsonl.gz")))
    if not files:
        print("NO DATA. Is the recorder running?")
        return

    snaps = [json.loads(line) for f in files for line in gzip.open(f, "rt")]
    size_mb = sum(Path(f).stat().st_size for f in files) / 1e6

    print(f"{len(files)} hourly files, {size_mb:.1f} MB on disk")

    for cur in ("BTC", "ETH"):
        rows = [s for s in snaps if s["currency"] == cur]
        if not rows:
            print(f"{cur}: none")
            continue
        ts = [s["sent_at"] for s in rows]
        age = time.time() - ts[-1]
        gaps = [b - a for a, b in zip(ts, ts[1:])]
        stalled = [g for g in gaps if g > 90]
        covered = sum(g for g in gaps if g <= 90) / 3600

        status = "LIVE" if age < 150 else f"STALE ({age/60:.0f} min old)"
        print(
            f"\n{cur}: {status}\n"
            f"  snapshots      {len(rows)}\n"
            f"  newest         {datetime.fromtimestamp(ts[-1], timezone.utc):%Y-%m-%d %H:%M:%S} UTC ({age:.0f}s ago)\n"
            f"  instruments    {len(rows[-1]['result'])}\n"
            f"  clean coverage {covered:.1f} h across {len(stalled)} gap(s)"
        )
        if stalled:
            worst = max(stalled)
            print(f"  longest gap    {worst/3600:.1f} h  <- laptop asleep or recorder stopped")

    last = [s for s in snaps if s["currency"] == "BTC"][-1]["result"]
    two = [x for x in last if x.get("bid_price") and x.get("ask_price")]
    crossed = [x for x in two if x["bid_price"] > x["ask_price"]]
    print(
        f"\nnewest BTC snapshot: {len(two)}/{len(last)} two-sided, "
        f"{len(crossed)} crossed, underlying ${last[0]['underlying_price']:,.0f}"
    )
    if crossed:
        print("  crossed quotes present - investigate before trusting executable-price results")


if __name__ == "__main__":
    main()
