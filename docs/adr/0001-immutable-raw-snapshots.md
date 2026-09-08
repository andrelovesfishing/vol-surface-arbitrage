# Raw snapshots are immutable; normalisation happens at load time

The recorder stores the exact bytes the Deribit API returned, wrapped only in
the timestamps bracketing the request. No parsing, unit conversion or field
selection happens at record time. All interpretation — including the BTC-to-USD
conversion forced by Deribit's inverse quoting — lives in a single normalisation
function applied when data is loaded for analysis.

## Considered Options

Converting to USD and selecting fields at ingest was the obvious alternative and
would cut storage by roughly an order of magnitude. Rejected because a bug in
that conversion silently corrupts every snapshot already collected, and the data
cannot be re-collected: it is a live market that has moved on. The whole point of
starting the recorder early is that the dataset accumulates faster than the
analysis is written, so the analysis must be able to change without invalidating
the data.

## Consequences

Storage is ~105 MB/day for BTC and ETH combined at 60-second intervals.
Any analysis bug is fixable by re-running against untouched raw data.
There must be exactly one place in the codebase where a price stops being
BTC-denominated; scattering conversions defeats the design.
