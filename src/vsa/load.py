"""Decode raw gzipped snapshots into partitioned Parquet.

Incremental by design: the recorder keeps appending while the analysis is being
written, so a source file is reconverted only when its bytes have changed. The
current hour is therefore picked up again on every run, at the cost of rewriting
one file.

Layout is `<CURRENCY>/<YYYY-MM-DD>/<HH>.parquet` — plain directories rather than
hive `key=value` ones, so `currency` stays an ordinary column instead of one
DuckDB would also synthesise from the path and surface twice.
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterator, NamedTuple

import pyarrow as pa
import pyarrow.parquet as pq

from vsa.normalise import SCHEMA, normalise_snapshot

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"
PARQUET_DIR = Path(__file__).resolve().parents[2] / "data" / "parquet"

MANIFEST = "_manifest.json"
_SOURCE = re.compile(r"^booksummary_(\d{4})(\d{2})(\d{2})T(\d{2})\.jsonl\.gz$")


class LoadReport(NamedTuple):
    converted: list[str]
    skipped: list[str]
    rows: int
    unparseable: dict[str, int]


def read_snapshots(path: Path) -> Iterator[dict]:
    """Yield every snapshot in an hour file.

    record.py appends, so each file is a multi-member gzip stream of ~60
    members. gzip.open spans them all; a reader that stops at the first member
    returns one snapshot instead of sixty and raises nothing.
    """
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def load(raw_dir: Path = RAW_DIR, out_dir: Path = PARQUET_DIR, *, force: bool = False) -> LoadReport:
    """Convert every raw hour file that has changed since the last run."""
    raw_dir, out_dir = Path(raw_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = _read_manifest(out_dir)

    converted: list[str] = []
    skipped: list[str] = []
    total = 0
    unparseable: Counter[str] = Counter()

    for src in sorted(raw_dir.glob("booksummary_*.jsonl.gz")):
        if not _SOURCE.match(src.name):
            continue
        stat = src.stat()
        seen = manifest.get(src.name)
        if not force and seen and (seen["size"], seen["mtime"]) == (stat.st_size, stat.st_mtime):
            skipped.append(src.name)
            continue

        rows, bad = _convert(src, out_dir)
        manifest[src.name] = {"size": stat.st_size, "mtime": stat.st_mtime, "rows": rows}
        converted.append(src.name)
        total += rows
        unparseable.update(bad)

    _write_manifest(out_dir, manifest)
    return LoadReport(converted, skipped, total, dict(unparseable))


def _convert(src: Path, out_dir: Path) -> tuple[int, Counter[str]]:
    """One hour file -> one Parquet file per currency it contains."""
    y, m, d, hour = _SOURCE.match(src.name).groups()
    by_currency: dict[str, list[dict]] = defaultdict(list)
    unparseable: Counter[str] = Counter()

    for snap in read_snapshots(src):
        result = normalise_snapshot(snap)
        by_currency[snap["currency"]].extend(result.rows)
        unparseable.update(result.skipped)

    rows = 0
    for currency, quotes in by_currency.items():
        dest = out_dir / currency / f"{y}-{m}-{d}" / f"{hour}.parquet"
        dest.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.Table.from_pylist(quotes, schema=SCHEMA), dest, compression="zstd")
        rows += len(quotes)
    return rows, unparseable


def _read_manifest(out_dir: Path) -> dict:
    path = out_dir / MANIFEST
    return json.loads(path.read_text()) if path.exists() else {}


def _write_manifest(out_dir: Path, manifest: dict) -> None:
    (out_dir / MANIFEST).write_text(json.dumps(manifest, indent=1, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=RAW_DIR)
    parser.add_argument("--out", type=Path, default=PARQUET_DIR)
    parser.add_argument("--force", action="store_true", help="reconvert every source file")
    args = parser.parse_args()

    report = load(args.raw, args.out, force=args.force)
    print(f"converted {len(report.converted)} file(s), skipped {len(report.skipped)} unchanged")
    print(f"{report.rows:,} quote rows -> {args.out}")
    if report.unparseable:
        print("unparseable instruments (universe churn — check before trusting counts):")
        for name, n in sorted(report.unparseable.items(), key=lambda kv: -kv[1])[:10]:
            print(f"  {name}  x{n:,}")


if __name__ == "__main__":
    main()
