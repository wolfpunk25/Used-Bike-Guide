#!/usr/bin/env python3
"""Stamp asset URLs in index.html with a hash of their contents.

GitHub Pages serves index.html, app.js and style.css with max-age=600 and no
versioning, so a browser can hold one file for ten minutes while fetching a
fresh copy of another. A stale index.html paired with a new app.js is the bad
case: app.js looks up an element the old markup does not have, render() throws
on the null, and the whole listing vanishes.

Hashing the query string ties them together. Whenever index.html is current,
the assets it names are the ones that shipped with it.

Run this after editing anything in assets/ and before committing.
"""

import hashlib
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "index.html")
PATTERN = re.compile(r'((?:href|src)=")(assets/[A-Za-z0-9_.-]+\.(?:js|css))(?:\?v=[0-9a-f]+)?(")')


def digest(rel):
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        sys.exit("index.html references %s, which does not exist" % rel)
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:10]


def main():
    with open(PAGE, encoding="utf-8") as fh:
        html = fh.read()

    seen = []

    def swap(m):
        rel = m.group(2)
        v = digest(rel)
        seen.append((rel, v))
        return "%s%s?v=%s%s" % (m.group(1), rel, v, m.group(3))

    out = PATTERN.sub(swap, html)
    if not seen:
        sys.exit("No asset references found in index.html — has the markup changed?")

    changed = out != html
    if changed:
        with open(PAGE, "w", encoding="utf-8") as fh:
            fh.write(out)
    for rel, v in seen:
        print("  %-24s v=%s" % (rel, v))
    print("index.html %s" % ("updated" if changed else "already current"))


if __name__ == "__main__":
    main()
