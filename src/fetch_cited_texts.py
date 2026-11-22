"""Day 3 prep: sample the citations to judge and fetch the cited works' open texts (no model calls).

1. Sample SAMPLE_N judgeable citation contexts (full text or abstract per Day 2), mostly English
   because the hand-check is in English, at most PER_ARTICLE per citing article, seeded.
2. For cited works marked open access, fetch the open PDF: the OpenAlex PDF link, else the OA
   landing page's citation_pdf_url meta tag. robots.txt respected, 2 s between requests to a host,
   bot walls recorded and not bypassed. Each PDF is parsed with the local GROBID server.
3. Abstracts are rebuilt from the cached OpenAlex records.
4. Write data/day3/ojs_inputs.jsonl in the same item format as the benchmark.

Also measures something Day 2 could not: how often "open access per OpenAlex" means a copy that an
automated client can actually retrieve.
"""
import hashlib
import json
import random
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import pandas as pd
import requests
from defusedxml import ElementTree as ET

from extract_contexts import T, text_of
from fetch_pdfs import PAUSE, get_pdf, robots_for
from harvest_oai import UA
from judge_prompt import bm25_top
from resolve_refs import clean_doi

SEED, SAMPLE_N, PER_ARTICLE = 20261123, 200, 8
QUOTA = {"EN": 160, "ES": 40}
MAX_FULL_CHARS, MIN_FULL_CHARS = 120_000, 5_000
GROBID = "http://localhost:8070/api/processFulltextDocument"
PDF_DIR, TEI_DIR, OUT = Path("data/raw/cited_pdf"), Path("data/tei_cited"), Path("data/day3")
PDF_META = re.compile(r'<meta[^>]+name=["\']citation_pdf_url["\'][^>]+content=["\']([^"\']+)["\']', re.I)
PDF_META_REV = re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']citation_pdf_url["\']', re.I)


def key(doi):
    return hashlib.sha1(doi.encode()).hexdigest()[:16]


def abstracts_from_cache():
    out = {}
    for p in list(Path("data/raw/resolve/openalex").glob("*.json")) + list(Path("data/raw/resolve/openalex_single").glob("*.json")):
        data = json.loads(p.read_text())
        for w in data.get("results", [data] if data.get("id") else []):
            inv = w.get("abstract_inverted_index")
            d = clean_doi(w.get("doi"))
            if d and inv:
                pos = sorted((i, word) for word, idx in inv.items() for i in idx)
                out[d] = " ".join(word for _, word in pos)
    return out


def sample_contexts():
    U = pd.read_csv("data/day2/contexts_usable.csv", dtype=str, keep_default_na=False)
    U = U[U["outcome"].isin(["full_text_oa", "abstract_only"])]
    rng = random.Random(SEED)
    picked = []
    for lang, quota in QUOTA.items():
        pool = U[U["lang_stratum"] == lang].to_dict("records")
        rng.shuffle(pool)
        per = defaultdict(int)
        for c in pool:
            if len([p for p in picked if p["lang_stratum"] == lang]) >= quota:
                break
            if per[c["article_id"]] < PER_ARTICLE:
                per[c["article_id"]] += 1
                picked.append(c)
    return picked


def fetch_one(session, doi, urls, cache):
    meta_p = PDF_DIR / f"{key(doi)}.json"
    if meta_p.exists():
        return json.loads(meta_p.read_text())
    meta = {"doi": doi, "status": "no_pdf", "tried": []}
    for url in urls:
        if not robots_for(session, url, cache):
            meta["tried"].append([url, "robots_disallow"])
            continue
        time.sleep(PAUSE)
        data, note = get_pdf(session, url)
        if data:
            (PDF_DIR / f"{key(doi)}.pdf").write_bytes(data)
            meta.update(status="ok", pdf_url=url)
            break
        if isinstance(note, tuple):  # landing page: follow its citation_pdf_url tag
            m = PDF_META.search(note[1]) or PDF_META_REV.search(note[1])
            meta["tried"].append([url, "html"])
            if m:
                link = urljoin(url, m.group(1).replace("&amp;", "&"))
                if robots_for(session, link, cache):
                    time.sleep(PAUSE)
                    data, note2 = get_pdf(session, link)
                    if data:
                        (PDF_DIR / f"{key(doi)}.pdf").write_bytes(data)
                        meta.update(status="ok", pdf_url=link)
                        break
                    meta["tried"].append([link, note2 if isinstance(note2, str) else "html"])
        else:
            meta["tried"].append([url, note])
            if note == "blocked_bot_protection":
                meta["status"] = "blocked_bot_protection"
    meta_p.write_text(json.dumps(meta, indent=1))
    return meta


