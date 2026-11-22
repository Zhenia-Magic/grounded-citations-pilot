"""Day 2 write-up: how many citations in real OJS articles can be judged at all.

Unit of analysis: a citation context (one in-text callout in a body sentence).
Confidence intervals resample whole articles (cluster bootstrap), because
citations inside one article are not independent.

Output: results/day2_summary.md
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

RNG = np.random.default_rng(20261122)
LANG = {"EN": "en", "ES": "es"}
TIER_LABEL = {
    "full_text_oa": "Full text open (OpenAlex)", "abstract_only": "Abstract only",
    "metadata_only": "Resolved, no abstract or open text",
    "unresolved_book_or_report": "Unresolved: book or report", "unresolved_web": "Unresolved: web page",
    "unresolved_other": "Unresolved: other",
}


def as_bool(s):
    return s.astype(str).str.lower().eq("true")


def boot(df, num, den, reps=2000):
    """Ratio of sums with a 95% CI from resampling articles."""
    g = df.groupby("article_id").agg(n=(num, "sum"), d=(den, "sum"))
    est = g["n"].sum() / g["d"].sum() if g["d"].sum() else float("nan")
    if len(g) < 2:
        return est, float("nan"), float("nan")
    idx = RNG.integers(0, len(g), size=(reps, len(g)))
    n, d = g["n"].to_numpy()[idx].sum(1), g["d"].to_numpy()[idx].sum(1)
    r = n[d > 0] / d[d > 0]
    return est, np.percentile(r, 2.5), np.percentile(r, 97.5)


def fmt(t):
    est, lo, hi = t
    return "n/a" if np.isnan(est) else f"{100 * est:.0f}% ({100 * lo:.0f}–{100 * hi:.0f}%)"


def main():
    A = pd.read_csv("data/day2/parsed_articles.csv", dtype=str, keep_default_na=False)
    C = pd.read_csv("data/day2/contexts.csv", dtype=str, keep_default_na=False)
    R = pd.read_csv("data/day2/references_resolved.csv", dtype=str, keep_default_na=False)
    metas = {p.stem: json.loads(p.read_text()) for p in Path("data/raw/pdf").glob("*.json")}

    A["pdf_ok"] = A["article_id"].map(lambda i: metas.get(i, {}).get("status") == "ok")
    A["parsed"] = (A["tei"] == "ok") & ~as_bool(A.get("parse_failed", pd.Series("True", index=A.index)))
    A["linked_ok"] = A["parsed"] & ~as_bool(A["linking_failed"])
    A["lang_ok"] = A.apply(lambda r: r["body_lang_detected"] == LANG[r["lang_stratum"]], axis=1)
    A["usable"] = A["linked_ok"] & A["lang_ok"]
    usable = set(A.loc[A["usable"], "article_id"])

    C = C.merge(A[["article_id", "lang_stratum", "field"]], on="article_id", how="left")
    C = C.merge(R[["article_id", "bibl_id", "tier", "is_retracted"]], on=["article_id", "bibl_id"], how="left")
    C["linked"] = C["link_check"].isin(["consistent", "rescued"])
    C["outcome"] = np.where(C["linked"], C["tier"].fillna("unresolved_other"),
                            np.where(C["link_check"] == "unlinked", "unlinked", "link_failed_check"))
    C["full"] = C["outcome"].eq("full_text_oa").astype(int)
    C["abstract"] = C["outcome"].eq("abstract_only").astype(int)
    C["judgeable"] = C["full"] + C["abstract"]
    C["one"] = 1
    U = C[C["article_id"].isin(usable)].copy()

    L = ["# Day 2: can the citations be judged at all?", "",
         "Pipeline: GROBID 0.9.1 (CRF models) on the Day-1 PDFs, citation links checked against the "
         "callouts, references resolved through Crossref and OpenAlex. Intervals resample whole articles.", "",
         "## Article funnel", "",
         "| Stage | English stratum | Spanish stratum | Total |", "|---|---|---|---|"]
    def row(label, mask):
        en = int((mask & (A["lang_stratum"] == "EN")).sum())
        es = int((mask & (A["lang_stratum"] == "ES")).sum())
        L.append(f"| {label} | {en} | {es} | {en + es} |")
    row("Sampled", A["article_id"].notna())
    row("PDF downloaded", A["pdf_ok"])
    row("Parsed with body text and a reference list", A["parsed"])
    row("Citation links mostly resolvable (≥50% of callouts)", A["linked_ok"])
    row("Body text in the stratum's language", A["linked_ok"] & A["lang_ok"])
    lost_lang = A[A["linked_ok"] & ~A["lang_ok"]]
    L += ["", f"Usable articles: {len(usable)}. "
          f"{len(lost_lang)} parsed articles were in another language than their stratum "
          f"({', '.join(sorted(lost_lang['body_lang_detected'].replace('', 'unknown')))}), all tagged as the "
          "stratum language by their journals. Articles where linking failed mostly use footnote citation "
          "styles, which GROBID reads as numbered callouts.", ""]

    L += ["## What happens to each citation (usable articles)", "",
          f"{len(U):,} in-text citations in {U['article_id'].nunique()} articles.", "",
          "| Outcome | Citations | Share |", "|---|---|---|"]
    order = ["full_text_oa", "abstract_only", "metadata_only", "unresolved_book_or_report",
             "unresolved_web", "unresolved_other", "link_failed_check", "unlinked"]
    labels = {**TIER_LABEL, "link_failed_check": "Linked to the wrong or a junk entry",
              "unlinked": "Not linked to any reference"}
    for o in order:
        n = int((U["outcome"] == o).sum())
        L.append(f"| {labels[o]} | {n} | {100 * n / len(U):.0f}% |")
    L += ["",
          f"- **Judgeable at all** (full text or abstract): {fmt(boot(U, 'judgeable', 'one'))} of citations.",
          f"- **Judgeable against full text**: {fmt(boot(U, 'full', 'one'))}.",
          f"- Abstract only, which can confirm support but never refute it: {fmt(boot(U, 'abstract', 'one'))}.",
          f"- Citations in methods sections, which the design treats as cannot-judge by default: "
          f"{100 * as_bool(U['methods_section']).mean():.0f}%.",
          "- For comparison, the proposal's untested guess was 25–40% full text, 10–20% abstract only and "
          "40–65% not judgeable.", ""]

    L += ["## By language and field", "",
          "| Group | Articles | Citations | Judgeable at all | Full text |", "|---|---|---|---|---|"]
    for label, sub in ([("English stratum", U[U["lang_stratum"] == "EN"]),
                        ("Spanish stratum", U[U["lang_stratum"] == "ES"])]
                       + [(f, U[U["field"] == f]) for f in ("health", "scitech", "social", "humanities")]):
        if len(sub):
            L.append(f"| {label} | {sub['article_id'].nunique()} | {len(sub)} | "
                     f"{fmt(boot(sub, 'judgeable', 'one'))} | {fmt(boot(sub, 'full', 'one'))} |")

    P = R[as_bool(R["needed"])]
    src = P["doi_source"].replace("", "none").value_counts()
    L += ["", "## Cited works (references cited at least once in a usable article)", "",
          f"- Distinct cited works: {len(P):,}. Across all parsed articles GROBID also produced "
          f"{int((~as_bool(pd.read_csv('data/day2/references.csv', dtype=str)['ref_like'])).sum())} junk entries "
          "such as checklist lines, which are excluded.",
          f"- DOI printed in the reference: {src.get('in_reference', 0)}; found by Crossref search: "
          f"{src.get('crossref_match', 0)}; no DOI found: {src.get('none', 0)}.",
          "- Kinds as parsed: " + ", ".join(f"{k} {v}" for k, v in P["kind"].value_counts().items()) + ".",
          f"- Open access per OpenAlex: {int(as_bool(P['is_oa']).sum())} of {int(as_bool(P['oa_found']).sum())} "
          "resolved works.",
          f"- Retracted works cited: {int(as_bool(P['is_retracted']).sum())}.", ""]
    retracted = P[as_bool(P["is_retracted"])]
    for r in retracted.itertuples():
        L.append(f"  - {r.article_id}: {r.first_author} ({r.year}), {r.oa_title[:110]}")

    L += ["", "## Caveats", "",
          "- Open access means OpenAlex knows an open copy. Day 3 has to fetch those copies, and some "
          "will be behind bot walls or dead links, so full-text shares here are upper bounds.",
          "- Crossref matches had to agree on title and year or author, so some findable works count "
          "as unresolved: precision was preferred to recall.",
          "- GROBID ran with its light CRF models; its deep-learning models link more callouts but need "
          "a 15 GB image.",
          f"- Small sample: {len(usable)} usable articles from {A.loc[A['usable'], 'article_id'].str.split('__').str[0].nunique()} "
          "journals, so per-field rows are indicative only."]
    inputs = Path("data/day3/ojs_inputs.jsonl")
    if inputs.exists():  # retrieval check run during Day-3 prep on the sampled citations
        items = [json.loads(l) for l in inputs.read_text(encoding="utf-8").splitlines() if l.strip()]
        metas = list(json.loads(Path("data/day3/open_works.json").read_text()).values())
        st = pd.Series([m["status"] for m in metas]).value_counts()
        ft = [i for i in items if i["day2_outcome"] == "full_text_oa"]
        got = sum(i["evidence"] == "full_text" for i in ft)
        share_ft = boot(U, "full", "one")[0]
        L += ["", "## Retrieval check: can the open copies actually be fetched?", "",
              f"For the {len(items)} citations prepared for judging, the open copies were fetched as a client "
              "would: the OpenAlex PDF link, else the landing page's `citation_pdf_url` tag, respecting robots.txt.", "",
              f"- Cited works listed as open access: {len(metas)}; PDF retrieved: {st.get('ok', 0)} "
              f"({100 * st.get('ok', 0) / max(1, len(metas)):.0f}%); behind bot protection: "
              f"{st.get('blocked_bot_protection', 0)}; no PDF found: {st.get('no_pdf', 0)}.",
              f"- Sampled citations whose source OpenAlex lists as open: {len(ft)}; full text actually obtained "
              f"for {got} ({100 * got / max(1, len(ft)):.0f}%); the rest fall back to the abstract where one exists.",
              f"- Applied to the headline, citations judgeable against retrieved full text are roughly "
              f"{100 * share_ft * got / max(1, len(ft)):.0f}% rather than {100 * share_ft:.0f}%. Publisher "
              "text-mining access, Europe PMC and repository copies could close part of that gap.", ""]
    Path("results/day2_summary.md").write_text("\n".join(L) + "\n")
    U.to_csv("data/day2/contexts_usable.csv", index=False)
    print("\n".join(L))


if __name__ == "__main__":
    main()
