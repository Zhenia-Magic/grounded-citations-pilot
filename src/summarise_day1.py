"""Turn the Day-1 harvest into numbers, pick the 30 pilot journals and the Day-2 article sample.

Outputs:
  data/sample/journals.csv    every candidate with derived fields; `selected` marks the 30
  data/sample/articles.csv    the Day-2 article sample (2 per EN journal, 1 per ES journal)
  data/records_recent.csv     one row per 2025-26 record from active OJS journals
  results/day1_summary.md     the write-up
"""
import json
import math
import random
import re
from pathlib import Path

import pandas as pd
import py3langid as langid

from harvest_oai import OUT, slug_for

SEED = 20261121
MIN_RECENT = 3
ARTICLES_PER_JOURNAL = {"EN": 2, "ES": 1}
STRATUM_LANG = {"EN": "en", "ES": "es"}
LANG_MAP = {"eng": "en", "spa": "es", "por": "pt", "ind": "id", "fre": "fr", "fra": "fr",
            "ger": "de", "deu": "de", "rus": "ru", "ukr": "uk", "tur": "tr", "ara": "ar",
            "ita": "it", "pol": "pl", "cze": "cs", "ces": "cs", "per": "fa", "fas": "fa",
            "cat": "ca", "hrv": "hr", "srp": "sr", "slo": "sk", "slk": "sk", "rum": "ro",
            "ron": "ro", "hun": "hu", "may": "ms", "msa": "ms", "vie": "vi", "tha": "th",
            "english": "en", "inglés": "en", "ingles": "en", "spanish": "es", "español": "es",
            "espanol": "es", "castellano": "es", "portuguese": "pt", "português": "pt",
            "indonesian": "id", "bahasa indonesia": "id", "indonesia": "id"}
DOI_RE = re.compile(r"(10\.\d{4,9}/[^\s\"<>]+)")
NOT_RESEARCH = re.compile(
    r"^\s*(editorial|editor.?s note|erratum|errata|corrigendum|correction|retraction|book review|"
    r"review of|rese[nñ]a|presentaci[oó]n|nota editorial|in memoriam|obituary|front matter|"
    r"back matter|table of contents|[ií]ndice|cover|preface|prefacio|foreword)\b", re.I)


def norm_lang(v):
    v = (v or "").strip().lower().replace("_", "-").split("-")[0]
    return LANG_MAP.get(v, v) or None


def norm_format(f):
    f = f.strip().lower()
    if "pdf" in f:
        return "pdf"
    if "html" in f:
        return "html"
    if "xml" in f:
        return "xml"
    if "epub" in f:
        return "epub"
    if "word" in f or "msword" in f or "officedocument" in f:
        return "word"
    if f.startswith(("audio/", "video/", "image/")):
        return "media"
    return "other"


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"),) * 3
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, max(0.0, c - h), min(1.0, c + h)


def pct(k, n):
    p, lo, hi = wilson(k, n)
    return "n/a" if n == 0 else f"{100 * p:.0f}% ({100 * lo:.0f}-{100 * hi:.0f}%)"


def record_row(rec, journal):
    dates = rec.get("date", [])
    year = int(dates[0][:4]) if dates and dates[0][:4].isdigit() else None
    lang = norm_lang((rec.get("language") or [None])[0]) or norm_lang(rec.get("title_lang"))
    fmts = sorted({norm_format(f) for f in rec.get("format", [])})
    idents = rec.get("identifier", [])
    doi = next((m.group(1).rstrip(".,;") for i in idents for m in [DOI_RE.search(i)] if m), "")
    landing = next((i for i in idents if i.startswith("http") and "/article/view/" in i), "")
    galleys = [r for r in rec.get("relation", []) if r.startswith("http") and "/article/view/" in r]
    title = (rec.get("title") or [""])[0]
    types = " | ".join(rec.get("type", []))
    # Journals' dc:language is often wrong (e.g. Indonesian articles tagged "en"), so detect the
    # language of the title and abstracts too. Day 2 re-checks the body text after parsing.
    texts = [title] + [d for d in rec.get("description", []) if len(d) > 40][:3]
    detected = {detect(t) for t in texts if len(t) > 15}
    return {
        "slug": journal["slug"], "lang_stratum": journal["lang"], "field": journal["field"],
        "oai_id": rec.get("oai_id", ""), "year": year, "date": dates[0] if dates else "",
        "language": lang, "title": title[:300], "types": types[:200], "formats": "|".join(fmts),
        "pdf_only": fmts == ["pdf"], "has_html": "html" in fmts, "has_xml": "xml" in fmts,
        "no_galley": not fmts, "doi": doi, "landing_url": landing, "galley_urls": "|".join(galleys),
        "research_like": not NOT_RESEARCH.search(title) and not re.search(r"editorial|book review", types, re.I),
        "text_langs": "|".join(sorted(detected)),
        "lang_clean": detected == {lang} if lang else False,
    }


