"""Day 3 write-up for the OJS citations, and the blind Day-4 hand-check kit.

    python src/summarise_day3.py data/day3/judgments/claude-opus-5-5 data/day3/judgments/gpt-6.2-sol

Reports, for each judge and for the two-judge rule (judge_prompt.combine), the final labels on
the sampled OJS citations: overall, by evidence type and by language stratum, with run status,
quote checks, cost and how often the two judges agree. Writes results/day3_ojs.md.

Also builds the Day-4 hand-check in data/day4/: up to 50 English citations. It takes every
citation that is negative under the two-judge rule, up to 8 that only one judge marked negative,
up to 15 that both judges call supported (the positive notes the design leads with), then fills
up with other disagreements, each group sampled with a fixed seed. The sheet and item files are
blind: they show the evidence the judges saw but not their labels, which are in
handcheck_key.csv. Label first, then open the key. An existing sheet is never overwritten, so
labels already entered are safe.
"""
import argparse
import csv
import json
import random
from collections import Counter
from pathlib import Path

from judge_common import load_items
from judge_prompt import NEGATIVE, SYSTEM, combine

SEED, N_CHECK = 20261124, 50
GROUPS = ["supported", "negative", "unrelated", "cannot_judge"]
STRATA = {1: "negative under the two-judge rule", 2: "negative by one judge only",
          3: "other disagreement", 4: "supported by both judges"}
QUOTA = {1: N_CHECK, 2: 8, 4: 15, 3: N_CHECK}  # filled in this order, up to N_CHECK in all


def group(label):
    return "negative" if label in NEGATIVE - {"unrelated"} else label


def status(r):
    if r is None:
        return "missing"
    if r.get("fallback_ran"):
        return "fallback"
    if r.get("stop_reason") == "refusal":
        return "refusal"
    return "ok" if r.get("verdict") and not r.get("error") else "error"


def final(r):
    return r["final"]["final_label"] if status(r) == "ok" else None


def load(d, ids):
    recs = {}
    for p in Path(d).glob("*.json"):
        r = json.loads(p.read_text())
        if r["item_id"] in ids:
            recs[r["item_id"]] = r
    return recs


def label_table(rows):
    """rows: (name, labels). Counts and shares of the four label groups."""
    out = ["| | Citations | " + " | ".join(g.replace("_", " ") for g in GROUPS) + " |",
           "|---" * (len(GROUPS) + 2) + "|"]
    for name, labels in rows:
        c, n = Counter(group(l) for l in labels), len(labels)
        out.append(f"| {name} | {n} | " + " | ".join(f"{c[g]} ({100 * c[g] / n:.0f}%)" if n else "–" for g in GROUPS) + " |")
    return out


def kappa(a, b):
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(g) / n) * (b.count(g) / n) for g in GROUPS)
    return po, ((po - pe) / (1 - pe) if pe < 1 else 1.0)


