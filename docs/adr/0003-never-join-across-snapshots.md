# No arbitrage test may combine quotes from different snapshots

A butterfly or vertical spread is only an arbitrage if all its legs are
simultaneously available. Deribit returns every instrument for an underlying in
a single API call, so a snapshot is internally consistent by construction; the
recorder writes each snapshot all-or-nothing to preserve that.

## Consequences

Cross-snapshot joins are legitimate for exactly one purpose — measuring how long
a violation persists — and that analysis operates on already-detected violations,
never on raw legs. A test that quietly joins across time will manufacture
violations out of ordinary price movement, and the resulting numbers will look
impressive and be worthless.
