"""Analysis entry point: one DuckDB view over every loaded snapshot."""
from __future__ import annotations

from pathlib import Path

import duckdb

from vsa.load import PARQUET_DIR


def connect(parquet_dir: Path = PARQUET_DIR) -> duckdb.DuckDBPyConnection:
    """A connection exposing `quotes`, the USD-denominated quote table.

    hive_partitioning is off deliberately: currency and time are real columns in
    the files, so letting DuckDB re-derive them from directory names would
    duplicate them. Row-group statistics still prune on snapshot_ts.
    """
    pattern = (Path(parquet_dir) / "**" / "*.parquet").as_posix()
    con = duckdb.connect()
    con.execute(
        f"CREATE VIEW quotes AS SELECT * FROM read_parquet('{pattern}', hive_partitioning=false)"
    )
    return con
