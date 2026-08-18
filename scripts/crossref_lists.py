#!/usr/bin/env python3
"""Cross-reference editorial model lists against the guide.

Does two jobs at once: finds models we do not cover, and — where a list
carries its own UK price range — compares it against ours. The second is the
more useful of the two, because it is an independent check on prices that
were researched separately.

Matching is deliberately loose on model text (lists write "GSX-R1000 K1 / K5",
we write "GSX-R1000 K5") but strict on year: a listed year must fall inside
the guide entry's production span, so a Daytona 675 never matches a 955i.
"""

import csv
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIKES = os.path.join(ROOT, "data", "bikes.json")

STOP = {"the", "and", "gen", "mk", "series", "edition", "model"}


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def tokens(model):
    """Split a listed model into comparable chunks, dropping slash-variants."""
    parts = re.split(r"[/,]", model)
    out = []
    for p in parts:
        p = re.sub(r"\(.*?\)", " ", p)
        toks = [norm(t) for t in re.split(r"[\s\-]+", p) if t]
        toks = [t for t in toks if t and t not in STOP and len(t) > 1]
        if toks:
            out.append(toks)
    return out or [[norm(model)]]


def parse_price(s):
    nums = re.findall(r"([\d,]{3,})", s or "")
    vals = []
    for n in nums:
        try:
            vals.append(int(n.replace(",", "")))
        except ValueError:
            pass
    return (min(vals), max(vals)) if len(vals) >= 2 else (None, None)


def find(bikes, make, model, year):
    m = norm(make)
    best = None
    for b in bikes:
        if norm(b["make"])[:4] != m[:4]:
            continue
        hay = norm(b["model"] + b["variant"])
        for group in tokens(model):
            joined = "".join(group)
            if joined in hay or hay in joined or all(t in hay for t in group):
                # Year must sit inside the production span (small tolerance).
                if year:
                    yf, yt = b["year_from"], (b.get("year_to") or b["year_from"])
                    # No tolerance: comparing a 1992 FireBlade against a 2020
                    # Fireblade produces a meaningless price gap.
                    if not (yf <= year <= yt):
                        continue
                return b
    return None      # no loose fallback: a wrong match is worse than a miss


def main():
    with open(BIKES, encoding="utf-8") as fh:
        bikes = json.load(fh)["bikes"]

    missing, compared = [], []
    for path in sys.argv[1:]:
        name = os.path.basename(path)
        with open(path, encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                if not r.get("Make"):
                    continue
                yr = r.get("Year Introduced", "").strip()
                yr = int(yr) if yr.isdigit() else None
                hit = find(bikes, r["Make"], r["Model"], yr)
                pl, ph = parse_price(r.get("Average UK Price (£)", ""))
                if not hit:
                    missing.append((name, r["Make"], r["Model"], yr, pl, ph))
                elif pl and ph:
                    compared.append((r["Make"], r["Model"], hit, pl, ph))

    print("=" * 78)
    print("MISSING FROM THE GUIDE (%d)" % len(missing))
    print("=" * 78)
    cur = None
    for src, mk, mo, yr, pl, ph in missing:
        if src != cur:
            print("\n-- %s" % src)
            cur = src
        print("   %-16s %-34s %-6s £%s-%s" % (mk, mo[:34], yr or "?", pl or "?", ph or "?"))

    print("\n" + "=" * 78)
    print("PRICE COMPARISON — ours vs the editorial lists (%d matched)" % len(compared))
    print("=" * 78)
    off = []
    for mk, mo, b, pl, ph in compared:
        ol, oh = b["price"]["private"], b["price"]["dealer"]
        omid, lmid = (ol + oh) / 2, (pl + ph) / 2
        diff = (omid - lmid) / lmid * 100 if lmid else 0
        if abs(diff) >= 30:
            off.append((diff, mk, mo, b, ol, oh, pl, ph))
    off.sort(key=lambda x: -abs(x[0]))
    print("\n%d of %d differ by 30%% or more on the midpoint:\n" % (len(off), len(compared)))
    for diff, mk, mo, b, ol, oh, pl, ph in off:
        arrow = "ours HIGHER" if diff > 0 else "ours LOWER "
        print("  %-30s ours £%-6d-£%-6d | list £%-6d-£%-6d  %s %+.0f%%"
              % ((mk + " " + b["model"])[:30], ol, oh, pl, ph, arrow, diff))
    return 0


if __name__ == "__main__":
    sys.exit(main())
