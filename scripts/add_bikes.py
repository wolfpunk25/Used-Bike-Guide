#!/usr/bin/env python3
"""Helper for bulk-adding entries to data/bikes.json.

Batch files hand us tuples in a fixed order; this turns them into full records,
generates stable ids, and refuses to introduce a duplicate. Prices added this
way are editorial estimates and are marked unverified so the front end keeps
flagging them until someone does a real price pass.

  (make, model, variant, category, year_from, year_to, cc, verdict,
   description, [pros], [cons], price_private, price_dealer)
"""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "bikes.json")

FIELDS = ("make model variant category year_from year_to engine_cc verdict "
          "description pros cons price_private price_dealer").split()


def slug(*parts):
    s = "-".join(str(p) for p in parts if p)
    s = s.lower().replace("&", "and").replace("+", "plus")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"-{2,}", "-", s).strip("-")


def add(batch, data_path=DATA):
    with open(data_path, encoding="utf-8") as fh:
        doc = json.load(fh)
    existing = {b["id"] for b in doc["bikes"]}

    added, skipped = [], []
    for row in batch:
        if len(row) != len(FIELDS):
            sys.exit("Row has %d fields, expected %d: %r" % (len(row), len(FIELDS), row[:3]))
        r = dict(zip(FIELDS, row))
        bike_id = slug(r["make"], r["model"], r["variant"], r["year_from"])
        if bike_id in existing:
            skipped.append(bike_id)
            continue
        existing.add(bike_id)
        doc["bikes"].append({
            "id": bike_id,
            "make": r["make"],
            "model": r["model"],
            "variant": r["variant"],
            "category": r["category"],
            "year_from": r["year_from"],
            "year_to": r["year_to"],
            "engine_cc": r["engine_cc"],
            "verdict": r["verdict"],
            "description": r["description"],
            "pros": list(r["pros"]),
            "cons": list(r["cons"]),
            "price": {
                "private": r["price_private"], "dealer": r["price_dealer"], "as_of": None,
                "source": "seed-estimate", "confidence": "unverified", "sample_size": 0,
            },
            "price_history": [],
        })
        added.append(bike_id)

    with open(data_path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    print("added %d, skipped %d duplicate(s); total now %d"
          % (len(added), len(skipped), len(doc["bikes"])))
    for s in skipped:
        print("  dup: %s" % s)
    return added
