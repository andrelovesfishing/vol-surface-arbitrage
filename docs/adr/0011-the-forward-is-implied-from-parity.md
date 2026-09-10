# The forward is implied from parity, not taken from the exchange

`underlying_price` is a mark, not a two-sided quote. Testing executable option
prices against a non-executable forward is exactly the basis mismatch this
project exists to measure, so put-call parity in its usual form is unusable.

Parity is instead written with the discount factor and the forward as unknowns:

    C(K) - P(K) = u - v*K,    v = df,  u = df*F

This stays linear in `(u, v)` and needs no external input. It also makes the
box spread implicit: parity at two strikes with `(u, v)` free is exactly
`(C(K1) - P(K1)) - (C(K2) - P(K2)) = df*(K2 - K1)`, which is tradeable in
options alone.

## Consequences

Every number in this branch derives from two-sided option quotes and nothing
else. `underlying_price` survives only as the coin-to-USD conversion at the
boundary (ADR 0007) and in the `mark_iv` reconciliation, where comparing
like with like requires the exchange's own inputs.

The regression always runs on mid prices, on every basis, so the tick
normaliser and the implied-vol inputs do not shift when the basis does.
