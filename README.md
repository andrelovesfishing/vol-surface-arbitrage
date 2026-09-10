# How much crypto options arbitrage is real?

Static no-arbitrage conditions are violated constantly on a live quoted options
surface. Almost none of those violations are tradeable. This project measures
the gap.

**Status: complete. Every pre-registered metric is measured; results below.**
None of these numbers was chosen after the fact — see
[ADR 0006](docs/adr/0006-metrics-pre-registered.md) and
[ADR 0010](docs/adr/0010-band-feasibility-is-pre-registered.md).

---

## The question

An options surface must satisfy conditions that follow from arbitrage alone,
with no model attached: prices must be convex in strike, spreads must be bounded
by the strike difference, and total implied variance must not decrease with tenor.
When quoted prices break these conditions, it looks like free money.

Usually it isn't. The violation is measured on mid prices, which nobody can
trade at, and it evaporates the moment you have to buy at the ask and sell at
the bid. This project quantifies how much evaporates, and what is left.

## Pre-registered metrics

Fixed before analysis. See [ADR 0006](docs/adr/0006-metrics-pre-registered.md).

**Primary** — the fraction of adjacent-strike butterflies within a snapshot that
violate convexity, computed on mid prices and on executable prices, broken down
by tenor bucket. The reported result is the ratio between the two: the share of
apparent arbitrage that is spread illusion.

**Secondary** — persistence: for violations that survive on executable prices,
how many consecutive 60-second snapshots they remain visible for.

**Null result** — that executable violations are approximately zero, and that
mid-price violations are entirely explained by spread width and quote staleness.
This is a publishable outcome, not a failure. It is also the expected one.

**Robustness** — the primary metric is computed independently on BTC and on ETH.
Disagreement between them is reported, not reconciled.

### Band feasibility (added 2026-09-10, pre-registered before running)

Counting violating triples asks whether any individual triple of quotes is
inconsistent. The stronger question is whether the quotes are collectively
consistent: does a single arbitrage-free surface lie inside every quoted
bid/ask at once? See [ADR 0010](docs/adr/0010-band-feasibility-is-pre-registered.md).

**Primary** — the share of slices whose band admits such a surface, on mid and
on executable, per currency, and how far the band would have to widen where it
does not.

**Prediction** — executable bands admit one essentially everywhere; mid bands
widely do not. An executable slice that fails is a multi-leg arbitrage no
triple test can see.

The forward used throughout is implied from put-call parity rather than taken
from the exchange ([ADR 0011](docs/adr/0011-the-forward-is-implied-from-parity.md)).

## Results

Measured over **5,284,244 quotes in 6,194 snapshots**, 2026-09-06 21:10 to
2026-09-10 12:50 UTC. BTC and ETH are computed independently throughout.

### Convexity: all of the apparent arbitrage is spread illusion

A *butterfly* is three adjacent strikes; convexity says the middle option cannot
cost more than the straight line between its two neighbours. Counted first on mid
prices, then on executable prices — wings bought at the ask, body sold at the bid.

| | butterflies | violating at mid | violating executable | illusion share |
|---|---|---|---|---|
| BTC | 2,516,346 | 233,926 (9.30%) | **0** | **100%** |
| ETH | 2,149,426 | 198,883 (9.25%) | **0** | **100%** |

The *illusion share* is the pre-registered primary metric: the fraction of apparent
arbitrage that exists only because mid prices cannot be traded. It is 1.0000
exactly — on both underlyings, at every materiality floor, including a floor of
zero where a one-cent violation still counts.

| materiality floor | mid, BTC | mid, ETH | executable |
|---|---|---|---|
| 0 ticks | 413,469 (16.43%) | 289,193 (13.45%) | 0 |
| 1 tick | 233,926 (9.30%) | 198,883 (9.25%) | 0 |
| 2 ticks | 124,446 (4.95%) | 131,325 (6.11%) | 0 |

This is the null result pre-registered above, and it is the expected one. The
secondary persistence metric is undefined: nothing survived in order to persist.

### Band feasibility: one surface fits inside every executable band

A *slice* is one currency, one snapshot, one expiry. `t*` is how far that slice's
quoted band must widen, in either direction, before a single arbitrage-free surface
fits inside all of it at once. `t* = 0` means the band already admits one. A *tick*
is Deribit's quote increment, 0.0001 of a coin.