langid.set_languages(["en", "es", "pt", "id", "ms", "fr", "de", "ru", "uk", "it", "hu", "tr", "pl",
                      "cs", "sk", "sl", "hr", "sr", "ro", "ca", "nl", "ar", "fa", "vi", "th"])


def detect(text):
    code = langid.classify(text)[0]
    return "id" if code == "ms" else code


def ojs_version_bucket(v):
    m = re.search(r"(\d+)\.(\d+)", v or "")
    if not m:
        return "unknown"
    major, minor = int(m.group(1)), int(m.group(2))
    if major >= 3 and minor >= 4:
        return "3.4–3.5"
    if major == 3 and minor == 3:
        return "3.3"
    if major == 3:
        return "3.0–3.2"
    return "2.x"


def outcome(status):
    if status == "ok":
        return "OAI works"
    if status == "records_failed":
        return "Identify works, record listing fails"
    if "bot_protection" in status:
        return "Blocked by bot protection"
    if "timeout" in status or "connection" in status or "ssl" in status:
        return "Unreachable (timeout, DNS, TLS)"
    if "http_" in status:
        return "HTTP error"
    return "Not an OAI response / other"


def main():
    frame = json.loads(Path("data/sample/frame_counts.json").read_text())
    cands = pd.read_csv("data/sample/candidates.csv", dtype=str, keep_default_na=False)
    cands["rank"] = cands["rank"].astype(int)
    cands["quota"] = cands["quota"].astype(int)
    jrows, rrows = [], []
    for c in cands.to_dict("records"):
        slug = slug_for(c["base_url"])
        res_p, rec_p = OUT / slug / "result.json", OUT / slug / "records.json"
        res = json.loads(res_p.read_text()) if res_p.exists() else {"status": "not_attempted"}
        recs = json.loads(rec_p.read_text()) if rec_p.exists() else []
        j = {**c, "slug": slug, **{k: res.get(k) for k in (
            "status", "tls_ok", "toolkit", "toolkit_version", "generator", "n_records", "capped",
            "records_error", "identify_final_url")}}
        version = res.get("toolkit_version") or re.sub(r"^\D*", "", res.get("generator") or "")
        j["ojs_confirmed"] = ("open journal systems" in (res.get("toolkit") or "").lower()
                              or (res.get("generator") or "").lower().startswith("open journal systems")
                              or any(r.get("oai_id", "").startswith("oai:ojs") for r in recs[:20]))
        j["ojs_version"] = version
        j["version_bucket"] = ojs_version_bucket(version) if j["ojs_confirmed"] else "not OJS"
        rows = [record_row(r, j) for r in recs]
        recent = [r for r in rows if r["year"] and r["year"] >= 2025]
        j["n_recent"] = len(recent)
        j["n_recent_lang"] = sum(r["language"] == STRATUM_LANG[c["lang"]] for r in recent)
        j["active"] = res.get("status") == "ok" and j["ojs_confirmed"] and j["n_recent"] >= MIN_RECENT
        j["eligible"] = j["active"] and j["n_recent_lang"] >= MIN_RECENT
        if j["active"]:
            rrows.extend(recent)
        jrows.append(j)
    J = pd.DataFrame(jrows)
    R = pd.DataFrame(rrows)

    # Pick the first eligible journals in rank order until each stratum's quota is met.
    J["selected"] = False
    for (lang, field), g in J.sort_values("rank").groupby(["lang", "field"]):
        quota = int(g["quota"].iloc[0])
        J.loc[g[g["eligible"]].index[:quota], "selected"] = True

    # Day-2 article sample: research-like, in the stratum language, with a PDF galley.
    rng = random.Random(SEED)
    picks = []
    for j in J[J["selected"]].sort_values(["lang", "field", "rank"]).to_dict("records"):
        pool = R[(R["slug"] == j["slug"]) & (R["language"] == STRATUM_LANG[j["lang"]])
                 & R["formats"].str.contains("pdf") & R["research_like"] & (R["galley_urls"] != "")]
        idx = list(pool.index)
        rng.shuffle(idx)
        idx.sort(key=lambda i: not pool.at[i, "lang_clean"])  # stable: clean-language records first
        picks.extend(idx[: ARTICLES_PER_JOURNAL[j["lang"]]])
    A = R.loc[picks].copy()
    A.insert(0, "article_id", [f"{s}__{o.rsplit('/', 1)[-1]}" for s, o in zip(A["slug"], A["oai_id"])])

    Path("results").mkdir(exist_ok=True)
    J.to_csv("data/sample/journals.csv", index=False)
    R.to_csv("data/records_recent.csv", index=False)
    A.to_csv("data/sample/articles.csv", index=False)
    Path("results/day1_summary.md").write_text(write_up(frame, J, R, A))
    print(Path("results/day1_summary.md").read_text())


