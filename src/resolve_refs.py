"""Day 2, step 4: resolve cited works to DOIs and find what evidence exists for each.

1. DOIs that GROBID found in the reference string are used as they are.
2. Other references go to Crossref's bibliographic search. A hit is accepted only if
   its title matches the parsed title (or appears in the raw string) and the year or
   first author agrees: a wrong match becomes a false flag, so precision beats recall.
3. All DOIs are looked up in OpenAlex in batches of 50 for open-access status, an
   abstract, the work type and retraction status.

Crossref is used through its public pool without a contact e-mail (no personal data
leaves the machine), sequentially and with a pause between requests. Responses are
cached under data/raw/resolve/, so re-runs are free.

Output: data/day2/references_resolved.csv
"""
import difflib
import hashlib
import json
import os
import re
import time
from pathlib import Path

import pandas as pd
import requests

from extract_contexts import YEAR, norm
from harvest_oai import UA

CACHE = Path("data/raw/resolve")
CR_PAUSE, OA_PAUSE = 0.4, 0.2
S = requests.Session()
S.headers["User-Agent"] = UA
DOI_CLEAN = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.I)


def clean_doi(d):
    d = DOI_CLEAN.sub("", (d or "").strip()).rstrip(".,;)]").lower()
    return d if re.match(r"^10\.\d{4,9}/\S+$", d) else ""


def get_json(url, params, cache_file, pause):
    if cache_file.exists():
        return json.loads(cache_file.read_text())
    for attempt in range(4):
        time.sleep(pause)
        try:
            r = S.get(url, params=params, timeout=60)
        except requests.RequestException:
            time.sleep(5 * (attempt + 1))
            continue
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(float(r.headers.get("Retry-After", 5 * (attempt + 1))))
            continue
        data = r.json() if r.status_code == 200 else {"_status": r.status_code}
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(data))
        return data
    return {"_status": "failed"}


