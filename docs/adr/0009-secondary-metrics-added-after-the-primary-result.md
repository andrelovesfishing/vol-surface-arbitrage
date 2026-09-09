# Metrics added after the primary result are reported as descriptive, not pre-registered

The spread-capture metric was written after the primary result was known. So was
the attribution of mid violations to spread width and liquidity. Neither is in
the README's pre-registration (ADR 0006), and neither is presented as though it
were.

Both are reported under their own heading, after the pre-registered metrics, and
described as descriptive. The primary metric and its result are not restated,
re-cut or re-thresholded to accommodate them.

This is the same rule the secondary metric already forced: persistence was
pre-registered over violations that survive executable prices, that population
is empty, and the honest response is to report the empty population rather than
quietly substitute a different one.

## Consequences

Adding a metric after seeing the data is exactly the drift ADR 0006 exists to
prevent, so the distinction has to be visible rather than assumed — a reader
cannot otherwise tell which numbers were committed to in advance and which were
chosen once the answer was known.

What makes these two admissible is that neither can change the primary result.
Spread capture is a reparameterisation of it: paying the spread on every leg
costs `cost_executable - cost_mid`, so the capture ratio is
`cost_executable / (cost_executable - cost_mid)`, and "zero executable
violations" is precisely that ratio staying below one everywhere. The same fact,
as a distribution instead of a count. Attribution conditions the mid violations
on observables and likewise leaves the counts untouched.

A metric that *could* move the headline does not get this treatment. It waits
for the next pre-registration.
