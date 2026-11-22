"""Score judge outputs on the Citation-Integrity benchmark sample.

    python src/score_benchmark.py data/day3/judgments/claude-opus-5-5 data/day3/judgments/gpt-6.2-astra

Three classes as in Sarol et al.: ACCURATE / NOT_ACCURATE / NEI. Reports accuracy
(= micro-F1 for single-label classification), macro-F1 with a bootstrap 95% CI,
per-class precision and recall, and the confusion matrix, for the model's raw label and
for the label after the publication rules. Items answered by a fallback model, refusals
and errors are counted and excluded.

Given two judgment folders, it also scores the two-judge rule (judge_prompt.combine) on the
items both judged, and reports how often the two judges agree with each other (Cohen's
kappa), to set beside their agreement with the experts.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np

from benchmark_ci import TO_GOLD
from judge_common import load_items, source_key
from judge_prompt import combine

CLASSES = ["ACCURATE", "NOT_ACCURATE", "NEI"]
LABEL_ORDER = ["supported", "partly_supported", "misquoted_number", "not_supported", "contradicted",
               "unrelated", "cannot_judge"]
RNG = np.random.default_rng(7)


def label_precision(name, gold, labels):
    """How often each label agrees with the experts' class (the TO_GOLD mapping). For the
    negative labels this is the precision a published note would have."""
    lines = [f"#### {name}: precision by label", "",
             "| Label | Given | Experts: ACCURATE | NOT_ACCURATE | NEI | Precision |", "|---|---|---|---|---|---|"]
    for lab in LABEL_ORDER:
        idx = [k for k, l in enumerate(labels) if l == lab]
        if idx:
            c = Counter(gold[k] for k in idx)
            lines.append(f"| {lab} | {len(idx)} | {c['ACCURATE']} | {c['NOT_ACCURATE']} | {c['NEI']} "
                         f"| {c[TO_GOLD.get(lab, 'NEI')] / len(idx):.2f} |")
    return "\n".join(lines + [""])


def macro_f1(gold, pred):
    f1s = []
    for c in CLASSES:
        tp = sum(g == c and p == c for g, p in zip(gold, pred))
        fp = sum(g != c and p == c for g, p in zip(gold, pred))
        fn = sum(g == c and p != c for g, p in zip(gold, pred))
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(2 * prec * rec / (prec + rec) if prec + rec else 0.0)
    return float(np.mean(f1s)), f1s


def report(name, gold, pred):
    n = len(gold)
    acc = sum(g == p for g, p in zip(gold, pred)) / n
    mf, f1s = macro_f1(gold, pred)
    boots = []
    g_arr, p_arr = np.array(gold), np.array(pred)
    for _ in range(2000):
        idx = RNG.integers(0, n, n)
        boots.append(macro_f1(g_arr[idx].tolist(), p_arr[idx].tolist())[0])
    lo, hi = np.percentile(boots, [2.5, 97.5])
    lines = [f"### {name}", "", f"- Items: {n}; accuracy (micro-F1) {acc:.2f}; macro-F1 {mf:.2f} (95% CI {lo:.2f}–{hi:.2f}). "
             "Published best system: micro-F1 0.59, macro-F1 0.52.", "",
             "| Gold \\ predicted | " + " | ".join(CLASSES) + " | Recall | F1 |", "|---" * (len(CLASSES) + 3) + "|"]
    for c, f1 in zip(CLASSES, f1s):
        row = [sum(g == c and p == d for g, p in zip(gold, pred)) for d in CLASSES]
        rec = row[CLASSES.index(c)] / sum(row) if sum(row) else 0.0
        lines.append(f"| {c} | " + " | ".join(map(str, row)) + f" | {rec:.2f} | {f1:.2f} |")
    prec = [sum(g == c and p == c for g, p in zip(gold, pred)) / max(1, sum(p == c for p in pred)) for c in CLASSES]
    lines += ["", "Precision: " + ", ".join(f"{c} {p:.2f}" for c, p in zip(CLASSES, prec)), ""]
    return "\n".join(lines)


def kappa(a, b):
    """Observed agreement and Cohen's kappa between two label lists."""
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in CLASSES)
    return po, ((po - pe) / (1 - pe) if pe < 1 else 1.0)


