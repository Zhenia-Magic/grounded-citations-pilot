"""Print samples of link-check outcomes and per-article extraction stats (debugging aid)."""
import pandas as pd

C = pd.read_csv("data/day2/contexts.csv", dtype=str, keep_default_na=False)
R = pd.read_csv("data/day2/references.csv", dtype=str, keep_default_na=False)
A = pd.read_csv("data/day2/parsed_articles.csv", dtype=str, keep_default_na=False)
M = C.merge(R[["article_id", "bibl_id", "first_author", "year", "position", "title", "raw"]],
            on=["article_id", "bibl_id"], how="left")

print("== per-article: refs, callouts, linked share, inconsistent share")
g = C.groupby("article_id")["link_check"].value_counts().unstack(fill_value=0)
g = g.join(A.set_index("article_id")[["n_refs", "lang_stratum", "body_lang_detected", "n_body_sentences"]])
g["linked"] = (g.get("consistent", 0) + g.get("inconsistent", 0)) / g.sum(axis=1, numeric_only=True)
print(g.sort_values("inconsistent", ascending=False).head(14).to_string())

print("\n== articles with few body sentences")
print(A[pd.to_numeric(A["n_body_sentences"], errors="coerce").fillna(0) < 30][
    ["article_id", "tei", "n_body_sentences", "n_refs", "n_callouts"]].to_string())

print("\n== inconsistent samples")
for r in M[M["link_check"] == "inconsistent"].sample(12, random_state=3).itertuples():
    print(f"- callout={r.callout!r} -> pos={r.position} author={r.first_author!r} year={r.year!r} "
          f"| raw={r.raw[:110]!r}")

print("\n== unlinked samples")
for r in M[M["link_check"] == "unlinked"].sample(8, random_state=3).itertuples():
    print(f"- callout={r.callout!r} | {r.sentence[:160]!r}")

print("\n== consistent samples")
for r in M[M["link_check"] == "consistent"].sample(3, random_state=5).itertuples():
    print(f"- {r.sentence[:300]!r}\n    -> {r.first_author} {r.year}: {r.title[:100]}")
