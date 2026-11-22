"""Download the Citation-Integrity benchmark (Sarol, Schneider & Kilicoglu 2024; MIT licence)
in its MultiVerS format and print its structure.

claims-test.jsonl holds the labelled citing statements (test split only: it is our external
benchmark); corpus.jsonl holds the cited articles' sentences for every split.
"""
import json
from collections import Counter
from pathlib import Path

import requests

from harvest_oai import UA

RAW = "https://raw.githubusercontent.com/ScienceNLP-Lab/Citation-Integrity/main"
OUT = Path("data/raw/citation_integrity")
OUT.mkdir(parents=True, exist_ok=True)
for name in ("Data/multivers-format/claims-test.jsonl", "Data/multivers-format/corpus.jsonl", "LICENSE",
             "README.md"):
    dest = OUT / Path(name).name
    if not dest.exists():
        r = requests.get(f"{RAW}/{name}", headers={"User-Agent": UA}, timeout=180)
        r.raise_for_status()
        dest.write_bytes(r.content)
    print(f"{dest} {dest.stat().st_size / 1e3:.0f} KB")


def load(p):
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


claims, corpus = load(OUT / "claims-test.jsonl"), load(OUT / "corpus.jsonl")
print("claims:", len(claims), "| corpus docs:", len(corpus))
print("claim keys:", list(claims[0]), "| corpus keys:", list(corpus[0]))
print("first claim:", json.dumps(claims[0], ensure_ascii=False)[:700])
print("first doc:", json.dumps(corpus[0], ensure_ascii=False)[:500])
labels = Counter()
for c in claims:
    ev = c.get("evidence") or {}
    if not ev:
        labels["(no evidence)"] += 1
    for doc_ev in ev.values():
        for e in (doc_ev if isinstance(doc_ev, list) else [doc_ev]):
            labels[e.get("label")] += 1
print("evidence labels:", labels.most_common())
print("doc_ids per claim:", Counter(len(c.get("doc_ids", [])) for c in claims).most_common(5))
sizes = [len(d.get("abstract", d.get("sentences", []))) for d in corpus]
print("sentences per cited doc: median", sorted(sizes)[len(sizes) // 2], "max", max(sizes))
