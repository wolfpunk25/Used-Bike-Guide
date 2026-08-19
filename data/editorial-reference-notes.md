# Editorial reference material

Seven *Fast Bikes* / *Used Bike Guide* features were supplied on 2026-08-18 for
context. **The PDFs themselves are not stored in this repo** — they are published,
copyrighted Kelsey material and this repository is public, so committing them would
republish them. They live in Darren's Downloads folder; ask him if you need them.

What was taken from them is factual data and house-style observations, which are
recorded below and in `PRICING-METHOD.md`.

## The files

| File | What it is |
|---|---|
| Used Bike Guide.pdf | Yamaha MT-10 SP used guide, words by Jon Urry |
| INSPIRED BY THE RCV.pdf | Honda FireBlade generations, with a rivals comparison panel |
| Sporty Europeans.pdf | Multi-bike European sports naked buyer guide |
| 12 bikes you can buy.pdf | Classified round-up with real asking prices |
| BMW R90S.pdf | Single-model classic feature |
| HONDA GL1000 Gold Wing.pdf | Single-model classic feature, restoration angle |
| Hurricane.pdf | Triumph X75 Hurricane feature |

## House style confirmed

- **`Verdict: x/10`** — matches the `verdict` field already in the database.
- **Prices are quoted as `Private:` and `Dealer:`**, not as a single average or a
  rough-to-mint span. See `PRICING-METHOD.md`.
- Features carry a **specialist contact** ("SPECIALIST: Motorworks…", "AMOC — the AJS
  & Matchless Owners' Club…"). The database has no field for this and it may be worth
  adding if the printed entries are to carry one.
- A **read-time marker** ("6 min") appears in the furniture.

## Price data extracted and used

From *Sporty Europeans*:

| Model | Years | Magazine price |
|---|---|---|
| BMW F900R | 2020-2024 | £4,999-£8,999 |
| Ducati Streetfighter 848 | 2012-2015 | £4,999-£7,500 |
| Triumph Street Triple 765 R | 2017-2019 | £4,499-£5,999 |
| KTM 890 Duke R | 2020-2022 | £4,999-£6,300 |
| Aprilia Tuono 660 | 2021- | £4,999-£7,999 |

From *Inspired by the RCV* rivals panel:

| Model | Private | Dealer |
|---|---|---|
| 2004 Kawasaki ZX-10R | £4,999 | £6,000 |
| 2004 Yamaha YZF-R1 | £4,000 | £4,800 |
| 2005 Suzuki GSX-R1000 K5 | £4,750 | £5,500 |
| 2004-07 Honda FireBlade | £3,500 | £4,000 (realistic) |

Four of eight spot-checks against these spanned our range exactly; three were
adjusted on 2026-08-18 (F900R, 890 Duke R, Tuono 660).

## Scootering buyers-guide cross-reference (19 Aug 2026)

Checked the guide against two pages of Scootering's own new-scooter buyers guide
(s1/s2, covering 50cc to 700cc plus electric, with the magazine's three classic
benchmarks: a Vespa small frame, a Vespa PX and a Lambretta GP 200).

Every model named in those tables is now represented, except for machines still
too new to have a used market: the Royal Alloy 350 range (GP350MT/SE, JPS350,
TG350), Royal Alloy GT2 125/160, Lambretta G350, the Italjet Dragster 459 and
700 twins, Vespa GTS 125 RST, Suzuki Avenis 125 and the Vespa Primavera
Elettrica 45. These are on the watchlist for the next issue rather than the
database — several launched in the last twelve months and have no used stock.

The cross-reference also exposed a real gap that had nothing to do with the new
models: the guide carried the PX and the GP200 but **no small-frame Vespa at
all**, which is the third of Scootering's own benchmarks. Six classic scooters
were added to close it — Vespa 50 Special, Primavera ET3, PK50, Rally 200,
Sprint Veloce 150 and GS160, plus the Lambretta TV200/GT200.

25 entries added in total. Prices are editorial estimates set against the
magazine's list prices and current classified asking prices; the shallow-market
entries are flagged `thin` and want a proper pass before press.

## Price pass, 19 Aug 2026

Cleared the thin-confidence backlog: 28 flagged entries plus 8 corrections the
same research turned up. 36 prices changed; the guide now stands at 753
researched and 5 thin. Worksheet archived as `data/price-pass-2026-08-19.csv`.

Sources used, in order of weight:

* **Vintage Scooters valuation guide** — the find of this pass. It puts the
  Lambretta SX200, TV200 and GP200 in a £10,000–£30,000 tier and the Vespa
  Rally 200 and GS160 in £10,000–£20,000, and records a TV200 making £23,000
  at auction. Our classic scooter prices were far below the market.
* **Iconic Auctioneers sold results** and **our own Bike Motor Mart / Old Bike
  Mart classifieds** — first-party, but they only covered 4 of the 28.
* **UK dealer and classified asking prices** for everything else, discounted to
  a private figure.

Direction of travel: classic scooters were the big under-valuation, recent
Ducatis and adventure bikes the big over-valuation. The DesertX was carrying
£12,000/£16,000 against real stock at £9,890–£10,800, and the Himalayan
£3,200/£5,000 against 2024 bikes at £4,399. Modern-classic and 1980s Japanese
prices moved much less.

Still thin, and why:

* **Harley-Davidson Street Bob** — the entry spans 2006–2025, which is two
  different motorcycles. The 2006–2017 Dyna trades at £6–9k, the 2018-on
  Milwaukee-Eight Softail at £12,795–£15,345. No single pair of figures is
  honest here; **this entry needs splitting** and no price pass can fix it.
* **Suzuki DR750S Big** — cult status is lifting values but UK sales are sparse.
* **Triumph Tiger 900 (885)** — very few trading; priced by reading across from
  contemporary Sprint and Daytona 900s.
* **Kawasaki KLE500** — searches are now swamped by the 2026 KLE500 revival,
  which makes the 1991–2007 bike hard to price from listings.
* **Italjet Dragster 300** — read across from 200 stock; too few 300s trading.