def item_markdown(n, it):
    c = it["ctx"]
    kind = ("the full text" if it["evidence"] == "full_text"
            else "only the abstract, which can confirm support but cannot show that support is missing")
    passages = "\n\n".join(f"[passage {i + 1}]\n{p}" for i, p in enumerate(it["passages"]))
    labels = SYSTEM.split("Labels:\n", 1)[1].split("\n\nJudge only", 1)[0]
    return (f"# Item {n}: {it['item_id']}\n\n"
            f"Field: {it['field']} · Evidence shown: {kind} · DOI: {it.get('doi') or 'none'}\n\n"
            "## Citing context\n\n"
            f"Section: {c.get('section') or 'unknown'}\n\n"
            f"Previous sentence: {c.get('prev_sentence') or '-'}\n\n"
            f"**Citing sentence:** {c['sentence']}\n\n"
            f"Next sentence: {c.get('next_sentence') or '-'}\n\n"
            "Judge only what the citing sentence attributes to the citation in [[double brackets]].\n\n"
            f"## Cited source\n\n{it['source_meta']}\n\n{passages}\n\n"
            "## Labels\n\nWrite one label in handcheck_sheet.csv, with the minutes you spent.\n\n"
            f"{labels}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("judge_a")
    ap.add_argument("judge_b")
    args = ap.parse_args()
    items = {it["item_id"]: it for it in load_items("data/day3/ojs_inputs.jsonl")}
    na, nb = Path(args.judge_a).name, Path(args.judge_b).name
    A, B = load(args.judge_a, items), load(args.judge_b, items)

    L = [f"# Day 3: what two judges said about {len(items)} OJS citations", "",
         f"Judges: {na} and {nb}, with the same prompt, output schema and publication rules. Labels are "
         "after those rules. The two-judge rule gives the label a note would carry: support only when both "
         "judges say supported, a negative only when both give one, otherwise cannot judge.", "",
         "## Runs", "",
         "| Judge | ok | refusal | fallback | error | missing | Quotes found in the source | Cost |",
         "|---|---|---|---|---|---|---|---|"]
    for name, R in ((na, A), (nb, B)):
        st = Counter(status(R.get(i)) for i in items)
        ok = [R[i] for i in items if status(R.get(i)) == "ok"]
        qv = sum(r["final"]["quotes_verified"] for r in ok), sum(r["final"]["quotes_total"] for r in ok)
        cost = sum(r.get("cost_usd", 0) for r in R.values())
        L.append(f"| {name} | {st['ok']} | {st['refusal']} | {st['fallback']} | {st['error']} | {st['missing']} "
                 f"| {qv[0]} of {qv[1]} | ${cost:.2f} |")

    la = {i: final(A[i]) for i in items if final(A.get(i))}
    lb = {i: final(B[i]) for i in items if final(B.get(i))}
    both = [i for i in items if i in la and i in lb]
    comb = {i: combine(la[i], lb[i]) for i in both}
    L += ["", "## Labels", ""] + label_table(
        [(na, list(la.values())), (nb, list(lb.values())), ("Two-judge rule", list(comb.values()))])
    L += ["", "Two-judge rule by evidence and by language stratum:", ""] + label_table(
        [("Full text", [comb[i] for i in both if items[i]["evidence"] == "full_text"]),
         ("Abstract only", [comb[i] for i in both if items[i]["evidence"] != "full_text"]),
         ("English stratum", [comb[i] for i in both if items[i]["lang_stratum"] == "EN"]),
         ("Spanish stratum", [comb[i] for i in both if items[i]["lang_stratum"] == "ES"])])
    if both:
        po, k = kappa([group(la[i]) for i in both], [group(lb[i]) for i in both])
        neg = lambda labels: sum(group(l) == "negative" for l in labels)
        L += ["", "## Agreement between the judges", "",
              f"- Same label group on {100 * po:.0f}% of the {len(both)} citations both judged "
              f"(Cohen's kappa {k:.2f} over the four groups).",
              f"- Negative labels: {neg(la[i] for i in both)} from {na}, {neg(lb[i] for i in both)} from {nb}, "
              f"{neg(comb.values())} from both, which is what the two-judge rule keeps.",
              "- Abstract-only evidence can never yield a negative label: the publication rules turn it into "
              "cannot judge."]

    def stratum(i):
        if comb[i] in NEGATIVE:
            return 1
        if (la[i] in NEGATIVE) != (lb[i] in NEGATIVE):
            return 2
        if la[i] != lb[i]:
            return 3
        return 4 if la[i] == "supported" else 5  # both cannot judge: nothing to check

    rng = random.Random(SEED)
    en = sorted(i for i in both if items[i]["lang_stratum"] == "EN")
    picked = []
    for s in (1, 2, 4, 3):
        pool = [i for i in en if stratum(i) == s]
        rng.shuffle(pool)
        picked += [(s, i) for i in pool[: max(0, min(QUOTA[s], N_CHECK - len(picked)))]]
    rng.shuffle(picked)  # mixed order, so the sheet does not show which group an item came from
    out = Path("data/day4")
    sheet = out / "handcheck_sheet.csv"
    if sheet.exists():
        L += ["", f"## Day-4 hand-check kit", "", f"Already in {out}/ and left untouched; delete the folder to rebuild it."]
    else:
        (out / "items").mkdir(parents=True, exist_ok=True)
        with sheet.open("w", newline="", encoding="utf-8-sig") as fs, \
                (out / "handcheck_key.csv").open("w", newline="", encoding="utf-8-sig") as fk:
            ws, wk = csv.writer(fs), csv.writer(fk)
            ws.writerow(["n", "item_id", "file", "field", "evidence", "human_label", "minutes", "notes"])
            wk.writerow(["n", "item_id", "group", na, nb, "two_judge_rule"])
            for n, (s, i) in enumerate(picked, start=1):
                f = f"items/{n:02d}_{i}.md"
                (out / f).write_text(item_markdown(n, items[i]), encoding="utf-8")
                ws.writerow([n, i, f, items[i]["field"], items[i]["evidence"], "", "", ""])
                wk.writerow([n, i, STRATA[s], la[i], lb[i], comb[i]])
        counts = Counter(s for s, _ in picked)
        L += ["", "## Day-4 hand-check kit", "",
              f"{len(picked)} English citations in {out}/: "
              + "; ".join(f"{counts[s]} {STRATA[s]}" for s in STRATA) + ".",
              "The sheet and item files show the evidence the judges saw, without their labels. "
              "Label every item in handcheck_sheet.csv, with the minutes each took, before opening handcheck_key.csv."]
    Path("results/day3_ojs.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
