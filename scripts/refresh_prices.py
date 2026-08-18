#!/usr/bin/env python3
"""Refresh the price block on each bike in data/bikes.json.

Prices follow Fast Bikes house style: a `private` figure (realistic private-sale
money for a running example) and a `dealer` figure (prepped forecourt stock).

Two working modes:

  worksheet  Emit a CSV of every bike with its current price, for a human (or
             Claude) to research and fill in. This is the assisted-refresh path.
  apply      Read a filled-in worksheet back and apply it, archiving the old
             price into price_history.
  ebay       Pull live asking prices from the official eBay Browse API and
             derive a range automatically. Needs EBAY_CLIENT_ID/SECRET.

Standard library only, works on Python 3.9+.
"""

import argparse
import base64
import csv
import datetime as dt
import json
import os
import statistics
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "bikes.json")

EBAY_OAUTH = "https://api.ebay.com/identity/v1/oauth2/token"
EBAY_SEARCH = "https://api.ebay.com/buy/browse/v1/item_summary/search"
EBAY_SCOPE = "https://api.ebay.com/oauth/api_scope"
# eBay UK motorcycle category. Confirm against the current eBay taxonomy if
# results look wrong -- eBay does reorganise these occasionally.
DEFAULT_CATEGORY = "6024"

# How much to trust a price. "verified" = sampled from many live listings;
# "researched" = taken from a published UK price guide; "thin" = derived from a
# handful of listings; "unverified" = seed estimate, not researched at all.
CONFIDENCE_LEVELS = ("verified", "researched", "thin", "unverified")

WORKSHEET_COLS = [
    "id", "make", "model", "variant", "years",
    "current_private", "current_dealer", "current_as_of", "current_source",
    "new_private", "new_dealer", "sample_size", "source", "confidence", "notes",
]


# ---------------------------------------------------------------- data helpers

def load():
    with open(DATA, encoding="utf-8") as fh:
        return json.load(fh)