| basis | BTC clean | ETH clean | median `t*` where it fails |
|---|---|---|---|
| executable (bid to ask) | 34,316 / 34,316 (**100.000%**) | 34,311 / 34,311 (**100.000%**) | — |
| mark (Deribit's fitted price) | 0.017% | 0.035% | 0.16 / 0.09 ticks |
| mid (the midpoint) | 0.003% | 0.070% | 3.16 / 4.21 ticks |

Mid and mark are *zero-width* bands — a single price rather than a range — so
failing is close to definitional for them, which [ADR 0010](docs/adr/0010-band-feasibility-is-pre-registered.md)
states in advance. The informative quantity is therefore the magnitude, not the share,
and the magnitudes form a ladder: raw midpoints need three to four ticks of room,
Deribit's own fitted mark surface needs about a tenth of a tick, and the real quoted
band needs none at all. A detector that could not see arbitrage would not order those
three sensibly.

**Is 100% clean simply a wide band?** No. The executable half-spread has a median of
7.50 ticks on both underlyings, against the 3.16 / 4.21 ticks the mid surface needs —
so the room required is roughly half the room the market actually quotes, and in 83%
(BTC) and 79% (ETH) of slices the required widening fits inside the spread outright.
There is headroom, but it is not a landslide.

Exclusions are reported rather than dropped: 8 BTC and 2 ETH slices had too few
strikes to solve at all, and 33 to 52 violating slices per basis have no paired
call/put strike, hence no parity forward to scale their severity by. They stay in
the clean share and are counted separately.

### Calendar: the only executable exceptions, and they are not trades

Total implied variance (`w = sigma^2 x T`) must not fall as expiry lengthens. Because
strikes do not line up between expiries, the far slice is interpolated across the
overlap only, never extrapolated. The tradeable direction sells the near expiry at its
bid and buys the far at its ask, which is the direction that makes a violation hardest
to find.

| basis | BTC | ETH |
|---|---|---|
| mid | 8,732 / 1,028,363 (0.849%) | 8,569 / 897,529 (0.955%) |
| executable | 13 / 904,677 (0.0014%) | 107 / 785,207 (0.0136%) |

Those 120 are the only executable violations anywhere in this project, and the calendar
condition is the only cross-expiry test here — the band program works one expiry at a
time, so nothing else could have caught them.

They are not floating-point noise: the median shortfall is 30% of the far leg's total
variance and the largest is 21x it. But they are not trades either. They collapse into
15 expiry pairs across just 12 of the 6,194 snapshots, and a 21x variance inversion
between neighbouring expiries would not survive minutes on a live book. Both the size
and the concentration point at isolated stale or broken quotes rather than a standing
edge. Confirming that case by case is not attempted here.

### Our implied vol against Deribit's published `mark_iv`

A check that the vol solver is inverting the same prices Deribit thinks it is quoting.
Median absolute gap **0.089 vol points** on BTC (2,564,971 quotes, p90 1.76) and
**0.157** on ETH (2,174,797 quotes, p90 3.13). Quotes the solver could not invert are
counted, not silently dropped: 88,655 and 111,875 respectively.

### What it adds up to

On a liquid crypto options venue, static arbitrage that is visible on mid prices is
entirely an artefact of quoting midpoints nobody trades at. Every one of roughly
700,000 apparent convexity violations disappears once both legs must cross the spread,
and one arbitrage-free surface fits inside every executable band on both underlyings.
The only executable exceptions are a dozen cross-expiry quote anomalies. See
[Limitations](#limitations) for what this deliberately does not test.

## Data

Deribit public API, no account required. `get_book_summary_by_currency` returns
every live option on an underlying in a single call, which is what makes
cross-strike tests valid within an instant.

- 964 live BTC options, 848 ETH, across 12 expiries and 94 strikes
- 902 of 964 carry two-sided quotes
- Recorded at 60-second intervals into append-only gzipped JSONL, ~105 MB/day

Quotes are denominated in the underlying coin, not USD — the main unit hazard in
the project, handled at exactly one point in the code ([ADR 0001](docs/adr/0001-immutable-raw-snapshots.md)).

## Running the recorder

```
python record.py            # every 60s until interrupted
python record.py --once     # single snapshot, smoke test
```

## Design

- [CONTEXT.md](CONTEXT.md) — the vocabulary this project uses precisely
- [docs/adr/](docs/adr/) — why the architecture is the way it is

## Limitations

Stated up front rather than discovered by the reader.

- Depth is not recorded, only top of book, so violations are not tested against
  size. A violation that exists for 0.1 contracts is not a business.
- Fees, margin and the capital cost of holding the position to expiry are not modelled.
- Deribit only. Cross-exchange violations are a different and larger question.
