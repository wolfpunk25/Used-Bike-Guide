# How prices in this guide are set — and a decision editorial needs to make

## The two possible meanings of a price range

Cross-checking against the editorial top-100/top-50 lists (August 2026) surfaced a
systematic difference. Of 141 entries that matched on model *and* generation, 35
differed by 30% or more on the midpoint — and **32 of those 35 had our figure lower**.

That is not random error. It is two different definitions of "price":

| | What it means | Where it comes from |
|---|---|---|
| **Our ranges** | The full spread, from a rough runner to a good example | Budget-dealer stock lists, classified ads, auction results (which include projects and exclude retail margin) |
| **Editorial lists** | What a good, presentable example costs | Curated valuations of notable bikes |

Neither is wrong. They answer different questions. A reader asking "what's the
cheapest way into one of these?" wants ours. A reader asking "what should I expect
to pay for a decent one?" wants theirs.

## What has been done

Where the same bike and generation genuinely disagreed, the **top of our range has
been raised** toward the editorial figure while the **floor has been kept**, because
our floors are researched from real bottom-of-market stock and are defensible. That
widens the ranges so they span rough-to-good, which is what a buyer's guide should
show. 21 entries were adjusted this way on 2026-08-18.

Three entries where ours reads *higher* were left alone, because the difference is
explained by span rather than error: our Road Glide and Le Mans entries cover more
model years than the editorial rows they matched.

## The house style already answers this

Seven *Fast Bikes* / *Used Bike Guide* features supplied on 2026-08-18 settle the
question. The magazine's own comparison panels quote **two figures per bike**:

```
2004 KAWASAKI ZX-10R      Private: £4999   Dealer: £6000
2004 YAMAHA YZF-R1        Private: £4000   Dealer: £4800
2005 SUZUKI GSX-R1000 K5  Private: £4750   Dealer: £5500
```

So the established convention is **private sale to dealer forecourt** — not
rough-to-mint, and not a single "average". The features also use `Verdict: x/10`,
which matches the `verdict` field already in the database.

Checked against that convention, our ranges hold up well on modern bikes: four of
eight spot-checks span the magazine's private and dealer figures exactly, and the
other four were within a few hundred pounds (adjusted 2026-08-18). The mismatch is
concentrated in pre-2000 machines, where our floors came from auction and budget
sources that sit below any realistic private sale.

**Recommended:** relabel the two price fields as `private` and `dealer` to match
house style, and raise the floors on pre-2000 entries to a realistic private-sale
figure rather than a project price. That is a schema change plus a systematic pass
over roughly 150 older entries, so it should be a deliberate decision.

## The decision

**The guide should state, once and prominently, which convention its prices use.**
Right now they span rough-to-good. If editorial would rather quote "what you'll pay
for a good one", every floor in the book needs raising — that is a systematic change,
not a per-entry fix, and it should be a deliberate choice rather than something that
varies entry by entry depending on which source happened to be available.

A third option, and probably the best one for a buyers' guide: print **two figures** —
"project/rough" and "good example" — which is effectively what the data already holds.

## Provenance

Every entry carries a `source` and a `notes` field explaining where its figure came
from. Sources currently in use, roughly from cheapest-skewing to dearest-skewing:

- `own-classifieds` / `budget-dealer-list` — bottom of the market
- `iconic-auction+market` — auction hammer prices, no retail margin, projects included
- `uk-market-research` — published guides and classified asking prices
- `dealer-stock` / `dealer-inventory` — prepped, warranted forecourt stock
- `editorial-lists-2026` — curated values for good examples
