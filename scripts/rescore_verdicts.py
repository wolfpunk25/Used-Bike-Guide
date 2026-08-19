#!/usr/bin/env python3
"""Re-score the Verdict on "how good a buy is this?".

The old score measured how significant a motorcycle was, which correlated with
price at Spearman 0.63 and told a reader nothing the price column did not. This
scores the question a used-bike buyer actually asks: for what it costs, is this
a sensible thing to go and buy?

Signals are drawn from the pros/cons and description already written for each
entry, plus price and a few structural facts. Everything is additive from a
base of 6 and clamped to 1-10, so every score can be explained.

Run with --dry-run to see the effect without writing.
"""

import argparse
import collections
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "bikes.json")
BACKUP = os.path.join(ROOT, "data", "verdicts-significance-scale.csv")

BASE = 6.0

# --- things that make a bike a GOOD buy -------------------------------------
GOOD = [
    (r"bulletproof|indestructible|unburstable|nearly unkillable|impossible to break", 1.4, "durability"),
    (r"very reliable|reliability|dependable|tough as|extremely tough|legendary durability", 1.0, "reliability"),
    (r"superb value|excellent value|remarkable value|astonishing value|great value|bargain|keenly priced", 1.2, "value"),
    (r"cheap to run|cheap to own|low running costs|tiny running costs|economical|superb economy|astonishing economy", 0.9, "running costs"),
    (r"huge aftermarket|vast parts|huge parts|parts everywhere|big parts|strong club|club support|owners' club", 0.7, "parts/support"),
    (r"holds value|strong residuals|values firming|hold its price|holds up well", 0.8, "residuals"),
    (r"values? (?:rising|climbing|have risen)|strong values|appreciat|blue-chip|investment", 0.9, "appreciating"),
    (r"undervalued|overlooked|underrated|cheap for (?:what|the)|bargain|good value used", 0.7, "underpriced for what it is"),
    (r"easy to (?:ride|own|maintain|work on|fix)|simple to (?:fix|maintain)|easy to work on", 0.6, "ease of ownership"),
    (r"very cheap|dirt cheap|extremely cheap|absurdly cheap|cheap to buy", 0.8, "cheap to buy"),
    (r"versatile|does everything|do-everything|all-rounder|genuinely practical|practical", 0.5, "versatility"),
    (r"forgiving|approachable|easy-going|accessible", 0.4, "approachability"),
]

# --- things that make a bike a BAD buy --------------------------------------
BAD = [
    (r"expensive to service|servicing costs|expensive servicing|desmo servic|belt service|costly to maintain", -1.2, "servicing cost"),
    (r"parts (?:are )?(?:scarce|scarcity|hard|difficult)|parts availability|parts supply|spares are hard|unobtainable", -1.1, "parts risk"),
    (r"dealer network|dealer support|dealer coverage|thin dealer|small dealer", -0.8, "dealer support"),
    (r"weak residuals|depreciat|residuals are weak|values fall|loses value", -0.9, "depreciation"),
    (r"known (?:weak|failure)|weak spot|notorious|reg/rec|regulator|camshaft wear|main bearing|bottomless", -0.9, "known faults"),
    (r"specialist (?:parts|servicing|knowledge|work)|specialist maintenance", -0.9, "specialist needs"),
    (r"short service interval|service intervals|measured in hours|frequent (?:servicing|maintenance)", -0.9, "service intervals"),
    (r"thirsty|fuel range|tiny (?:tank|range)|small tank", -0.4, "running cost"),
    (r"rust|corrosion|finish (?:suffers|tarnish)", -0.5, "corrosion"),
    (r"two-stroke (?:costs|upkeep|running)|two-stroke maintenance", -0.7, "two-stroke upkeep"),
    (r"not road legal|pure racer|competition machine", -1.3, "not road usable"),
    (r"heavy|very heavy|vast weight|enormous weight", -0.25, "weight"),
    (r"unproven|long-term reliability unproven|build quality (?:is )?(?:basic|varies)|basic (?:build|finish|mechanicals)", -0.8, "build quality"),
    (r"most have been (?:thrashed|raced|ridden hard)|hard-ridden|many (?:have been )?(?:crashed|modified|tracked)", -0.6, "condition risk"),
    (r"fakes|authenticity|provenance is everything|replicas (?:abound|outnumber)", -0.9, "provenance risk"),
]

# Brands with no factory behind them any more — a real ownership risk.
ORPHANED = {"Buell", "Victory", "EBR", "Excelsior-Henderson", "Cannondale", "ATK",
            "Hercules", "Laverda", "Bimota", "Husaberg", "Metisse", "Bultaco", "Maico"}


