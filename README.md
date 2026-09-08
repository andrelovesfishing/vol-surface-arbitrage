# How much crypto options arbitrage is real?

Static no-arbitrage conditions are violated constantly on a live quoted options
surface. Almost none of those violations are tradeable. This project measures
the gap.

**Status: metrics pre-registered, data collection running, analysis not yet written.**
Headline numbers will be filled in below. They are not being chosen after the fact
— see [ADR 0006](docs/adr/0006-metrics-pre-registered.md).

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
