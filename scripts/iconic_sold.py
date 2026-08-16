#!/usr/bin/env python3
"""Harvest real sold prices from Iconic Auctioneers' public results.

Unlike classified ads, these are prices bikes actually changed hands for. The
catch is the catalogue is heavily weighted to classic and collector machines,
so this feeds a classics section far better than it feeds mainstream used
listings -- run `--report` to see the split before relying on it.

Results accumulate in data/auction-sold.csv, deduplicated by lot id, so the
archive gets more useful every quarter.
"""

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVE = os.path.join(ROOT, "data", "auction-sold.csv")
BIKES = os.path.join(ROOT, "data", "bikes.json")

BASE = "https://www.iconicauctioneers.com"
LOTS_URL = BASE + "/index.php?option=com_bidding&format=json&task=commission.getLots"
AUCTIONS_URL = BASE + "/index.php?option=com_calendar&format=json&task=archive.filterAuctions"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")

COLS = ["lot_id", "auction_id", "sale_date", "year", "make", "model",
        "engine_cc", "odometer", "sold_price", "hammer_price", "lot_name"]


def post(url, data):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": UA,
    })
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.load(r)


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read().decode("utf-8", "replace")


def discover_auctions(limit=6):
    """Ask the archive endpoint for recent motorcycle sales, newest first."""
    # The endpoint's sale_type filter returns nothing, so pull everything and
    # pick the motorcycle sales out by name.
    payload = post(AUCTIONS_URL, {
        "sale_type": "", "layout": "archive", "sale_year": "",
        "per_page": max(limit * 4, 25), "current_page": 1,
    })
    ids = []
    for a in payload.get("auctions") or []:
        name = (a.get("name") or "")
        if not re.search(r"motorcycle|motorbike|\bbike\b", name, re.I):
            continue
        aid = str(a.get("id") or "").strip()
        if aid and aid not in ids:
            ids.append(aid)
    return ids[:limit]


def fetch_lots(auction_id, per_page=200):
    """Page through one auction's lots."""
    out, page = [], 1
    while True:
        payload = post(LOTS_URL, {
            "per_page": per_page, "current_page": page, "auction_id": auction_id,
            "session_no": "1", "lot_order": "", "sale_type": "", "search": "",
        })
        lots = payload.get("lots") or []
        out.extend(lots)
        if len(lots) < per_page:
            break
        page += 1
        if page > 20:      # safety valve against a pagination loop
            break
    return out


def int_or_none(v):
    try:
        n = int(float(v))
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


def to_row(lot, auction_id):
    if lot.get("article_cat_code") != "BIKE" or lot.get("sold") != "1":
        return None
    price = int_or_none(lot.get("sold_price"))
    make = (lot.get("make") or "").strip()
    if not price or not make:
        return None
    return {
        "lot_id": lot.get("unique_id") or lot.get("id"),
        "auction_id": auction_id,
        "sale_date": (lot.get("published_at") or "")[:10],
        "year": int_or_none(lot.get("production_year")) or "",
        "make": make.title(),
        "model": (lot.get("model") or "").strip().title(),
        "engine_cc": int_or_none(lot.get("Engine_capacity")) or "",
        "odometer": int_or_none(lot.get("Odometer_Reading")) or "",
        "sold_price": price,
        "hammer_price": int_or_none(lot.get("hammer_price")) or "",
        "lot_name": (lot.get("name") or "").strip(),
    }


def load_archive():
    if not os.path.exists(ARCHIVE):
        return {}
    with open(ARCHIVE, encoding="utf-8-sig", newline="") as fh:
        return {r["lot_id"]: r for r in csv.DictReader(fh)}


def save_archive(rows):
    with open(ARCHIVE, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        for r in sorted(rows.values(), key=lambda r: (str(r.get("sale_date")), str(r.get("lot_id")))):
            w.writerow(r)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--auctions", nargs="*", help="auction ids (default: discover recent ones)")
    ap.add_argument("--limit", type=int, default=4, help="how many recent auctions to pull")
    ap.add_argument("--report", action="store_true",
                    help="summarise the archive's usefulness instead of fetching")
    args = ap.parse_args()

    archive = load_archive()

    if not args.report:
        ids = args.auctions or discover_auctions(args.limit)
        if not ids:
            sys.exit("Could not find any auction ids to fetch.")
        print("Fetching %d auction(s): %s" % (len(ids), ", ".join(ids)))
        added = 0
        for aid in ids:
            try:
                lots = fetch_lots(aid)
            except Exception as e:                      # noqa: BLE001 - keep going
                print("  ! auction %s failed: %s" % (aid, e))
                continue
            new = 0
            for lot in lots:
                row = to_row(lot, aid)
                if row and row["lot_id"] not in archive:
                    archive[row["lot_id"]] = row
                    new += 1
            print("  auction %s: %d lots, %d new sold bikes" % (aid, len(lots), new))
            added += new
        save_archive(archive)
        print("\nArchive now holds %d sold bikes -> %s" % (len(archive), ARCHIVE))

    # Always report the modern/classic split - it's the thing that decides
    # whether this data can price a mainstream used bike.
    rows = list(archive.values())
    if not rows:
        print("Archive is empty.")
        return 0
    years = [int(r["year"]) for r in rows if str(r.get("year")).isdigit()]
    modern = [y for y in years if y >= 2005]
    print("\nWith a year recorded: %d" % len(years))
    print("  2005 or newer : %d (%.0f%%)" % (len(modern), 100.0 * len(modern) / max(len(years), 1)))
    print("  pre-2005      : %d" % (len(years) - len(modern)))

    with open(BIKES, encoding="utf-8") as fh:
        guide = json.load(fh)["bikes"]
    hits = 0
    for b in guide:
        want_make, want_model = b["make"].lower(), b["model"].lower().split()[0]
        n = sum(1 for r in rows
                if want_make in (r["make"] or "").lower()
                and want_model in (r["model"] or r["lot_name"] or "").lower())
        if n:
            hits += 1
            print("  matched %-34s %d sale(s)" % (b["make"] + " " + b["model"], n))
    print("\n%d of %d guide entries have any auction comparable." % (hits, len(guide)))
    if hits < len(guide) / 4:
        print("Too sparse to price the main listings - treat as a classics feed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
