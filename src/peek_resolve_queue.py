"""How many Crossref searches does the headline number actually need? (debugging aid)"""
import hashlib
from pathlib import Path

import pandas as pd

A = pd.read_csv("data/day2/parsed_articles.csv", dtype=str, keep_default_na=False)
R = pd.read_csv("data/day2/references.csv", dtype=str, keep_default_na=False)
lang = {"EN": "en", "ES": "es"}
usable = set(A[(A["tei"] == "ok") & (A["parse_failed"] == "False") & (A["linking_failed"] == "False")
               & (A["body_lang_detected"] == A["lang_stratum"].map(lang))]["article_id"])
R = R[R["ref_like"] == "True"]
no_doi = R[R["doi"] == ""]


def done(ref):
    q = ref["raw"][:300] if len(ref["raw"]) >= 40 else " ".join(
        x for x in (ref["title"], ref["first_author"], ref["year"], ref["container"]) if x)
    return (Path("data/raw/resolve/crossref") / f"{hashlib.sha1(q.encode()).hexdigest()[:16]}.json").exists()


no_doi = no_doi.assign(done=no_doi.apply(done, axis=1),
                       needed=no_doi["article_id"].isin(usable) & (pd.to_numeric(no_doi["n_usable_contexts"]) > 0))
print(f"usable articles: {len(usable)}; refs without DOI: {len(no_doi)}; done: {int(no_doi['done'].sum())}")
print(f"needed for the headline: {int(no_doi['needed'].sum())}; needed and not done: "
      f"{int((no_doi['needed'] & ~no_doi['done']).sum())}")