def save(doc):
    with open(DATA, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def years(bike):
    a, b = bike.get("year_from"), bike.get("year_to")
    if not a:
        return ""
    return str(a) if not b or b == a else "%s-%s" % (a, b)


def label(bike):
    return " ".join(x for x in [bike.get("make"), bike.get("model"), bike.get("variant")] if x)


def apply_price(bike, private, dealer, source, sample_size, as_of, confidence="verified"):
    """Archive the outgoing price, then write the new one."""
    old = bike.get("price") or {}
    if old.get("private") is not None and old.get("source") != "seed-estimate":
        bike.setdefault("price_history", []).append({
            "as_of": old.get("as_of"),
            "private": old.get("private"),
            "dealer": old.get("dealer"),
            "source": old.get("source"),
            "sample_size": old.get("sample_size", 0),
        })
    bike["price"] = {
        "private": private,
        "dealer": dealer,
        "as_of": as_of,
        "source": source,
        "confidence": confidence,
        "sample_size": sample_size,
    }


# ------------------------------------------------------------------- worksheet

def select(bikes, args):
    """Narrow a worksheet to one batch: a decade, a make, or whatever still
    needs pricing. Keeps a price pass to a reviewable size."""
    out = []
    for b in bikes:
        if args.make and args.make.lower() not in b["make"].lower():
            continue
        if args.category and args.category.lower() not in (b.get("category") or "").lower():
            continue
        yf, yt = b.get("year_from"), b.get("year_to") or b.get("year_from")
        # Overlap, matching the front end: a 1998-2003 bike is in the 1990s.
        if args.year_from and yt < args.year_from:
            continue
        if args.year_to and yf > args.year_to:
            continue
        if args.todo and (b.get("price") or {}).get("confidence") in ("verified", "researched"):
            continue
        out.append(b)
    return out


def cmd_worksheet(args):
    doc = load()
    out = args.file or os.path.join(ROOT, "data", "price-worksheet.csv")
    chosen = select(doc["bikes"], args)
    if not chosen:
        sys.exit("Nothing matched that selection.")
    with open(out, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=WORKSHEET_COLS)
        w.writeheader()
        for b in chosen:
            p = b.get("price") or {}
            w.writerow({
                "id": b["id"], "make": b.get("make", ""), "model": b.get("model", ""),
                "variant": b.get("variant", ""), "years": years(b),
                "current_private": p.get("private", ""), "current_dealer": p.get("dealer", ""),
                "current_as_of": p.get("as_of") or "", "current_source": p.get("source", ""),
                "new_private": "", "new_dealer": "", "sample_size": "", "source": "",
                "confidence": "", "notes": "",
            })
    print("Wrote worksheet for %d bikes -> %s" % (len(chosen), out))
    print("Fill in new_private / new_dealer / sample_size / source, then run:")
    print("  python3 scripts/refresh_prices.py apply --file %s" % out)
    return 0


def cmd_apply(args):
    if not args.file:
        sys.exit("apply needs --file pointing at a filled-in worksheet")
    doc = load()
    index = {b["id"]: b for b in doc["bikes"]}
    today = args.as_of or dt.date.today().isoformat()

    updated, skipped, unknown = 0, 0, []
    with open(args.file, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            bike_id = (row.get("id") or "").strip()
            if not bike_id:
                continue
            if bike_id not in index:
                unknown.append(bike_id)
                continue
            lo, hi = (row.get("new_private") or "").strip(), (row.get("new_dealer") or "").strip()
            if not lo or not hi:
                skipped += 1
                continue
            try:
                lo_i, hi_i = int(float(lo)), int(float(hi))
            except ValueError:
                unknown.append("%s (bad number: %r/%r)" % (bike_id, lo, hi))
                continue
            if lo_i > hi_i:
                lo_i, hi_i = hi_i, lo_i
            sample = (row.get("sample_size") or "").strip()
            conf = (row.get("confidence") or "").strip() or "verified"
            if conf not in CONFIDENCE_LEVELS:
                unknown.append("%s (unknown confidence %r)" % (bike_id, conf))
                continue
            apply_price(
                index[bike_id], lo_i, hi_i,
                (row.get("source") or "manual-research").strip(),
                int(sample) if sample.isdigit() else 0,
                today, confidence=conf,
            )
            if (row.get("notes") or "").strip():
                index[bike_id]["notes"] = row["notes"].strip()
            updated += 1

    doc["meta"]["last_refreshed"] = today
    if args.issue:
        doc["meta"]["issue"] = args.issue
    if args.dry_run:
        print("DRY RUN - nothing written.")
    else:
        save(doc)
    print("Updated %d, skipped %d (blank), %d unrecognised" % (updated, skipped, len(unknown)))
    for u in unknown:
        print("  ! %s" % u)
    return 0


# ------------------------------------------------------------------ eBay pull

def ebay_token(client_id, client_secret):
    cred = base64.b64encode(("%s:%s" % (client_id, client_secret)).encode()).decode()
    body = urllib.parse.urlencode({"grant_type": "client_credentials", "scope": EBAY_SCOPE}).encode()
    req = urllib.request.Request(EBAY_OAUTH, data=body, headers={
        "Authorization": "Basic " + cred,
        "Content-Type": "application/x-www-form-urlencoded",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["access_token"]


def ebay_prices(token, query, category, floor, limit=200):
    """Return asking prices (GBP) for active UK listings matching `query`."""
    params = {
        "q": query,
        "category_ids": category,
        "limit": str(min(limit, 200)),
        "filter": "priceCurrency:GBP,price:[%d..]" % floor,
    }
    url = EBAY_SEARCH + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + token,
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_GB",
    })
    with urllib.request.urlopen(req, timeout=45) as r:
        payload = json.load(r)
    prices = []
    for item in payload.get("itemSummaries") or []:
        price = (item.get("price") or {}).get("value")
        if price is None:
            continue
        try:
            prices.append(float(price))
        except (TypeError, ValueError):
            continue
    return prices


def derive_range(prices, round_to=100):
    """20th-80th percentile of asking prices, rounded. Ignores the tails, which
    are usually damaged bikes at one end and dealer optimism at the other."""
    if len(prices) < 5:
        return None
    ordered = sorted(prices)
    lo = statistics.quantiles(ordered, n=10)[1]   # 20th percentile
    hi = statistics.quantiles(ordered, n=10)[7]   # 80th percentile
    r = float(round_to)
    return int(round(lo / r) * r), int(round(hi / r) * r)


def cmd_ebay(args):
    cid, secret = os.environ.get("EBAY_CLIENT_ID"), os.environ.get("EBAY_CLIENT_SECRET")
    if not cid or not secret:
        sys.exit("Set EBAY_CLIENT_ID and EBAY_CLIENT_SECRET (see README).")

    doc = load()
    token = ebay_token(cid, secret)
    today = args.as_of or dt.date.today().isoformat()
    updated, thin = 0, []

    for bike in doc["bikes"]:
        if args.only and bike["id"] not in args.only:
            continue
        query = label(bike)
        try:
            prices = ebay_prices(token, query, args.category, args.floor)
        except urllib.error.HTTPError as e:
            print("  ! %s: HTTP %s %s" % (query, e.code, e.reason))
            continue
        rng = derive_range(prices)
        if not rng:
            thin.append("%s (%d listings)" % (query, len(prices)))
            continue
        print("  %-38s %5d listings  £%s-£%s" % (query, len(prices), rng[0], rng[1]))
        apply_price(bike, rng[0], rng[1], "ebay-uk-asking", len(prices), today,
                    confidence="verified" if len(prices) >= args.min_sample else "thin")
        updated += 1

    doc["meta"]["last_refreshed"] = today
    if args.issue:
        doc["meta"]["issue"] = args.issue
    if args.dry_run:
        print("DRY RUN - nothing written.")
    else:
        save(doc)
    print("\nUpdated %d bikes; %d had too few listings to price:" % (updated, len(thin)))
    for t in thin:
        print("  - %s" % t)
    return 0


# ----------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    w = sub.add_parser("worksheet", help="emit a CSV to research prices into")
    w.add_argument("--file")
    w.add_argument("--year-from", type=int, help="only bikes on sale in or after this year")
    w.add_argument("--year-to", type=int, help="only bikes on sale in or before this year")
    w.add_argument("--make")
    w.add_argument("--category")
    w.add_argument("--todo", action="store_true", help="skip anything already researched")
    w.set_defaults(func=cmd_worksheet)

    a = sub.add_parser("apply", help="apply a filled-in worksheet")
    a.add_argument("--file", required=True)
    a.add_argument("--as-of", help="ISO date to stamp (default: today)")
    a.add_argument("--issue", help="set meta.issue, e.g. '2026 Q4'")
    a.add_argument("--dry-run", action="store_true")
    a.set_defaults(func=cmd_apply)

    e = sub.add_parser("ebay", help="pull asking prices from the eBay Browse API")
    e.add_argument("--category", default=DEFAULT_CATEGORY)
    e.add_argument("--floor", type=int, default=500, help="ignore listings below this (parts, spares)")
    e.add_argument("--min-sample", type=int, default=15, help="listings needed to mark a price verified")
    e.add_argument("--only", nargs="*", help="limit to these bike ids")
    e.add_argument("--as-of")
    e.add_argument("--issue")
    e.add_argument("--dry-run", action="store_true")
    e.set_defaults(func=cmd_ebay)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
