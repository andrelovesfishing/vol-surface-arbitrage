# Coin premiums are converted to USD at the expiry forward, not the spot index

Deribit quotes premiums in the underlying coin, and the snapshot carries two
plausible rates to convert them with: `estimated_delivery_price`, the spot index
(USD per coin), and `underlying_price`, the price of the future for that
instrument's expiry. Normalisation uses the forward.

## Considered Options

The index is the intuitive choice — it is what the premium is worth in cash at
the moment it is paid — and it was the first implementation. It is wrong for
this project's purposes.

These are inverse options: a call pays `max(S-K,0)/S` in coin, so in coin terms
`C - P = (F-K)/F`. Multiplying by `F` is exactly what turns that into the
textbook `C - P = F - K`, which is the form every price-space no-arbitrage bound
assumes, and the form Black-76 prices with `r = 0`.

The choice was settled empirically rather than by argument. Reconstructing the
forward from put-call parity on the exchange's own mark prices, across 635,000
call/put pairs in the first day of recording:

| conversion rate | median error vs recorded forward |
|---|---|
| expiry forward | 5 ppm (BTC), 13 ppm (ETH) |
| spot index | 855 ppm |

The 855 ppm is the futures basis, and it is a term structure — roughly -170 ppm
at the front expiry, widening with tenor — not a constant rescale.

## Consequences

Convexity, the primary metric, is unaffected either way: it is tested within one
expiry, where the two rates differ by a factor constant across strikes, and
convexity is scale-invariant. The choice matters for everything else. The
vertical bound is not scale-invariant. The calendar condition compares across
expiries, which is precisely where the basis varies, so the index would have
introduced a tenor-dependent distortion into the one test designed to measure a
tenor-dependent quantity. Implied volatilities inverted from index-converted
prices would carry the same bias.

`index_usd` is retained on every row as the cash rate, so the basis stays
measurable and the decision stays auditable. Parity agreement at 5 ppm is
reportable as a validation of the loader in its own right.
