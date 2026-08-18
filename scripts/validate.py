#!/usr/bin/env python3
"""Sanity-check data/bikes.json before it goes anywhere near a page layout."""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "bikes.json")

REQUIRED = ["id", "make", "model", "category", "year_from", "engine_cc",
            "verdict", "description", "pros", "cons", "price"]
ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def main():
    with open(DATA, encoding="utf-8") as fh:
        doc = json.load(fh)

    errors, warnings = [], []
    seen = set()

    for i, b in enumerate(doc.get("bikes", [])):
        where = b.get("id") or "bike[%d]" % i

        for key in REQUIRED:
            if b.get(key) in (None, "", []):
                errors.append("%s: missing %s" % (where, key))

        if b.get("id"):
            if not ID_RE.match(b["id"]):
                errors.append("%s: id must be lower-case kebab-case" % where)
            if b["id"] in seen:
                errors.append("%s: duplicate id" % where)
            seen.add(b["id"])

        v = b.get("verdict")
        if isinstance(v, int) and not 1 <= v <= 10:
            errors.append("%s: verdict %s outside 1-10" % (where, v))

        yf, yt = b.get("year_from"), b.get("year_to")
        if isinstance(yf, int) and isinstance(yt, int) and yt < yf:
            errors.append("%s: year_to %s before year_from %s" % (where, yt, yf))

        p = b.get("price") or {}
        lo, hi = p.get("private"), p.get("dealer")
        if isinstance(lo, int) and isinstance(hi, int):
            if lo > hi:
                errors.append("%s: private %s above dealer %s" % (where, lo, hi))
            if hi > lo * 4:
                warnings.append("%s: private-to-dealer spread looks very wide (%s-%s)" % (where, lo, hi))
        conf = p.get("confidence")
        if conf not in ("verified", "researched", "thin", "unverified"):
            errors.append("%s: unknown confidence %r" % (where, conf))
        elif conf not in ("verified", "researched"):
            warnings.append("%s: price needs checking (%s, %s)" % (where, conf, p.get("source")))

        desc = b.get("description") or ""
        if len(desc) > 400:
            warnings.append("%s: description is %d chars, may overrun the box" % (where, len(desc)))

    for w in warnings:
        print("WARN  %s" % w)
    for e in errors:
        print("ERROR %s" % e)

    print("\n%d bikes, %d errors, %d warnings" % (len(doc.get("bikes", [])), len(errors), len(warnings)))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
