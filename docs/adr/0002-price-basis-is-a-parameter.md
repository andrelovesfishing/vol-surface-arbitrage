# Every arbitrage test is parameterised by price basis

The project's headline finding is the difference between violations found on mid
prices and violations found on executable bid/ask prices. So no test hardcodes a
price source: each takes the price basis as an argument and the same test runs
under all of them.

## Consequences

Producing the primary result is a loop over price bases rather than a second
implementation, which removes the risk that the mid and executable code paths
diverge and make the comparison meaningless. Adding a further basis later — mark
price, or executable with a size haircut — costs nothing.
