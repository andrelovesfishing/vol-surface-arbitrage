# Band feasibility and its metrics are pre-registered

This branch asks a new primary question — whether one arbitrage-free surface
fits inside the whole quoted band — so ADR 0006 applies to it in full. The
metrics and the expected outcome are fixed here, before any of it runs.

## Primary

The share of slices whose band admits an arbitrage-free surface (`t* = 0`), on
mid and on executable, per currency; and the distribution of `t*` in ticks
where it does not.

## Prediction, recorded before the fact

Executable bands admit an arbitrage-free surface essentially everywhere. Mid
bands widely do not. Any executable slice returning `t* > 0` is a multi-leg
arbitrage invisible to the triple test, and is the most interesting outcome
this branch can produce.

## Secondary

Solver-versus-oracle agreement, reported as a headline number (ADR 0005). The
`mark_iv` reconciliation: whether Deribit's published implied volatility is the
implied volatility of Deribit's own mark price. Calendar violation rates on
both bases.

## Robustness

BTC and ETH computed independently. Disagreement is reported, not reconciled.

## Consequences

Subsampling snapshots for runtime, if it ever becomes necessary, must be
pre-registered before it is run rather than adopted after seeing a clock.

Parity enters the LP as a hard equality, so on a zero-width band `t* > 0` is
close to guaranteed. That is the same statement the existing headline makes —
the mid surface is not a tradeable object — so the informative comparison is
the magnitude of `t*` on mid against executable, not the bare share of slices
that fail.
