"""Day 3 prep: build judge inputs for the Citation-Integrity benchmark (no model calls).

Gold labels follow the authors' three classes (ACCURATE / NOT_ACCURATE / NOT ENOUGH INFO):
a claim whose evidence is all ACCURATE is ACCURATE; any other error label makes it
NOT_ACCURATE; no evidence (or only IRRELEVANT) is NEI. This is a claim-level
approximation of their setup, so compare with their 0.59 micro-F1 / 0.52 macro-F1
as a reference point, not a replication.

Output: data/day3/ci_inputs.jsonl (a seeded random sample of N_CLAIMS test claims)
"""
import json
import random
from collections import Counter
from pathlib import Path

from judge_prompt import bm25_top

N_CLAIMS, TOP_K, SEED = 300, 15, 20261122
MAX_FULL_CHARS = 120_000  # about 30k tokens
SRC = Path("data/raw/citation_integrity")
OUT = Path("data/day3")
TO_GOLD = {"supported": "ACCURATE", "partly_supported": "NOT_ACCURATE", "not_supported": "NOT_ACCURATE",
           "contradicted": "NOT_ACCURATE", "misquoted_number": "NOT_ACCURATE", "unrelated": "NEI",
           "cannot_judge": "NEI"}


def load(p):
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def gold_label(evidence):
    labels = [e["label"] for entries in (evidence or {}).values() for e in entries]
    labels = [l for l in labels if l != "IRRELEVANT"]
    if not labels:
        return "NEI", labels
    return ("ACCURATE" if all(l == "ACCURATE" for l in labels) else "NOT_ACCURATE"), labels


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    claims = load(SRC / "claims-test.jsonl")
    corpus = {d["doc_id"]: d for d in load(SRC / "corpus.jsonl")}
    rng = random.Random(SEED)
    sample = rng.sample(claims, min(N_CLAIMS, len(claims)))
    rows, mixed = [], 0
    for c in sample:
        gold, fine = gold_label(c.get("evidence"))
        mixed += len(set(fine)) > 1
        paras = [" ".join(corpus[i]["abstract"]) for i in c["cited_doc_ids"] if i in corpus]
        text = c["claim"].replace("<|multi_cit|>", "").strip()
        multi = "<|multi_cit|>" in c["claim"]
        # Whole article when it fits (identical across claims, so it caches); else BM25 top paragraphs.
        if sum(map(len, paras)) <= MAX_FULL_CHARS:
            shown = paras
        else:
            shown = [paras[i] for i in bm25_top(text, paras, k=TOP_K)]
        rows.append({
            "item_id": f"ci_{c['id']}", "gold": gold, "fine_labels": sorted(set(fine)),
            "ctx": {"section": "unknown", "prev_sentence": "", "next_sentence": "",
                    "sentence": text + " [[citation]]" + (" (this sentence also cites other sources)" if multi else "")},
            "source_meta": "a biomedical research article (title withheld in the benchmark)",
            "evidence": "full_text", "passages": shown, "n_paragraphs": len(paras),
        })
    with (OUT / "ci_inputs.jsonl").open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(rows)} benchmark items; gold: {Counter(r['gold'] for r in rows).most_common()}; "
          f"claims with mixed fine labels: {mixed}")
    chars = sorted(sum(map(len, r["passages"])) for r in rows)
    print(f"shown source chars per item: median {chars[len(chars) // 2]}, p90 {chars[int(len(chars) * 0.9)]}, "
          f"max {chars[-1]}; items with whole article: "
          f"{sum(len(r['passages']) == r['n_paragraphs'] for r in rows)}; distinct sources: "
          f"{len({chr(10).join(r['passages']) for r in rows})}")
    print("example sentence:", rows[0]["ctx"]["sentence"][:200])


if __name__ == "__main__":
    main()
