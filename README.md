# Used Bike Guide — listings database

An internal database and browser for the quarterly *Used Bike Guide* relaunch. Editorial
content (verdict, write-up, plus/minus points) is written once and reused; only the price
data is refreshed each issue. The front end sorts and filters, and exports a CSV in the
magazine's field order for the page-design stage.

30 bikes are seeded to get you started. **All seed prices are unverified estimates** and
must be refreshed before anything goes to press — the app flags this at the top of the page.

---

## Running it

```bash
python3 -m http.server 8000
```

Then open <http://localhost:8000>. It has to be served over HTTP — opening `index.html`
straight from Finder won't work, because browsers block the data file from `file://`.

## Deploying

Push to `main` and the `deploy.yml` workflow validates the data and publishes to GitHub
Pages. In the repo settings, set **Pages → Source → GitHub Actions** once.

### One thing to know about "internal"

A GitHub Pages site is **publicly readable even when the repository is private**. Making
the site itself private needs GitHub Enterprise Cloud. So pick one:

| Option | Internal? | Effort |
|---|---|---|
| Run locally with the command above | Yes | None — repo stays private, nothing published |
| GitHub Pages, public URL | No — obscure, not secret | Already set up |
| GitHub Pages + Enterprise Cloud access control | Yes | Needs the Enterprise plan |
| Cloudflare Pages / Netlify with password protection | Yes | ~15 minutes to switch hosts |

The page carries a `noindex` tag so it won't turn up in search results, but treat the
public-Pages option as "unlisted", not "private". If the price research is commercially
sensitive, run it locally or move to a host with a password.

---

## The quarterly price refresh

Two routes. They write to the same place and can be mixed.

### Route 1 — assisted research (what you asked for)

This is the "ask Claude every couple of months" workflow.

```bash
python3 scripts/refresh_prices.py worksheet
```

That writes `data/price-worksheet.csv`: one row per bike with its current price and empty
`new_low` / `new_high` / `sample_size` / `source` columns. Hand that file over, ask for a
price re-check, and get it back filled in. Then:

```bash
python3 scripts/refresh_prices.py apply --file data/price-worksheet.csv --issue "2026 Q4"
```

The old price is archived into `price_history` automatically, so the **Change** column
starts showing quarter-on-quarter movement from the second refresh onwards. Rows left blank
are skipped, so you can do it in batches.

### Route 2 — automatic, from the eBay API

eBay is the one large UK marketplace with an official, free API that permits this.
Register an app at <https://developer.ebay.com>, then:

```bash
EBAY_CLIENT_ID=xxx EBAY_CLIENT_SECRET=yyy python3 scripts/refresh_prices.py ebay
```

It searches UK listings per bike, discards the top and bottom fifth of asking prices, and
rounds to the nearest £100. Bikes with fewer than 15 listings are marked `thin` rather than
`verified`, so a shallow sample never quietly becomes a published price.

Add those two values as repository secrets and `refresh-prices.yml` will run it quarterly
on the 15th of Feb/May/Aug/Nov, raising a **pull request** rather than committing — so
someone signs off on the numbers before they reach a layout.

### What the automatic route can and can't cover

Worth being straight about this, because it shaped the design:

- **Autotrader can't be scraped.** Their `robots.txt` explicitly disallows `/bike-search`
  and `/bike-details`, and their terms prohibit automated collection. They do sell a
  Valuations API to trade partners — as a publisher you may well be able to license it,
  and that would be the single best data source here. Worth a call to their commercial team.
- **eBay prohibits scraping** but the Browse API is free and allowed. It gives *asking*
  prices for active listings, not sold prices; sold data needs partner-level access.
- **Auction results** (H&H, Bonhams) are published, but skew heavily to classic and
  collector machines — little use for a 2013 ZX-6R.
- **Car & Classic and similar** sit behind bot protection.

So: asking prices from eBay give you a defensible, automatable baseline; a licensed
Autotrader feed would be better; and editorial judgement on top of either is what makes it
a *guide* rather than a price list. The assisted route exists because that judgement is the
valuable part and shouldn't be automated away.

---

## Adding or editing bikes

Edit `data/bikes.json` directly, then:

```bash
python3 scripts/validate.py
```

It checks for missing fields, duplicate IDs, verdicts outside 1–10, reversed year and price
ranges, and write-ups long enough to overrun the layout box. The deploy workflow runs it too
and will refuse to publish broken data.

### Fields

| Field | Notes |
|---|---|
| `id` | Lower-case kebab-case, must be unique. It's the key the refresh scripts match on — don't change it once set. |
| `make`, `model`, `variant` | `variant` is the trim, e.g. `636`, `RS`, `LC`. |
| `year_from`, `year_to` | The generation the entry covers. |
| `engine_cc` | Number only; the "cc" is added on display. |
| `category` | Free text, but reuse existing values — it populates the filter. |
| `verdict` | 1–10. |
| `description` | The write-up. Keep under ~400 characters for the layout. |
| `pros`, `cons` | Arrays; exported comma-joined into the `Plus` / `Minus` CSV columns. |
| `price` | Written by the refresh scripts. Don't hand-edit unless you also update `as_of`. |
| `price_history` | Appended automatically. Drives the Change column. |

Photos aren't handled here by design — they're dropped in at page-design stage, as you
specified. If that ever changes, add an `image` field and a thumbnail column.

## Export

**Export CSV** downloads exactly what's on screen — current filters, current sort order —
with columns in the magazine's running order (Make, Model, Year, Engine, Verdict,
Description, Plus, Minus, Price range, …). The `Price range` column is pre-formatted as
`£5,000 - £8,000` so it can drop straight into a layout. **Export JSON** gives the same
selection with full structure, for anything more programmatic.
