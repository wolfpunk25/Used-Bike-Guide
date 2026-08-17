#!/usr/bin/env python3
"""Turn dealer stock-list PDFs into structured listings.

Uses pdf_text.py to recover the text, then parses the repeated blocks these
sites render:  "2023 (23) reg | Naked | 5,750 miles | <model> | <price>".
The renderer repeats each string several times, so runs are collapsed first.

Appends to data/dealer-listings.csv alongside the scraped dealer stock.
"""

import csv
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pdf_text import extract                                  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "dealer-listings.csv")
COLS = ["dealer", "brand", "name", "price", "year", "url"]

REG = re.compile(r"(\d{4})\s*\((\d{2})\)\s*reg")
MILES = re.compile(r"([\d,]+)\s*miles")
PRICE = re.compile(r"£([\d,]+)")
DEDUPE = re.compile(r"(.{4,80}?)\1{1,}")

MAKES = ("Honda Yamaha Suzuki Kawasaki Triumph BMW Ducati KTM Aprilia Harley-Davidson "
         "Harley Moto Royal Husqvarna Indian Benelli CFMoto Zontes Lexmoto Vespa Piaggio "
         "Lambretta MV Norton Velocette Matchless AJS BSA Ariel Panther Sinnis Keeway "
         "Sym Kymco Peugeot Gilera Derbi Rieju Mutt Herald Brixton Bullit Mash Fantic "
         "Beta Sherco Gas Husaberg Bimota Buell Victory Zero Energica Super").split()


def clean(raw):
    # Drop image-stream noise: keep lines that are mostly printable ASCII.
    keep = []
    for line in raw.splitlines():
        printable = sum(1 for c in line if 32 <= ord(c) < 127)
        if line and printable / max(len(line), 1) > 0.85:
            keep.append(line)
    txt = " ".join(keep)
    txt = txt.replace("!", " ")
    prev = None
    while prev != txt:                       # collapse the renderer's repeats
        prev = txt
        txt = DEDUPE.sub(r"\1", txt)
    return re.sub(r"\s+", " ", txt)


def find_make(s):
    for mk in MAKES:
        if re.search(r"\b" + re.escape(mk) + r"\b", s, re.I):
            return "Harley-Davidson" if mk in ("Harley",) else mk
    return ""


# CMC render their cards as: <model>CMC<store><miles>"mi.<cc>cc£<price>cashprice
# with the year+make pairs emitted afterwards in a separate batched layer, in
# the same order as the cards. So we parse both and zip them.
CMC_CARD = re.compile(
    r'(?P<model>[A-Za-z0-9][^£]{0,44}?)CMC(?P<store>[A-Za-z]+?)(?P<miles>\d[\d,]*)"?mi\.'
    r'(?:(?P<cc>\d{2,4})cc)?£(?P<price>[\d,]+)cashprice')
CMC_MAKEYEAR = re.compile(r"(?P<year>(?:19|20)\d{2})\s*(?P<make>[A-Z][A-Z\-]{2,})")


BRAND_FIX = {"Bmw": "BMW", "Ktm": "KTM", "Mv": "MV Agusta", "Harleydavidson": "Harley-Davidson",
             "Harley-Davidson": "Harley-Davidson", "Royalenfield": "Royal Enfield",
             "Indianmotorcycle": "Indian", "Motoguzzi": "Moto Guzzi", "Cfmoto": "CFMoto"}

FINANCE_NOISE = re.compile(
    r"(\d*deposit|HP\s*\w*nance|PCP\s*\w*nance|per\s*month|permonth|cashprice|"
    r"LifetimeWarrantyIncluded|RESERVED|Same-day\s*rideaway|ComingSoon|\d+\s*bikes|"
    r"£[\d,.]+)", re.I)


def parse_cmc(txt, dealer):
    """Pull the year+make layer out first, in order, then parse the cards from
    what remains. Doing it in that order stops the two layers contaminating
    each other, which they do badly if parsed in place."""
    makes = []

    def _take(m):
        makes.append((m.group("year"), m.group("make").title()))
        return " | "

    stripped = CMC_MAKEYEAR.sub(_take, txt)

    rows = []
    for i, m in enumerate(CMC_CARD.finditer(stripped)):
        model = FINANCE_NOISE.sub(" ", m.group("model"))
        model = model.split("|")[-1]                      # drop anything before a layer break
        model = re.sub(r"^[^A-Za-z0-9]+", "", model)
        model = re.sub(r"\s+", " ", model).strip(" -,.")
        if not model or len(model) < 2:
            continue
        try:
            price = int(m.group("price").replace(",", ""))
        except ValueError:
            continue
        if price < 300:
            continue
        year, make = makes[i] if i < len(makes) else ("", "")
        rows.append({"dealer": dealer, "brand": BRAND_FIX.get(make, make),
                     "name": model, "price": price, "year": year, "url": ""})
    return rows


def parse(path, dealer):
    """Scan for a make, then take the text up to the next price as the model.

    Anchoring on prices rather than registration markers matters: these are
    printed web pages, so a listing's model and its reg line often land on
    opposite sides of a page break.
    """
    txt = clean(extract(path))
    if "cashprice" in txt:                     # CMC's layout
        return parse_cmc(txt, dealer)
    rows, seen_spans = [], []
    make_re = re.compile(r"\b(" + "|".join(re.escape(m) for m in MAKES) + r")\b", re.I)

    for m in make_re.finditer(txt):
        start = m.start()
        window = txt[start:start + 260]
        price = PRICE.search(window)
        if not price:
            continue
        # Model runs from the make up to the price, minus any sales blurb in caps.
        seg = window[:price.start()]
        seg = re.split(r"(?:[A-Z]{4,}\s){2,}", seg)[0]        # drop "ONLY 5K MILES..." shouting
        seg = re.sub(r"Euro\s*\d.*$", "", seg, flags=re.I)
        seg = re.sub(r"\d[\d,]*\s*(miles|cc)\b.*$", "", seg, flags=re.I)
        name = re.sub(r"\s+", " ", seg).strip(" -,.")
        if not name or len(name) > 60:
            continue
        try:
            p = int(price.group(1).replace(",", ""))
        except ValueError:
            continue
        if p < 300:
            continue
        # Nearest preceding registration year, if there is one.
        back = txt[max(0, start - 200):start]
        regs = REG.findall(back)
        year = regs[-1][0] if regs else ""
        span = (start, start + price.end())
        if any(abs(span[0] - s0) < 30 for s0, _ in seen_spans):
            continue
        seen_spans.append(span)
        make = m.group(1)
        rows.append({"dealer": dealer,
                     "brand": "Harley-Davidson" if make.lower().startswith("harley") else make.title(),
                     "name": name, "price": p, "year": year, "url": ""})
    return rows


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: parse_dealer_pdf.py <dealer> <pdf> [pdf...]")
    dealer, paths = sys.argv[1], sys.argv[2:]
    rows = []
    for p in paths:
        got = parse(p, dealer)
        print("  %-58s %3d listings" % (os.path.basename(p)[:58], len(got)))
        rows.extend(got)

    existing = []
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8-sig", newline="") as fh:
            existing = list(csv.DictReader(fh))
    seen = {(r["dealer"], r["name"], str(r["price"])) for r in existing}
    added = [r for r in rows if (r["dealer"], r["name"], str(r["price"])) not in seen]

    with open(OUT, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        for r in existing + added:
            w.writerow({k: r.get(k, "") for k in COLS})
    print("\nParsed %d, added %d new -> %s" % (len(rows), len(added), OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
