# Auto-Fix Examples

Touchstone only fixes a row when the correct answer is derivable from a trusted reference. Otherwise it holds the row for a human.

## RENAMED: Identity Fix

Input:

```json
{"id":"r3","entity_name":"Square, Inc.","ticker":"SQ","cusip":"852234103"}
```

Trusted lookup:

```text
CUSIP 852234103 -> Block, Inc. / XYZ
former ticker SQ retired 2025-01-21
```

Output:

```text
FIXED identity
SQ / Square, Inc. -> XYZ / Block, Inc.
why: renamed identity corrected: SQ -> XYZ (Block, Inc.)
```

## WRONG UNITS: Currency Fix

Input:

```json
{"id":"r8","entity_name":"Samsung Electronics Co Ltd","ticker":"005930.KS","shares":130000,"value_usd":8799120000}
```

Trusted lookup:

```text
price = 52.00 USD
expected USD value = 130000 * 52.00 = 6760000
observed / expected = 1302
KRW FX rate = 1302
```

Output:

```text
FIXED value_usd
8799120000 -> 6760000
why: converted from KRW to USD: $6.8M
```

## NO PROOF: Headline Claim Fix

Input:

```json
{"id":"r7","source":"news_claim","entity_name":"Apple Inc.","claimed_value":500000000}
```

Trusted lookup:

```text
official filed value = 250000 shares * 193.45 = 48362500
```

Output:

```text
FIXED claimed_value
500000000 -> 48362500
why: claim corrected to the filed figure: $48.4M
```

## RECOMPUTE: Value Fix

When `shares * pinned price` differs from the reported value and the ratio is not a novel unknown pattern, Touchstone replaces the value with the recomputed amount.

```text
FIXED value_usd
old reported value -> shares * PRICE_FEED[(ticker, as_of_date)]
why: value recomputed from shares x price
```

## HOLD Instead Of Guess

Touchstone does not auto-fix:

- `OUTDATED`: a corrected filing exists, so a human should load the corrected filing.
- `STUCK`: the feed is frozen, so there is no fresh source value to trust.
- missing CUSIP reference: the identity cannot be proven from the current snapshot.
- arbitrary ticker mismatch: CUSIP points elsewhere, but there is no known retired ticker mapping.

