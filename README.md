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

Push to `main` and GitHub Pages publishes it. Set **Settings → Pages → Source →
Deploy from a branch → `main` → `/ (root)`** once, and that is the whole mechanism.

The site is plain HTML, CSS, JS and JSON with no build step, so it needs no Actions
workflow to deploy. It used to run through `actions/deploy-pages`, but frequent pushes
got rate-limited (HTTP 429) when the runner tried to download the Pages actions from
codeload.github.com. Serving from the branch removes that dependency entirely and
publishes faster.

### After editing anything in `assets/`

Run this before committing:

```
python3 scripts/stamp_assets.py
```

Pages serves `index.html`, `app.js` and `style.css` with `max-age=600` and no
versioning, so a browser can hold one of them for ten minutes while fetching a fresh
copy of another. A stale `index.html` next to a new `app.js` is the case that hurts:
the script looks up an element the old markup does not contain and `render()` throws
on the null, taking the whole listing with it. Stamping a content hash onto the asset
URLs ties them together, so a current `index.html` always pulls the assets that
shipped with it. Editorial staff will still see up to ten minutes of the old page
after a deploy — that is the Pages cache and a hard refresh is the only way to skip it.

`validate.yml` still runs `scripts/validate.py` on any change to the bike data, but it
is a safety net rather than a gate — if it fails or is throttled, the site still
publishes. Run it locally before pushing:

```bash
python3 scripts/validate.py
```

A `.nojekyll` file at the root stops Pages running the content through Jekyll.

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

The four commands you need are in **[PRICE-COMMANDS.md](PRICE-COMMANDS.md)**:
`status` to see what's due, `worksheet` to generate a batch, `apply` to write the
researched prices back, and `validate.py` to check before shipping.

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

### Route 3 — auction sold prices (Iconic Auctioneers)

```bash
python3 scripts/iconic_sold.py --limit 4
```

Iconic publish real **sold** prices — what bikes actually made, not what sellers
hoped for — through a clean JSON endpoint, and their `robots.txt` sets no
restrictions. Results accumulate in `data/auction-sold.csv`, deduplicated by lot,
so the archive compounds each quarter. It already holds 355 sales.

The catch, measured rather than assumed: only **10% of those lots are 2005 or
newer**, and just **8 of our 30 entries have any comparable at all** — mostly a
single sale each. It is an excellent feed for a classics section and no use for
pricing a 2013 ZX-6R. The script prints that split every run so it stays honest.

### What the automatic route can and can't cover

Worth being straight about this, because it shaped the design.

**Assessed and rejected:**

| Source | Verdict |
|---|---|
| Autotrader | `robots.txt` disallows `/bike-search` and `/bike-details*` for all agents, and the terms prohibit automated collection. Off limits. |
| eBay (scraping) | `robots.txt` prohibits it outright and points to the official API. |
| Motorcycles To Go | `robots.txt` contains an explicit `User-agent: ClaudeBot / Disallow: /`. The operator has specifically excluded us, so we don't touch it. |
| Car & Classic | Behind Cloudflare bot protection. |
| The Bike Market | `robots.txt` is permissive, but model pages return HTTP 500 ("We have been alerted"). Too unreliable to depend on. |
| Bigmoto | One dealer group's own stock across three sites, heavy on small-capacity imports, and it 403s anything but a real browser. Not a market sample. |
| The Motorcycle Barn | Permissive and readable, but 32 bikes of one dealer's stock. Useful as a spot-check, not a feed. |
| MotoDealer | Permissive, and has a valuation tool, but it's a young community registry — thin volume today. Worth revisiting. |
| Auction houses (H&H, Bonhams) | Published results, but overwhelmingly classic and collector machines. |

**Usable today:**

- **eBay Browse API** — official, free, permitted. Asking prices for active UK
  listings, not sold prices; sold data needs partner-level access.
- **Iconic Auctioneers** — real sold prices, classic-heavy (see above).
- **Published UK price guides** — Bennetts BikeSocial publish per-generation used
  ranges. This is where the current Q3 numbers came from.

**Worth buying:** Autotrader license a Valuations API to trade partners. As a
publisher you may well be able to get commercial access, and it would be the
single best source here by some distance — worth a call to their commercial team.

