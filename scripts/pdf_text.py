#!/usr/bin/env python3
"""Minimal PDF text extractor (stdlib only).

There is no pdftotext or PDF library on this machine, and these dealer stock
lists are browser print-to-PDFs, so the text is really in there — it just
needs pulling out of the Flate-compressed content streams. Good enough to
recover model names and prices; not a general-purpose PDF parser.
"""

import re
import sys
import zlib


def streams(data):
    for m in re.finditer(rb"stream\r?\n", data):
        start = m.end()
        end = data.find(b"endstream", start)
        if end == -1:
            continue
        raw = data[start:end].rstrip(b"\r\n")
        try:
            yield zlib.decompress(raw)
        except zlib.error:
            try:
                yield zlib.decompressobj().decompress(raw)
            except zlib.error:
                continue


def unescape(s):
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == 92 and i + 1 < len(s):          # backslash
            nxt = s[i + 1:i + 2]
            mapping = {b"n": b"\n", b"r": b"\r", b"t": b"\t",
                       b"(": b"(", b")": b")", b"\\": b"\\"}
            if nxt in mapping:
                out.append(mapping[nxt]); i += 2; continue
            if nxt.isdigit():                    # octal escape
                oct_digits = s[i + 1:i + 4]
                try:
                    out.append(bytes([int(oct_digits, 8) & 0xFF])); i += 1 + len(oct_digits); continue
                except ValueError:
                    pass
            i += 2; continue
        out.append(bytes([c])); i += 1
    return b"".join(out)


def text_from(stream):
    parts = []
    # (literal) Tj  and  [ (a) -250 (b) ] TJ
    for m in re.finditer(rb"\((?:[^()\\]|\\.)*\)", stream):
        parts.append(unescape(m.group(0)[1:-1]))
    return b"".join(parts)


def looks_like_text_stream(s):
    """Image streams decompress to binary that happens to contain parentheses,
    so require the PDF text operators a real content stream always carries."""
    return b"BT" in s and b"ET" in s and (b"Tf" in s or b"Td" in s or b"TJ" in s)


def sensible(t):
    """Reject extracted runs that are mostly punctuation or control bytes."""
    if len(t) < 8:
        return False
    good = sum(1 for c in t if c.isalnum() or c in " ,.&/-()£'")
    return good / len(t) > 0.80


def extract(path):
    with open(path, "rb") as fh:
        data = fh.read()
    chunks = []
    for s in streams(data):
        if not looks_like_text_stream(s):
            continue
        t = text_from(s).decode("latin-1", "replace")
        if sensible(t):
            chunks.append(t)
    return "\n".join(chunks)


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(extract(p))