def title_sim(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    # Containment counts only between titles of similar length: "X" inside "X: ... in Russian"
    # is a different edition or a longer work, not the same one.
    if min(len(a), len(b)) >= 25 and min(len(a), len(b)) / max(len(a), len(b)) >= 0.8 and (a in b or b in a):
        return 0.95
    return difflib.SequenceMatcher(None, a, b).ratio()


def crossref_match(ref):
    query = ref["raw"][:300] if len(ref["raw"]) >= 40 else " ".join(
        x for x in (ref["title"], ref["first_author"], ref["year"], ref["container"]) if x)
    key = hashlib.sha1(query.encode()).hexdigest()[:16]
    data = get_json("https://api.crossref.org/works",
                    {"query.bibliographic": query, "rows": 3,
                     "select": "DOI,title,author,issued,type,container-title,score"},
                    CACHE / "crossref" / f"{key}.json", CR_PAUSE)
    items = (data.get("message") or {}).get("items") or []
    raw_n = norm(ref["raw"])
    raw_years = {int(y[:4]) for y in YEAR.findall(ref["raw"])}
    want_years = {int(ref["year"])} if ref["year"] else raw_years
    for it in items:
        cand_title = (it.get("title") or [""])[0]
        parts = ((it.get("issued") or {}).get("date-parts") or [[None]])[0]
        cand_year = parts[0] if parts else None
        fam = norm(((it.get("author") or [{}])[0]).get("family", ""))
        year_ok = cand_year is not None and any(abs(cand_year - y) <= 1 for y in want_years)
        author_ok = bool(fam) and fam in raw_n[:80]
        if ref["title"] and len(ref["title"]) >= 15:
            sim = title_sim(ref["title"], cand_title)
            ok = sim >= 0.9 and (year_ok or author_ok or not want_years) or sim >= 0.75 and year_ok and author_ok
        else:
            ct = norm(cand_title)
            sim = 0.95 if len(ct) >= 25 and ct in raw_n else 0.0
            ok = sim > 0 and (year_ok or author_ok)
        if ok:
            return clean_doi(it.get("DOI")), round(sim, 3), it.get("type", "")
    return "", 0.0, ""


def openalex_lookup(dois):
    found, todo = {}, sorted(set(d for d in dois if d and "," not in d and "|" not in d))
    fields = "id,doi,display_name,type,publication_year,open_access,best_oa_location,abstract_inverted_index,is_retracted,language"
    for i in range(0, len(todo), 50):
        chunk = todo[i:i + 50]
        key = hashlib.sha1("|".join(chunk).encode()).hexdigest()[:16]
        data = get_json("https://api.openalex.org/works",
                        {"filter": "doi:" + "|".join(chunk), "per-page": 50, "select": fields},
                        CACHE / "openalex" / f"{key}.json", OA_PAUSE)
        if "_status" in data:  # a malformed DOI can sink the whole batch: look them up one by one
            for d in chunk:
                k1 = hashlib.sha1(d.encode()).hexdigest()[:16]
                w = get_json(f"https://api.openalex.org/works/doi:{d}", {"select": fields},
                             CACHE / "openalex_single" / f"{k1}.json", OA_PAUSE)
                if w.get("id"):
                    found[d] = w
            continue
        for w in data.get("results", []):
            d = clean_doi(w.get("doi"))
            if d:
                found[d] = w
    return found


def tier(row):
    if row["oa_found"]:
        if row["is_oa"]:
            return "full_text_oa"
        return "abstract_only" if row["has_abstract"] else "metadata_only"
    if row["kind"] in ("book_or_report", "chapter"):
        return "unresolved_book_or_report"
    if row["kind"] == "web" or row["url"]:
        return "unresolved_web"
    return "unresolved_other"


def main():
    R = pd.read_csv("data/day2/references.csv", dtype=str, keep_default_na=False)
    R = R[R["ref_like"] == "True"].copy()
    if os.environ.get("LIMIT"):  # smoke test on the first N entries
        R = R.head(int(os.environ["LIMIT"]))
    R["doi_source"], R["crossref_sim"], R["crossref_type"] = "", None, ""
    R["doi_clean"] = R["doi"].map(clean_doi)
    R.loc[R["doi_clean"] != "", "doi_source"] = "in_reference"
    # References cited by a usable citation context are the population the Day-2 numbers use.
    A = pd.read_csv("data/day2/parsed_articles.csv", dtype=str, keep_default_na=False)
    lang = {"EN": "en", "ES": "es"}
    usable = set(A[(A["tei"] == "ok") & (A["parse_failed"] == "False") & (A["linking_failed"] == "False")
                   & (A["body_lang_detected"] == A["lang_stratum"].map(lang))]["article_id"])
    R["needed"] = R["article_id"].isin(usable) & (pd.to_numeric(R["n_usable_contexts"]) > 0)
    todo = R[R["doi_clean"] == ""]
    if os.environ.get("ONLY_NEEDED"):
        R.loc[(R["doi_clean"] == "") & ~R["needed"], "doi_source"] = "not_queried"
        todo = todo[todo["needed"]]
    print(f"{len(R)} reference-like entries; {int((R['doi_clean'] != '').sum())} carry a DOI; "
          f"querying Crossref for {len(todo)}", flush=True)
    t0 = time.time()
    for n, (i, ref) in enumerate(todo.iterrows(), start=1):
        doi, sim, ctype = crossref_match(ref)
        if doi:
            R.at[i, "doi_clean"], R.at[i, "doi_source"] = doi, "crossref_match"
        R.at[i, "crossref_sim"], R.at[i, "crossref_type"] = sim, ctype
        if n % 50 == 0:
            print(f"  crossref {n}/{len(todo)} ({time.time() - t0:.0f}s)", flush=True)

    works = openalex_lookup(R["doi_clean"].tolist())
    print(f"OpenAlex found {len(works)} of {R['doi_clean'].ne('').sum()} DOIs", flush=True)
    rows = []
    for _, ref in R.iterrows():
        w = works.get(ref["doi_clean"]) if ref["doi_clean"] else None
        oa = (w or {}).get("open_access") or {}
        best = (w or {}).get("best_oa_location") or {}
        rows.append({
            "oa_found": w is not None, "oa_type": (w or {}).get("type", ""),
            "oa_title": ((w or {}).get("display_name") or "")[:300],
            "is_oa": bool(oa.get("is_oa")), "oa_status": oa.get("oa_status", ""),
            "oa_url": oa.get("oa_url") or "", "pdf_url": best.get("pdf_url") or "",
            "has_abstract": bool((w or {}).get("abstract_inverted_index")),
            "is_retracted": bool((w or {}).get("is_retracted")),
            "work_language": (w or {}).get("language") or "",
            "doi_title_sim": title_sim(ref["title"], (w or {}).get("display_name") or "") if w and ref["title"] else None,
        })
    R = pd.concat([R.reset_index(drop=True), pd.DataFrame(rows)], axis=1)
    R["tier"] = R.apply(tier, axis=1)
    R.to_csv("data/day2/references_resolved.csv", index=False)
    print(R["doi_source"].replace("", "none").value_counts().to_string())
    print(R["tier"].value_counts().to_string())
    print("retracted works cited:", int(R["is_retracted"].sum()))


if __name__ == "__main__":
    main()