def grobid_paragraphs(doi):
    tei = TEI_DIR / f"{key(doi)}.tei.xml"
    pdf = PDF_DIR / f"{key(doi)}.pdf"
    if not tei.exists():
        with pdf.open("rb") as fh:
            r = requests.post(GROBID, files={"input": fh}, data={"consolidateHeader": "0",
                              "consolidateCitations": "0"}, timeout=300)
        if r.status_code != 200:
            return None
        tei.write_bytes(r.content)
    root = ET.parse(tei).getroot()
    abstract = text_of(root.find(f".//{T}profileDesc/{T}abstract"))
    body = root.find(f".//{T}text/{T}body")
    paras = [text_of(p) for p in (body.iter(f"{T}p") if body is not None else [])]
    paras = [p for p in paras if len(p) > 40]
    return ([abstract] if len(abstract) > 40 else []) + paras


def main():
    for d in (PDF_DIR, TEI_DIR, OUT):
        d.mkdir(parents=True, exist_ok=True)
    picked = sample_contexts()
    R = pd.read_csv("data/day2/references_resolved.csv", dtype=str, keep_default_na=False)
    refs = {(r["article_id"], r["bibl_id"]): r for r in R.to_dict("records")}
    abstracts = abstracts_from_cache()

    want = {}
    for c in picked:
        r = refs[(c["article_id"], c["bibl_id"])]
        if c["outcome"] == "full_text_oa" and r["doi_clean"]:
            want[r["doi_clean"]] = [u for u in dict.fromkeys([r["pdf_url"], r["oa_url"]]) if u]
    by_host = defaultdict(list)
    for doi, urls in want.items():
        by_host[(urlsplit(urls[0]).hostname or "") if urls else ""].append((doi, urls))
    print(f"{len(picked)} contexts sampled; {len(want)} open cited works to fetch on {len(by_host)} hosts", flush=True)

    def run_host(items):
        s = requests.Session()
        s.headers["User-Agent"] = UA
        cache = {}
        return [fetch_one(s, doi, urls, cache) if urls else {"doi": doi, "status": "no_url"} for doi, urls in items]

    with ThreadPoolExecutor(max_workers=8) as ex:
        fetched = {m["doi"]: m for group in ex.map(run_host, by_host.values()) for m in group}

    texts, too_short = {}, 0
    for doi, m in fetched.items():
        if m["status"] == "ok":
            paras = grobid_paragraphs(doi)
            # A fragment is not full text: judged against it, a sound citation looks unsupported.
            if paras and sum(map(len, paras)) >= MIN_FULL_CHARS:
                texts[doi] = paras
            else:
                too_short += 1

    (OUT / "open_works.json").write_text(json.dumps(  # exactly the works behind this sample
        {doi: {"status": fetched.get(doi, {}).get("status", "no_url"), "usable_text": doi in texts} for doi in want},
        indent=1))
    items, outcome = [], defaultdict(int)
    for c in picked:
        r = refs[(c["article_id"], c["bibl_id"])]
        doi = r["doi_clean"]
        meta = f"{r['oa_title'] or r['title']} ({r['year'] or '?'}), {r['first_author'] or 'unknown author'}" \
               + (f" et al., {r['container']}" if r["container"] else "")
        if doi in texts:
            paras, evidence = texts[doi], "full_text"
            if sum(map(len, paras)) > MAX_FULL_CHARS:
                paras = [paras[0]] + [paras[1:][i] for i in bm25_top(c["sentence"], paras[1:], k=15)]
            outcome["full_text"] += 1
        elif doi in abstracts:
            paras, evidence = [abstracts[doi]], "abstract"
            outcome["abstract (fetch failed)" if c["outcome"] == "full_text_oa" else "abstract"] += 1
        else:
            outcome["no evidence after fetch"] += 1
            continue
        items.append({"item_id": c["context_id"], "lang_stratum": c["lang_stratum"], "field": c["field"],
                      "day2_outcome": c["outcome"], "doi": doi, "link_check": c["link_check"],
                      "methods_section": c["methods_section"],
                      "ctx": {k: c[k] for k in ("section", "prev_sentence", "sentence", "next_sentence")},
                      "source_meta": meta, "evidence": evidence, "passages": paras})
    with (OUT / "ojs_inputs.jsonl").open("w", encoding="utf-8") as fh:
        for it in items:
            fh.write(json.dumps(it, ensure_ascii=False) + "\n")
    status = pd.Series([m["status"] for m in fetched.values()]).value_counts()
    n_en = sum(i["lang_stratum"] == "EN" for i in items)
    lines = ["# Day 3 prep: retrieving the open copies", "",
             f"- Citations sampled for judging: {len(picked)} (seed {SEED}; at most {PER_ARTICLE} per citing article).",
             f"- Distinct cited works that OpenAlex lists as open access: {len(want)}.",
             f"- Open PDF retrieved and parsed into usable full text: {len(texts)} of {len(want)} "
             f"({100 * len(texts) / max(1, len(want)):.0f}%); retrieved but parsed into under "
             f"{MIN_FULL_CHARS:,} characters (treated as not retrieved): {too_short}.",
             "- Fetch outcomes: " + ", ".join(f"{k} {v}" for k, v in status.items()) + ".",
             "- Evidence available for the sampled citations: "
             + ", ".join(f"{k} {v}" for k, v in outcome.items()) + ".",
             f"- Judge inputs written: {len(items)} ({n_en} English, {len(items) - n_en} Spanish)."]
    Path("results/day3_prep.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
