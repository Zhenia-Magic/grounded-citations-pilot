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
    return "n/a" if np.isnan(est) else f"{100 * est:.0f}% ({100 * lo:.0f}-{100 * hi:.0f}%)"


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

    n_journals = A["article_id"].str.split("__").str[0].nunique()
    pdf_status = A["article_id"].map(lambda i: metas.get(i, {}).get("status"))
    blocked = A.loc[pdf_status == "blocked_bot_protection", "article_id"].str.split("__").str[0].nunique()
    L = ["# Day 2: how many citations can be checked?", "",
         "The sampled articles were downloaded and turned into text with GROBID 0.9.1, and each in-text "
         "citation was linked to its reference. The cited works were looked up in Crossref and OpenAlex. "
         "Intervals resample whole articles.", "",
         "## Which articles could be used", "",
         "| Stage | English journals | Spanish journals | Total |", "|---|---|---|---|"]
    def row(label, mask):
        en = int((mask & (A["lang_stratum"] == "EN")).sum())
        es = int((mask & (A["lang_stratum"] == "ES")).sum())
        L.append(f"| {label} | {en} | {es} | {en + es} |")
    row("Sampled", A["article_id"].notna())
    row("PDF downloaded", A["pdf_ok"])
    row("Parsed into body text and a reference list", A["parsed"])
    row("At least half the citations linked to a reference", A["linked_ok"])
    row("Body text in the expected language", A["linked_ok"] & A["lang_ok"])
    lost_lang = A[A["linked_ok"] & ~A["lang_ok"]]
    L += ["", f"{blocked} of the {n_journals} journals put their PDFs behind bot protection, although their "
          "article lists were open. The script recorded this and did not get around it. Linking failed mostly "
          f"in articles with footnote citations, and {len(lost_lang)} articles were in a different language from "
          "the one their journals' records gave.", ""]

    L += ["## What happens to each citation", "",
          f"{len(U):,} in-text citations in the {U['article_id'].nunique()} usable articles:", "",
          "| Outcome | Citations | Share |", "|---|---|---|"]
    order = ["full_text_oa", "abstract_only", "metadata_only", "unresolved_book_or_report",
             "unresolved_web", "unresolved_other", "link_failed_check", "unlinked"]
    labels = {**TIER_LABEL, "link_failed_check": "Linked to the wrong or a junk entry",
              "unlinked": "Not linked to any reference"}
    for o in order:
        n = int((U["outcome"] == o).sum())
        L.append(f"| {labels[o]} | {n} | {100 * n / len(U):.0f}% |")
    L += ["",
          f"- Can be checked at all (open full text or an abstract): {fmt(boot(U, 'judgeable', 'one'))}.",
          f"- Can be checked against full text: {fmt(boot(U, 'full', 'one'))}.",
          f"- Abstract only: {fmt(boot(U, 'abstract', 'one'))}. An abstract can confirm support but can't "
          "show that it is missing.", ""]

    inputs = Path("data/day3/ojs_inputs.jsonl")
    if inputs.exists():  # added once Day-3 prep has tried to download the open copies
        items = [json.loads(l) for l in inputs.read_text(encoding="utf-8").splitlines() if l.strip()]
        works = list(json.loads(Path("data/day3/open_works.json").read_text()).values())
        st = pd.Series([m["status"] for m in works]).value_counts()
        ft = [i for i in items if i["day2_outcome"] == "full_text_oa"]
        got = sum(i["evidence"] == "full_text" for i in ft)
        share_ft = boot(U, "full", "one")[0]
        L += ["## Can the open copies actually be downloaded?", "",
              f"For {len(items)} sampled citations, a script tried to download each open copy the way any "
              "outside tool would: the PDF link OpenAlex gives, or else the one on the article's page.", "",
              f"- Of {len(works)} cited works listed as open access, {st.get('ok', 0)} were downloaded "
              f"({100 * st.get('ok', 0) / max(1, len(works)):.0f}%). {st.get('blocked_bot_protection', 0)} were "
              f"behind bot protection and {st.get('no_pdf', 0)} had no PDF to find.",
              f"- Full text was obtained for {got} of the {len(ft)} citations whose source is listed as open "
              f"({100 * got / max(1, len(ft)):.0f}%). The rest fall back to the abstract where there is one.",
              f"- So only about {100 * share_ft * got / max(1, len(ft)):.0f}% of all citations can be checked "
              f"against full text that a script can actually get, not {100 * share_ft:.0f}%.", ""]

    L += ["## Caveats", "",
          "- Crossref matches had to agree on title and year or author, so some findable works count as "
          "unresolved.",
          "- GROBID ran with its light models. Its larger deep-learning models link more citations.",
          f"- Small sample: {len(usable)} usable articles from "
          f"{A.loc[A['usable'], 'article_id'].str.split('__').str[0].nunique()} journals."]
    Path("results/day2_summary.md").write_text("\n".join(L) + "\n")
    U.to_csv("data/day2/contexts_usable.csv", index=False)
    print("\n".join(L))


if __name__ == "__main__":
    main()
