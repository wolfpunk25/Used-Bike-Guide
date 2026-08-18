# The four price commands

Run all of these from the repo root:
`cd "/Users/darrenhendley/Documents/Claude/Used Bike Guide"`

They form a loop: **check what's due → generate a worksheet → apply the researched
prices → validate before it ships.**

---

## 1. What state are the prices in?

```bash
python3 scripts/refresh_prices.py status
```

Shows entry count, current issue, when prices were last refreshed, the confidence
breakdown, which entries need attention, how stale the figures are, and which decades
still have gaps. Read-only — it changes nothing. Start here.

## 2. Generate a worksheet for a batch

```bash
python3 scripts/refresh_prices.py worksheet --year-from 2010 --year-to 2014 --todo
```

Writes `data/price-worksheet.csv` with one row per bike: its current private and dealer
figures, plus empty `new_private` / `new_dealer` / `source` / `notes` columns to fill in.

- `--todo` skips anything already researched
- also takes `--make Triumph` or `--category Enduro`
- omit the year flags for the whole guide

Keep batches to 40–60 so each one stays reviewable.

## 3. Apply the researched prices

```bash
python3 scripts/refresh_prices.py apply --file data/price-worksheet.csv --issue "2026 Q4"
```

Reads the filled-in worksheet back. Rows left blank are skipped, so it can be run
repeatedly as a batch is worked through. The outgoing price is archived into
`price_history`, which is what drives the **Change** column quarter on quarter.

## 4. Check it before it ships

```bash
python3 scripts/validate.py
```

Fails on missing fields, duplicate IDs, verdicts outside 1–10, reversed year or price
ranges, and unknown confidence values. Warns on over-long descriptions that would
overrun the layout box. **Run this before every push** — it is the last thing between a
bad edit and the printed page.

---

## The full quarterly loop

```bash
python3 scripts/refresh_prices.py status
python3 scripts/refresh_prices.py worksheet --year-from 1990 --year-to 1999 --todo
# ... research and fill in data/price-worksheet.csv ...
python3 scripts/refresh_prices.py apply --file data/price-worksheet.csv --issue "2026 Q4"
python3 scripts/validate.py
git add -A && git commit -m "Q4 price refresh: 1990s" && git push
```

The push publishes automatically — GitHub Pages serves from the `main` branch.
