# Volatility Surface Arbitrage

Measures how often the live quoted options surface on Deribit violates
static no-arbitrage conditions, and how much of that apparent arbitrage
survives once you can only trade at real bid and ask prices.

## Language

### Market structure

**Instrument**:
One tradeable option contract, identified by underlying, expiry and strike
(e.g. `BTC-7SEP26-69000-C`). The atomic unit of the dataset.
_Avoid_: contract, option, ticker

**Snapshot**:
The complete set of quotes for every live instrument on one underlying,
retrieved in a single API call and therefore sharing one instant.
_Avoid_: tick, sample, observation

**Surface**:
The quoted prices across all strikes and expiries within a single snapshot.
A surface never spans snapshots.
_Avoid_: vol surface, smile, skew (these name features *of* a surface)

**Underlying Price**:
The reference price of the underlying at the moment of a snapshot, as reported
by the exchange alongside each quote.
_Avoid_: spot, index, mark

**Tenor**:
The time remaining until an instrument expires.
_Avoid_: maturity, expiry (reserve "expiry" for the dated event itself)

### Prices

**Executable Price**:
The price you would actually transact at: the ask when buying, the bid when
selling. The stricter of the two price bases.
_Avoid_: real price, tradeable price, touch

**Mid Price**:
The midpoint of bid and ask. A theoretical construct, not transactable.
_Avoid_: fair value, theo

**Mark Price**:
The exchange's own published valuation of an instrument. Used only as an
external reference to validate our own calculations against.
_Avoid_: settlement price

**Price Basis**:
Which of executable, mid or mark a given test is run against. Every
arbitrage test is parameterised by exactly one.
_Avoid_: price mode, price type

### The conditions being tested

**Violation**:
A single instance where a set of quotes within one snapshot breaks a static
no-arbitrage condition.
_Avoid_: opportunity, signal, edge

**Butterfly**:
Three instruments sharing an expiry at consecutive strikes. Its price must be
non-negative; a negative value is a convexity violation.
_Avoid_: fly, triplet, spread

**Convexity Condition**:
The requirement that option price is convex in strike within an expiry.
The project's primary test.
_Avoid_: butterfly condition, curvature

**Vertical Bound**:
The requirement that the price difference between two strikes in the same
expiry stays within the discounted strike difference.
_Avoid_: call spread bound, monotonicity

**Calendar Condition**:
The requirement that total implied variance is non-decreasing in tenor at a
fixed moneyness.
_Avoid_: term structure condition, time-spread bound

**Spread Illusion**:
A violation that appears on mid prices but disappears on executable prices.
The gap between the two counts is the project's headline finding.
_Avoid_: false positive, phantom arbitrage

**Persistence**:
How long a violation remains present across consecutive snapshots.
_Avoid_: lifetime, decay, half-life

### Calculation

**Implied Volatility**:
The volatility that reproduces an observed option price under Black-76.
Solved for by our own root-finder, not taken from the exchange.
_Avoid_: IV, vol (in prose; fine as a variable name)

**Total Implied Variance**:
Implied volatility squared multiplied by tenor. The quantity in which the
calendar condition is naturally stated.
_Avoid_: total variance, w

**Inverse Quoting**:
Deribit's convention of quoting option prices in units of the underlying
coin rather than USD. The source of the project's main unit hazard.
_Avoid_: coin-margined, crypto-quoted
