#!/usr/bin/env python3
"""Harvest live classified listings from our own Kelsey marketplace sites.

Bike Motor Mart and Old Bike Mart run the same listings platform, so one
parser handles both. These are first-party asking prices, which makes them
the most directly usable price source we have — and the listings also show
which models are actually trading, which is a useful check on what the guide
covers.

Writes data/own-listings.csv and reports models that appear in the classifieds
but are missing from the guide.
"""

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "own-listings.csv")
BIKES = os.path.join(ROOT, "data", "bikes.json")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")

SITES = [
    ("bikemotormart", "https://bikemotormart.com", "bikes-for-sale"),
    ("oldbikemart", "https://www.oldbikemart.co.uk", "listings"),
]
CATEGORIES = ["adventure", "chopper", "classic", "cruiser", "enduro", "moped",
              "naked", "off-road", "scooter", "sport-tourer", "sports",
              "street", "touring", "trike"]

COLS = ["site", "category", "title", "price", "seller", "url"]

# The listing cards carry stable js- hooks, which are far safer to parse
# against than the utility classes around them.
CARD = re.compile(
    r'js-clb-listing-item-inner[^>]*?href="(?P<url>[^"]+)"'  # some themes put href after
    , re.S)
LINK = re.compile(r'<a\s+href="(?P<url>https?://[^"]+?-p\d+/)"[^>]*js-clb-listing-item-inner', re.S)
TITLE = re.compile(r'js-clb-listing-item-title[^>]*>(?P<t>.*?)</div>', re.S)
PRICE = re.compile(r'js-clb-listing-item-price[^>]*>(?P<p>.*?)</div>', re.S)
TYPE = re.compile(r'js-clb-listing-item-type[^>]*>(?P<s>.*?)</div>', re.S)


def get(url, tries=3):
    for n in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if n == tries - 1:
                raise
        except Exception:
            if n == tries - 1:
                raise
        time.sleep(2)
    return None


def clean(s):
    s = re.sub(r"<[^>]+>", "", s or "")
    s = s.replace("&amp;", "&").replace("&#038;", "&").replace("&nbsp;", " ")
    s = s.replace("&#8217;", "'").replace("&quot;", '"').replace("&#8211;", "-")
    return re.sub(r"\s+", " ", s).strip()


def parse_price(text):
    m = re.search(r"£\s*([\d,]+)", text or "")
    if not m:
        return ""
    try:
        return int(m.group(1).replace(",", ""))
    except ValueError:
        return ""


def parse_cards(htmltext):
    """Split the page on listing-item boundaries so each card's title, price
    and seller stay together."""
    out = []
    chunks = htmltext.split("clb-listing-item js-clb-listing-item")
    for chunk in chunks[1:]:
        chunk = chunk[:4000]
        t = TITLE.search(chunk)
        if not t:
            continue
        u = re.search(r'href="(https?://[^"]+?-p\d+/)"', chunk)
        p = PRICE.search(chunk)
        s = TYPE.search(chunk)
        out.append({
            "title": clean(t.group("t")),
            "price": parse_price(clean(p.group("p")) if p else ""),
            "seller": clean(s.group("s")) if s else "",
            "url": u.group(1) if u else "",
        })
    return out


def harvest(max_pages=25, delay=1.0):
    rows, seen = [], set()
    for site, base, path in SITES:
        for cat in CATEGORIES:
            page = 1
            while page <= max_pages:
                url = "%s/%s/category/%s/" % (base, path, cat) if page == 1 \
                    else "%s/%s/category/%s/page/%d/" % (base, path, cat, page)
                try:
                    body = get(url)
                except Exception as e:                      # noqa: BLE001
                    print("  ! %s: %s" % (url, e))
                    break
                if not body:
                    break
                cards = parse_cards(body)
                if not cards:
                    break
                new = 0
                for c in cards:
                    key = c["url"] or (site + c["title"])
                    if key in seen:
                        continue
                    seen.add(key)
                    c.update(site=site, category=cat)
                    rows.append(c)
                    new += 1
                print("  %-14s %-12s page %-2d  %2d listings (%d new)"
                      % (site, cat, page, len(cards), new))
                if new == 0:
                    break
                page += 1
                time.sleep(delay)
    return rows


def save(rows):
    with open(OUT, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        for r in sorted(rows, key=lambda r: (r["site"], r["category"], r["title"])):
            w.writerow({k: r.get(k, "") for k in COLS})


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report-only", action="store_true",
                    help="analyse the existing CSV without re-fetching")
    args = ap.parse_args()

    if args.report_only and os.path.exists(OUT):
        with open(OUT, encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))
    else:
        print("Harvesting our own classifieds...")
        rows = harvest()
        save(rows)
        print("\nSaved %d listings -> %s" % (len(rows), OUT))

    priced = [r for r in rows if str(r.get("price")).strip() not in ("", "0")]
    print("\n%d listings, %d with a price" % (len(rows), len(priced)))

    import collections
    cats = collections.Counter(r["category"] for r in rows)
    print("\nBy category:")
    for c, n in cats.most_common():
        print("  %-14s %3d" % (c, n))

    # Which makes are we seeing that the guide does not cover?
    with open(BIKES, encoding="utf-8") as fh:
        guide = json.load(fh)["bikes"]
    guide_makes = {b["make"].lower() for b in guide}
    seen_makes = collections.Counter()
    for r in rows:
        first = (r["title"] or "").split()
        if first:
            seen_makes[first[0].lower()] += 1
    missing = [(m, n) for m, n in seen_makes.most_common() if m not in guide_makes and n >= 2]
    if missing:
        print("\nMakes appearing in our classifieds but not in the guide:")
        for m, n in missing[:25]:
            print("  %-16s %d listing(s)" % (m, n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