def write_up(frame, J, R, A):
    n = len(J)
    ok = J[J["status"] == "ok"]
    L = ["# Day 1: can a program read OJS journals?", "",
         f"{frame['frame_en'] + frame['frame_es']:,} of the {frame['doaj_journals']:,} journals in DOAJ's list "
         f"(`{frame['doaj_csv']}`) have OJS-style homepages and accept articles in English or Spanish. "
         f"{n} of them were drawn at random, across 2 languages and 4 fields.", "",
         "## Can a program list their articles?", "",
         "OJS has a standard feed for this, OAI-PMH.", "",
         "| Outcome | Journals | Share (95% CI) |", "|---|---|---|"]
    oc = J["status"].fillna("not_attempted").map(outcome).value_counts()
    for k, v in oc.items():
        L.append(f"| {k} | {v} | {pct(v, n)} |")
    L += ["", f"{int(J['active'].sum())} of the {len(ok)} working journals published at least {MIN_RECENT} "
          "articles in 2025-26. The rest of this page covers those active journals.", ""]

    act = J[J["active"]]
    L += ["## How is the full text published?", "",
          f"{len(R):,} articles dated 2025-26 in the {len(act)} active journals:", "",
          "| Journals | Articles | PDF only | Any HTML | Any XML |", "|---|---|---|---|---|"]
    for label, sub in [("All", R), ("English-language", R[R["lang_stratum"] == "EN"]),
                       ("Spanish-language", R[R["lang_stratum"] == "ES"])]:
        m = len(sub)
        L.append(f"| {label} | {m:,} | {pct(int(sub['pdf_only'].sum()), m)} | "
                 f"{pct(int(sub['has_html'].sum()), m)} | {pct(int(sub['has_xml'].sum()), m)} |")
    jl = R.groupby("slug").agg(any_html=("has_html", "any"), any_xml=("has_xml", "any"))
    pdf_only_j = int((~(jl["any_html"] | jl["any_xml"])).sum())

    # Stratum-weighted journal-level estimate for the in-scope frame.
    strata = frame["strata"]
    tot = sum(strata.values())
    est, var = 0.0, 0.0
    jl = jl.join(J.set_index("slug")[["lang", "field"]])
    for key, N_h in strata.items():
        lang, field = key.split("/")
        g = jl[(jl["lang"] == lang) & (jl["field"] == field)]
        if len(g) == 0:
            continue
        p_h = float((~(g["any_html"] | g["any_xml"])).mean())
        W = N_h / tot
        est += W * p_h
        var += W * W * p_h * (1 - p_h) / max(len(g) - 1, 1)
    lo, hi = max(0, est - 1.96 * math.sqrt(var)), min(1, est + 1.96 * math.sqrt(var))
    L += ["", f"{pdf_only_j} of the {len(jl)} active journals ({100 * pdf_only_j / len(jl):.0f}%) published no "
          f"HTML or XML full text for any 2025-26 article. Weighted to the DOAJ list, that is about "
          f"{100 * est:.0f}% of journals (95% CI {100 * lo:.0f}-{100 * hi:.0f}%).", ""]

    sel = J[J["selected"]]
    L += [f"For Day 2, {len(sel)} of the active journals ({int((sel['lang'] == 'EN').sum())} English-language, "
          f"{int((sel['lang'] == 'ES').sum())} Spanish-language) and {len(A)} of their articles were sampled.", "",
          "## Caveats", "",
          "- DOAJ lists better-resourced journals than the long tail of OJS, so across all OJS journals the "
          "PDF-only share is probably higher.",
          "- File types come from the journals' own records, and an HTML version can still be a thin wrapper "
          "around a PDF."]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
