# The implied volatility solver is written from scratch, with libraries used only as an oracle

Implied volatility is inverted from Black-76 by our own root-finder rather than
by py_vollib or QuantLib. The libraries are used in tests as a reference oracle,
and the measured agreement is reported as a headline number.

## Considered Options

Calling a library is faster and less error-prone. Rejected for a specific
non-technical reason: this is a portfolio project whose purpose is to
demonstrate that the author can do the mathematics, and "I called a function"
does not survive interview questioning. The library is retained where it adds
real value — as an independent check that the hand-rolled solver is correct.

## Consequences

The primary convexity result does not depend on this solver at all, because
convexity is tested on prices rather than volatilities. The solver is on the
critical path only for the calendar condition and for validation, so a delay
here cannot block the headline finding.