def price_factor(b):
    """Price alone says nothing about whether a bike is a good buy — that was the
    flaw in the old significance score, inverted. What matters is capital at risk:
    a large sum is only a problem where the bike also depreciates or is expensive
    to keep. Where values are firm, a costly bike can be an excellent buy."""
    dealer = b["price"]["dealer"]
    text = " ".join([b["description"]] + b["pros"] + b["cons"]).lower()
    firm = re.search(r"values? (?:rising|climbing|firm|have risen)|strong values|holds value|"
                     r"strong residuals|blue-chip|investment|appreciat|collectable", text)
    if not dealer:
        return 0.0, ""
    if dealer >= 25000 and not firm:
        return -1.0, "large sum, values not firm"
    if dealer >= 12000 and not firm:
        return -0.5, "significant outlay"
    return 0.0, ""


# The absolute weights below are judgement calls, so the raw total is only
# meaningful as a RANKING. Scores are assigned by mapping that ranking onto a
# deliberate distribution, which gives the column a usable spread instead of
# piling everything onto two values — the flaw in the old significance scale.
CURVE = [(0.02, 10), (0.10, 9), (0.28, 8), (0.53, 7), (0.78, 6), (0.93, 5), (0.98, 4), (1.01, 3)]


def curve_score(rank_pct):
    for edge, val in CURVE:
        if rank_pct <= edge:
            return val
    return 3


def score(b):
    # Match each polarity against the right text. Reading both against one blob
    # meant a positive could score as a negative: "proper competition machine" is
    # a PRO of the KTM 450 EXC, but was being read as "not road usable".
    desc = (b["description"] + " " + (b.get("notes") or "")).lower()
    plus = (desc + " " + " ".join(b["pros"])).lower()
    minus = (desc + " " + " ".join(b["cons"])).lower()
    s = BASE
    why = []
    for pat, w, label in GOOD:
        if re.search(pat, plus):
            s += w; why.append("+%.1f %s" % (w, label))
    for pat, w, label in BAD:
        if re.search(pat, minus):
            s += w; why.append("%.1f %s" % (w, label))
    pf, plabel = price_factor(b)
    if pf:
        s += pf; why.append("%+.1f %s" % (pf, plabel))
    if b["make"] in ORPHANED:
        s -= 0.7; why.append("-0.7 orphaned marque")
    return s, why


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--show", type=int, default=0, help="print N worked examples")
    args = ap.parse_args()

    doc = json.load(open(DATA, encoding="utf-8"))
    bikes = doc["bikes"]
    old = {b["id"]: b["verdict"] for b in bikes}
    raw = {}
    for b in bikes:
        r, why = score(b)
        raw[b["id"]] = (r, why)
    # rank high-to-low, then map onto the curve
    order = sorted(bikes, key=lambda b: -raw[b["id"]][0])
    new = {}
    for i, b in enumerate(order):
        new[b["id"]] = (curve_score((i + 1) / len(order)), raw[b["id"]][1])

    dist_old = collections.Counter(old.values())
    dist_new = collections.Counter(v for v, _ in new.values())
    print("verdict distribution        OLD      NEW")
    for v in range(1, 11):
        if dist_old.get(v) or dist_new.get(v):
            print("   %2d/10   %5d   %5d" % (v, dist_old.get(v, 0), dist_new.get(v, 0)))
    moved = sum(1 for i in old if old[i] != new[i][0])
    print("\n   changed: %d of %d" % (moved, len(bikes)))

    if args.show:
        print("\nBiggest risers:")
        ups = sorted(bikes, key=lambda b: -(new[b["id"]][0] - old[b["id"]]))[:args.show]
        for b in ups:
            print("  %-32s %d -> %d  £%s  %s" % ((b["make"] + " " + b["model"])[:32],
                  old[b["id"]], new[b["id"]][0], b["price"]["dealer"], "; ".join(new[b["id"]][1][:4])))
        print("\nBiggest fallers:")
        downs = sorted(bikes, key=lambda b: (new[b["id"]][0] - old[b["id"]]))[:args.show]
        for b in downs:
            print("  %-32s %d -> %d  £%s  %s" % ((b["make"] + " " + b["model"])[:32],
                  old[b["id"]], new[b["id"]][0], b["price"]["dealer"], "; ".join(new[b["id"]][1][:4])))

    if args.dry_run:
        print("\nDRY RUN — nothing written.")
        return 0

    with open(BACKUP, "w", encoding="utf-8-sig", newline="") as fh:
        import csv
        w = csv.writer(fh); w.writerow(["id", "make", "model", "verdict_significance"])
        for b in bikes:
            w.writerow([b["id"], b["make"], b["model"], old[b["id"]]])
    for b in bikes:
        b["verdict"] = new[b["id"]][0]
    doc["meta"]["verdict_scale"] = ("How good a buy is this for what it costs — value, running "
                                    "costs, reliability, parts support and ownership risk. Not a "
                                    "measure of how significant the motorcycle is.")
    json.dump(doc, open(DATA, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    open(DATA, "a").write("\n")
    print("\nWritten. Previous scores saved to %s" % os.path.basename(BACKUP))
    return 0


if __name__ == "__main__":
    sys.exit(main())
