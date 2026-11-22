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
from collections import Counter
from datetime import date
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
    return "n/a" if n == 0 else f"{k}/{n} = {100 * p:.0f}% ({100 * lo:.0f}–{100 * hi:.0f}%)"


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
    L = [f"# Day 1: OJS journal sample and full-text formats",
         "",
         f"Run {date.today().isoformat()} on DOAJ's journal list `{frame['doaj_csv']}`.",
         "",
         "## Sampling frame",
         "",
         f"- DOAJ lists {frame['doaj_journals']:,} journals; {frame['frame_after_dedup']:,} have OJS-style "
         f"`/index.php/<journal>` homepages.",
         f"- In scope: {frame['frame_en']:,} that accept English but not Spanish (EN) and "
         f"{frame['frame_es']:,} that accept Spanish (ES).",
         f"- Seeded random draw (seed {frame['seed']}) within 8 strata (2 languages x 4 field groups): "
         f"{n} candidates, {frame['oversample']}x the quota of 30.",
         "",
         "## Can an outside tool harvest them? (all candidates)",
         "",
         "| Outcome | Journals | Share (95% CI) |", "|---|---|---|"]
    oc = J["status"].fillna("not_attempted").map(outcome).value_counts()
    for k, v in oc.items():
        L.append(f"| {k} | {v} | {pct(v, n)} |")
    ok = J[J["status"] == "ok"]
    L += ["",
          f"- Confirmed OJS among working endpoints: {pct(int(ok['ojs_confirmed'].sum()), len(ok))}.",
          f"- Working only after skipping certificate checks (broken TLS): "
          f"{pct(int((ok['tls_ok'] == False).sum()), len(ok))}.",
          f"- Active (at least {MIN_RECENT} articles dated 2025–26): {pct(int(J['active'].sum()), len(ok))} "
          f"of working endpoints.",
          f"- Journals whose record listing hit the 8-page cap: {int(J['capped'].fillna(False).astype(bool).sum())}.",
          "",
          "OJS versions among confirmed OJS journals with working endpoints:",
          ""]
    vc = ok[ok["ojs_confirmed"]]["version_bucket"].value_counts()
    L += [f"- {k}: {v}" for k, v in vc.items()]

    act = J[J["active"]]
    L += ["", "## How full text is published (active journals, articles dated 2025–26)", "",
          f"{len(act)} active journals, {len(R):,} articles.", "",
          "| Group | Articles | PDF only | Any HTML | Any XML | No file type listed |",
          "|---|---|---|---|---|---|"]
    for label, sub in [("All", R), ("EN journals", R[R["lang_stratum"] == "EN"]),
                       ("ES journals", R[R["lang_stratum"] == "ES"])]:
        m = len(sub)
        L.append(f"| {label} | {m:,} | {pct(int(sub['pdf_only'].sum()), m)} | {pct(int(sub['has_html'].sum()), m)} | "
                 f"{pct(int(sub['has_xml'].sum()), m)} | {pct(int(sub['no_galley'].sum()), m)} |")
    jl = R.groupby("slug").agg(any_html=("has_html", "any"), any_xml=("has_xml", "any"),
                               share_pdf_only=("pdf_only", "mean"), n=("pdf_only", "size"))
    pdf_only_j = int((~(jl["any_html"] | jl["any_xml"])).sum())
    top5 = jl["n"].nlargest(5).sum() / jl["n"].sum()
    L += ["", f"Journal level: {pct(pdf_only_j, len(jl))} of active journals published no HTML or XML "
          "full text for any 2025–26 article.",
          f"The median journal's share of PDF-only articles is {100 * jl['share_pdf_only'].median():.0f}%. "
          f"Journals published a median of {jl['n'].median():.0f} articles in 2025–26 (range "
          f"{jl['n'].min()}–{jl['n'].max()}); the five largest supply {100 * top5:.0f}% of the pooled articles, "
          "so read the article-level rows as descriptive.", ""]
    jl = jl[["any_html", "any_xml"]]

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
    L += [f"Weighted to the in-scope DOAJ frame: about {100 * est:.0f}% of journals are PDF-only "
          f"(approximate 95% CI {100 * max(0, est - 1.96 * math.sqrt(var)):.0f}–"
          f"{100 * min(1, est + 1.96 * math.sqrt(var)):.0f}%).", ""]

    has_doi = int((R["doi"] != "").sum())
    langs = Counter(R[R["lang_stratum"] == "EN"]["language"].fillna("unknown"))
    tagged_en = R[(R["lang_stratum"] == "EN") & (R["language"] == "en")]
    mixed_en = tagged_en[~tagged_en["lang_clean"]]
    other = Counter(l for s in mixed_en["text_langs"] for l in s.split("|") if l and l != "en")
    L += ["## DOIs and article languages", "",
          f"- Articles with a DOI in their OAI record: {pct(has_doi, len(R))}.",
          "- Languages of 2025–26 articles in EN-stratum journals, as the journals tag them: "
          + ", ".join(f"{k} {v}" for k, v in langs.most_common(6)) + ".",
          f"- Records tagged English whose title or abstract is detected as another language too: "
          f"{pct(len(mixed_en), len(tagged_en))}; most often "
          + ", ".join(f"{k} ({v})" for k, v in other.most_common(4))
          + ". Many are bilingual records (an English abstract beside the original), so the tag alone "
          "can't tell you the body's language. Day 2 checks each parsed body before the English hand-check.",
          f"- Day-2 articles whose title and abstracts are all detected as the stratum language: "
          f"{int(A['lang_clean'].sum())} of {len(A)}.", ""]

    sel = J[J["selected"]]
    L += ["## Day-2 sample", "",
          "| Stratum | Journals needed | Selected | Eligible found |", "|---|---|---|---|"]
    for (lang, field), g in J.groupby(["lang", "field"]):
        L.append(f"| {lang}/{field} | {int(g['quota'].iloc[0])} | {int(g['selected'].sum())} | "
                 f"{int(g['eligible'].sum())} |")
    L += ["", f"{len(sel)} journals selected; {len(A)} articles sampled "
          f"({int((A['lang_stratum'] == 'EN').sum())} English, {int((A['lang_stratum'] == 'ES').sum())} Spanish). "
          "Eligible means working OAI, confirmed OJS and at least "
          f"{MIN_RECENT} 2025–26 articles in the stratum's language.", ""]
    metas = {p.stem: json.loads(p.read_text()) for p in Path("data/raw/pdf").glob("*.json")}
    if metas:
        st = A["article_id"].map(lambda i: metas.get(i, {}).get("status", "not tried"))
        ok = st == "ok"
        L += ["## PDF downloads (Day 2, step 1)", "",
              f"- PDFs fetched: {int(ok.sum())} of {len(A)} "
              f"({int((ok & (A['lang_stratum'] == 'EN')).sum())} English, "
              f"{int((ok & (A['lang_stratum'] == 'ES')).sum())} Spanish).",
              f"- Journals whose PDF downloads sit behind bot protection, although their OAI endpoint "
              f"works: {A[st == 'blocked_bot_protection']['slug'].nunique()} of {A['slug'].nunique()}. "
              "Recorded, not bypassed.",
              f"- Journals where no PDF could be reached from the galley links: "
              f"{A[st == 'no_pdf']['slug'].nunique()}.",
              "- Downloads respected robots.txt and paused 2 s between requests to the same host.", ""]
    L += ["## Caveats", "",
          "- DOAJ-listed journals are better resourced than OJS's long tail, so the PDF-only share across all "
          "OJS journals is probably higher than this.",
          "- File types come from the journals' own OAI records (`dc:format`); an HTML galley can still be "
          "a thin wrapper around a PDF.",
          "- Article dates come from `dc:date`; records were requested from datestamp 2025-01-01, which "
          "catches every article published since then.",
          "- Bot-protected endpoints were recorded, not bypassed."]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