def load(d):
    recs = [json.loads(p.read_text()) for p in sorted(Path(d).glob("ci_*.json"))]
    status = Counter("fallback" if r.get("fallback_ran") else ("refusal" if r.get("stop_reason") == "refusal"
                     else ("error" if r.get("error") else "ok")) for r in recs)
    ok = {r["item_id"]: r for r in recs if r.get("verdict") and not r.get("fallback_ran")}
    return recs, status, ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+", help="one folder of judgment files per model")
    ap.add_argument("--out", default="results/day3_benchmark.md")
    args = ap.parse_args()
    items = {r["item_id"]: r for r in load_items("data/day3/ci_inputs.jsonl")}
    gold = {i: r["gold"] for i, r in items.items()}
    n_sources = len({source_key(r) for r in items.values()})
    out = ["# Citation-Integrity benchmark results", ""]
    judged = {}
    for d in map(Path, args.dirs):
        recs, status, ok = load(d)
        judged[d.name] = ok
        rows = list(ok.values())
        qv = sum(r["final"]["quotes_verified"] for r in rows), sum(r["final"]["quotes_total"] for r in rows)
        spent = sum(r.get("cost_usd", 0) for r in recs)
        out += [f"## {d.name}", "", f"- Judged: {len(recs)} ({dict(status)}); spent ${spent:.2f}.",
                f"- Quotes found verbatim in the source: {qv[0]} of {qv[1]}."]
        fb = Counter(source_key(items[r["item_id"]]) for r in recs if r.get("fallback_ran") and r["item_id"] in items)
        if fb:
            out.append(f"- Answered by a fallback model and left out: {sum(fb.values())} items, from {len(fb)} of the "
                       f"{n_sources} cited sources ({', '.join(map(str, sorted(fb.values(), reverse=True)))} items each), "
                       "so the scores below do not cover those sources evenly.")
        out.append("")
        if rows:
            g = [gold[r["item_id"]] for r in rows]
            raw = [TO_GOLD.get(r["verdict"]["label"], "NEI") for r in rows]
            fin = [TO_GOLD.get(r["final"]["final_label"], "NEI") for r in rows]
            out += [report("Model label", g, raw), report("After publication rules", g, fin),
                    label_precision(d.name, g, [r["final"]["final_label"] for r in rows])]
    if len(judged) == 2:
        (na, a), (nb, b) = judged.items()
        both = sorted(set(a) & set(b))
        if both:
            la = [a[i]["final"]["final_label"] for i in both]
            lb = [b[i]["final"]["final_label"] for i in both]
            po, k = kappa([TO_GOLD.get(x, "NEI") for x in la], [TO_GOLD.get(x, "NEI") for x in lb])
            comb = [TO_GOLD.get(combine(x, y), "NEI") for x, y in zip(la, lb)]
            out += [f"## Both judges: {na} and {nb}", "",
                    f"- Items both judged: {len(both)}. The judges agree with each other on {100 * po:.0f}% "
                    f"of them (Cohen's kappa {k:.2f}; three classes, after the publication rules).",
                    "- Rule: support only when both say supported; a negative only when both give one "
                    "(the milder if they differ); otherwise cannot judge.",
                    "- Each judge is also scored on these shared items alone, so that items one judge "
                    "lost to a refusal or fallback do not tilt the comparison.", "",
                    report("Two-judge rule", [gold[i] for i in both], comb),
                    label_precision("Two-judge rule", [gold[i] for i in both],
                                    [combine(x, y) for x, y in zip(la, lb)]),
                    report(f"{na} on the shared items", [gold[i] for i in both], [TO_GOLD.get(x, "NEI") for x in la]),
                    report(f"{nb} on the shared items", [gold[i] for i in both], [TO_GOLD.get(x, "NEI") for x in lb])]
    text = "\n".join(out)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
