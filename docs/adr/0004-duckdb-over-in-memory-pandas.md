# Analysis queries Parquet through DuckDB rather than loading into pandas

A week of 60-second snapshots across 1,812 instruments is roughly 18 million
quote rows. Raw gzipped JSONL is decoded once into partitioned Parquet, and
analysis runs as DuckDB SQL over those files.

## Consequences

The dataset stops being bounded by laptop RAM, which matters because the
recorder keeps growing the dataset while the analysis is being written. pandas
remains the right tool downstream of aggregation, where results are small.
