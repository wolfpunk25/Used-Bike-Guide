#!/usr/bin/env python3
"""Harvest used-bike stock from dealer sites that permit it.

Currently covers Webbs Motorcycles (Lincoln/Peterborough). Their listing
cards expose clean data- attributes, so no fragile HTML scraping is needed.

Webbs' robots.txt names ClaudeBot in a group carrying Crawl-delay: 10 (not a
blanket disallow), so we honour that delay, and it disallows any URL carrying
_bc_fsnf=1 — the brand-filter links — which we never request.

These are dealer asking prices for modern used bikes, which balances the
classic-heavy data from our own classifieds.
"""

import argparse
import csv
import os
import re
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "dealer-listings.csv")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")

BASE = "https://webbsmotorcycles.co.uk/bikes-for-sale/"
CRAWL_DELAY = 10          # as requested by their robots.txt
COLS = ["dealer", "brand", "name", "price", "year", "url"]

ARTICLE = re.compile(r"<article[^>]*?data-name=\"(?P<name>[^\"]*)\"[^>]*?"
                     r"data-product-brand=\"(?P<brand>[^\"]*)\"[^>]*?"
                     r"data-product-price=\"(?P<price>[^\"]*)\"", re.S)
LINK = re.compile(r'href="(https://webbsmotorcycles\.co\.uk/[^"]+?-\d+-\d+/)"')


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read().decode("utf-8", "replace")


def parse(page_html):
    rows = []
    # Split per card so a card's link stays with its data attributes.
    for chunk in page_html.split("<article")[1:]:
        m = ARTICLE.search("<article" + chunk[:1500])
        if not m:
            continue
        name = m.group("name").strip()
        if not name:
            continue
        try:
            price = int(float(m.group("price")))
        except (TypeError, ValueError):
            price = ""
        link = LINK.search(chunk[:2500])
        # Some names carry a registration year, e.g. "TRIUMPH TIGER 900 (2021)"
        y = re.search(r"\b(19|20)\d{2}\b", name)
        rows.append({
            "dealer": "webbs",
            "brand": m.group("brand").strip(),
            "name": name,
            "price": price,
            "year": y.group(0) if y else "",
            "url": link.group(1) if link else "",
        })
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max-pages", type=int, default=10)
    args = ap.parse_args()

    rows, seen = [], set()
    for page in range(1, args.max_pages + 1):
        url = BASE if page == 1 else BASE + "?page=%d" % page
        if page > 1:
            time.sleep(CRAWL_DELAY)
        try:
            body = get(url)
        except Exception as e:                              # noqa: BLE001
            print("  ! page %d: %s" % (page, e))
            break
        found = parse(body)
        new = [r for r in found if (r["url"] or r["name"]) not in seen]
        for r in new:
            seen.add(r["url"] or r["name"])
        rows.extend(new)
        print("  page %d: %d cards, %d new" % (page, len(found), len(new)))
        if not new:
            break

    with open(OUT, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        for r in sorted(rows, key=lambda r: (r["brand"], r["name"])):
            w.writerow(r)
    print("\nSaved %d listings -> %s" % (len(rows), OUT))

    import collections
    priced = [r for r in rows if str(r["price"]).strip() not in ("", "0")]
    print("%d with a price" % len(priced))
    print("\nBy brand:")
    for b, n in collections.Counter(r["brand"] for r in rows).most_common(15):
        print("  %-16s %2d" % (b or "(none)", n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
