# The convexity test is spacing-weighted, priced per body contract, above a one-tick floor

Three decisions inside the detector, none of them forced by the condition itself.

**Legs are weighted by strike spacing, not differenced (1, -2, 1).** For
K1 < K2 < K3 write K2 = w*K1 + (1-w)*K3; the trade is buy w of K1, buy (1-w) of
K3, sell one K2. Deribit's strike grid is dense near the money and sparse in the
wings, so equal weights on unequal spacing report ordinary convex surfaces as
violations — on a 2000/4000 grid, prices of 4000/2800/1000 are convex, while
differencing them gives -600.

**The position is normalised to one short body contract**, so a violation is
quoted in dollars per body. Under equal spacing this is half the textbook
butterfly. It keeps the number comparable across strike spacings, which the
textbook normalisation is not.

**A violation must exceed one tick.** Each of the three quotes is rounded to the
exchange tick (0.0001 coin, ~$8 on BTC at present), and the position holds two
contracts' worth, so rounding alone can fabricate up to one full tick of
apparent violation: 0.5 tick * (w + (1-w) + 1). The floor is exactly that bound,
not a tuned parameter, and `analyse.py` reports the metric at 0, 1 and 2 ticks
so the choice is visible rather than assumed.

**Every price basis is measured on one universe**: butterflies are formed only
from instruments quoted on both sides, and "adjacent" means adjacent within that
set. Otherwise the mid and executable counts would have different denominators
and their ratio — the project's headline number — would compare nothing.

## Consequences

The mid-price count includes butterflies whose legs carry absurd quotes: an
ETH-26MAR27-2000-C was seen with a 0.0001-coin bid against a 20-coin ask, and an
inverse call cannot be worth more than one coin. Its mid of 10 coin produces a
$24,683 "violation". These are not filtered out. A quote that wide is exactly
what the project claims mid prices are — a number nobody would trade at — and
removing them after seeing the data would be the metric drift ADR 0006 exists to
prevent. The same butterfly costs a large positive amount on executable prices,
which is the finding, not a nuisance.