So: published guides give defensible editorial numbers today, eBay gives an
automatable baseline, auctions give real transaction data for classics, and a
licensed Autotrader feed would beat all three. Editorial judgement on top is what
makes it a *guide* rather than a price list.

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
| `verdict` | 1–10, scored on **how good a buy this is for what it costs** — value for money, running costs, reliability, parts and dealer support, residual values and ownership risk. It is deliberately *not* a measure of how significant or desirable the motorcycle is: a Vincent is a more important machine than a Bandit 600, but the Bandit is the easier thing to go and buy. Scores are produced by `scripts/rescore_verdicts.py`, which ranks every entry on signals drawn from its own pros and cons and maps that ranking onto a fixed distribution. The previous significance-based scores are preserved in `data/verdicts-significance-scale.csv`. |
| `description` | The write-up. Keep under ~400 characters for the layout. |
| `pros`, `cons` | Arrays; exported comma-joined into the `Plus` / `Minus` CSV columns. |
| `price` | Two figures in Fast Bikes house style: `private` (realistic private-sale money for a running example) and `dealer` (prepped forecourt stock). Written by the refresh scripts — don't hand-edit unless you also update `as_of`. `confidence` is one of `verified` (sampled from many live listings), `researched` (from a published UK price guide), `thin` (only a handful of comparables — flagged in the UI), or `unverified` (seed estimate). |
| `price_history` | Appended automatically. Drives the Change column. |

Photos aren't handled here by design — they're dropped in at page-design stage, as you
specified. If that ever changes, add an `image` field and a thumbnail column.

## Images

Each row has a **＋** button that uploads a photo for that bike. The thumbnail appears
in the row, and the file is renamed to the entry's id — drop in `IMG_0421.PNG` for the
Bimota DB1 and it becomes `bimota-db1-1985.png`, so design receives a folder of
sensibly-named files rather than camera roll numbers.

**Download images** produces a ZIP of the photos for whatever is currently on screen,
matching the CSV export, and the CSV gains an **Image file** column naming each one.

### Sharing between several people

Everyone works from one set of photos, held on the repository's `images` branch.

**Viewing them needs nothing.** Open the page and the shared photos are already there.

**Adding them needs a GitHub token.** Click the **＋** on any row and, if you have not
connected yet, the sharing panel opens and explains why — your chosen file is held and
uploads the moment you save a valid token. There is deliberately no way to add a photo
that only exists on your own machine: an earlier version allowed it, and the obvious
failure was someone adding a hundred images before realising none of them had ever
reached the team.

Tokens are checked against GitHub when you save one, so a mistyped or expired token is
rejected there and then rather than failing silently at the next upload.

Each person needs their own token, made once:

1. Open **<https://github.com/settings/personal-access-tokens>** and click *Generate new token*
2. Grant access to **only** the `Used-Bike-Guide` repository
3. Repository permissions → **Contents: Read and write**. Nothing else.
4. Paste it into the sharing panel

The token lives in that browser's local storage and is sent only to github.com. Treat it
as a password: not on shared machines, and revoke it when the issue is finished. Clearing
the box and saving turns sharing back off, at which point images are local again.

### Design notes worth knowing

**Images go on the `images` branch, not `main`.** Pages builds from `main` and throttles
at roughly ten builds an hour; committing photos there would exhaust that in an
afternoon of uploading. The branch is an orphan, so it carries no site history.

**Thumbnails load from `raw.githubusercontent.com`, not the Pages URL**, so a new photo
appears the moment its commit lands rather than waiting on a deploy.

**Photos are resized to 1600px on the long edge before upload**, typically an 80-90%
reduction. They are for identification and cross-reference; print-resolution originals
belong in the picture library. GitHub asks that files stay near 1MB, and 733 untouched
archive scans would run to several gigabytes.

**A token is only needed to upload.** Anyone can open the page and see every shared
image without one — the repository is public, so both the file listing and the images
themselves are readable by anybody. Unauthenticated GitHub API calls are capped at 60 an
hour per IP, so an office sharing one address is still better off with tokens set.

Any photos left in a browser from before this rule existed still show, with a **dashed
amber border**, and the page offers to upload them to the shared branch as soon as you
connect.

**This repository is public**, so uploaded images are publicly visible, and copies get
cached and indexed beyond your control. Only upload what is cleared for publication.

## Export

Expanding a row also shows an **Image search** link, which opens Google Images for
that exact make, model, variant and year span. It is there so editorial can quickly
cross-check archive photography against what the bike actually looks like — the
results are for checking only, not for publication. Including the year span matters:
the guide holds three different Daytonas and two different Nightsters, and a search
without years returns all of them mixed together.

**Export CSV** downloads exactly what's on screen — current filters, current sort order —
with columns in the magazine's running order (Make, Model, Year, Engine, Verdict,
Description, Plus, Minus, Price range, Private, Dealer, …) and an **Image search**
column at the end carrying the same Google Images link as the expanded row, so
editorial can work through a spreadsheet against the photo library. The `Price range` column is pre-formatted as
`£5,000 - £8,000` so it can drop straight into a layout. **Export JSON** gives the same
selection with full structure, for anything more programmatic.
