"""The primary metric, rendered: python analyse.py

Reports mid against executable prices per underlying and tenor bucket, then the
gap between them — the share of apparent arbitrage that is spread illusion.
Metrics are the pre-registered ones (ADR 0006); nothing here chooses a cut.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

from vsa.convexity import (
    PROFILE_DIMENSIONS, TICK_COIN, capture, capture_profile, headline, summarise,
)
from vsa.dataset import connect
from vsa.load import PARQUET_DIR

SENSITIVITY_TICKS = (0.0, 1.0, 2.0)  # the materiality floor is a judgement, so show it


def _coverage(con: duckdb.DuckDBPyConnection) -> str:
    n, snaps, first, last = con.sql(
        "SELECT count(*), count(DISTINCT snapshot_ts), min(snapshot_ts), max(snapshot_ts) FROM quotes"
    ).fetchone()
    return (f"{n:,} quotes | {snaps:,} snapshots | "
            f"{first:%Y-%m-%d %H:%M} -> {last:%Y-%m-%d %H:%M} UTC")


def render(con: duckdb.DuckDBPyConnection, *, min_ticks: float = 1.0) -> str:
    out = ["Convexity of the quoted surface", "=" * 31, _coverage(con),
           f"materiality floor: {min_ticks:g} tick ({TICK_COIN:g} coin per leg)", ""]

    for (currency,) in con.sql("SELECT DISTINCT currency FROM quotes ORDER BY 1").fetchall():
        h = headline(con, min_ticks=min_ticks, currency=currency)
        illusion = "n/a" if h.illusion_share is None else f"{h.illusion_share:.1%} of it is spread illusion"
        out += [
            currency,
            f"  mid         {h.mid_violations:>9,} of {h.butterflies:,} butterflies violate convexity ({h.mid_rate:.2%})",
            f"  executable  {h.executable_violations:>9,} of {h.butterflies:,} survive executable prices ({h.executable_rate:.2%})",
            f"  -> {illusion}",
            "",
            f"  {'basis':<12}{'tenor':<9}{'butterflies':>13}{'violations':>12}{'rate':>9}",
        ]
        for basis, bucket, n, viols, rate in summarise(
            con, min_ticks=min_ticks, currency=currency
        ).fetchall():
            out.append(f"  {basis:<12}{bucket:<9}{n:>13,}{viols:>12,}{rate:>9.2%}")
        out.append("")

        out.append("  violation rate against the materiality floor")
        for ticks in SENSITIVITY_TICKS:
            s = headline(con, min_ticks=ticks, currency=currency)
            share = "n/a" if s.illusion_share is None else f"{s.illusion_share:.1%} illusion"
            out.append(f"    {ticks:g} ticks: mid {s.mid_rate:>7.2%} -> executable {s.executable_rate:>7.2%}   ({share})")
        out.append("")

        c = capture(con, min_ticks=min_ticks, currency=currency)
        out.append("  spread an apparent violation would need you to capture")
        out.append(
            "    no mid violations to measure" if not c.n else
            f"    median {c.median:.1%}   (p10 {c.p10:.1%}, p90 {c.p90:.1%})"
            f"   over {c.n:,} mid violations"
        )
        out.append("")

        if c.n:
            out.append("  capture required by slice (descriptive, ADR 0009)")
            out.append(f"    {'dimension':<12}{'bucket':<12}{'violations':>12}{'median':>10}{'p10':>10}")
            for dim in PROFILE_DIMENSIONS:
                for bucket, n, med, p10 in capture_profile(
                    con, by=dim, min_ticks=min_ticks, currency=currency
                ).fetchall():
                    out.append(f"    {dim:<12}{bucket:<12}{n:>12,}{med:>10.1%}{p10:>10.1%}")
            out.append("")

    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parquet-dir", type=Path, default=PARQUET_DIR)
    ap.add_argument("--min-ticks", type=float, default=1.0)
    args = ap.parse_args()
    with connect(args.parquet_dir) as con:
        print(render(con, min_ticks=args.min_ticks))
