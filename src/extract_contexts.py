"""Day 2, step 3: turn GROBID TEI into references and citation contexts.

A citation context is one in-text callout inside a body sentence, linked to one
reference-list entry. Every link is checked, because a wrong link later becomes a
false "unsupported" flag:

- Numeric callouts. GROBID links by the printed label, which its TEI omits, and its
  reference list can contain junk entries (a numbered checklist read as references)
  or split entries, which shift positions forward. A link is consistent when the
  shift is forward and no larger than the number of surplus entries, and the
  linked entry looks like a real reference.
- Author-year callouts must share a year and a name token with the entry, checked
  against both GROBID's parsed fields and the raw reference string (parsed years
  are sometimes wrong).
- Unlinked author-year callouts are re-linked when exactly one entry matches
  ("rescued"). Unlinked numeric callouts are left alone: in footnote styles they
  are note markers, not references.

Outputs (data/day2/): parsed_articles.csv, references.csv, contexts.csv
"""
import re
import unicodedata
from pathlib import Path

import pandas as pd
import py3langid as langid
from defusedxml import ElementTree as ET

T = "{http://www.tei-c.org/ns/1.0}"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
TEI_DIR, OUT = Path("data/tei"), Path("data/day2")
METHODS_HEAD = re.compile(r"method|material|metodolog|procedim|data collection|participants|"
                          r"muestra|instrument", re.I)
YEAR = re.compile(r"(?<!\d)(1[6-9]\d\d|20[0-3]\d)[a-z]?(?!\d)")
NAME_STOP = {"et", "al", "and", "y", "e", "dan", "p", "pp", "cf", "see", "also", "in", "eds", "ed",
             "op", "cit", "ibid", "por", "ejemplo", "the", "de", "del", "la", "van", "von", "der"}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", s)).strip()


def text_of(el) -> str:
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip() if el is not None else ""


def marked(s_el, target) -> str:
    """Sentence text with the callout being judged wrapped in [[ ]]."""
    parts = [s_el.text or ""]
    for child in s_el:
        inner = text_of(child)
        parts.append(f"[[{inner}]]" if child is target else inner)
        parts.append(child.tail or "")
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def expand_numbers(callout: str):
    """'[3, 5-7]' -> {3, 5, 6, 7}; None when the callout is not purely numeric."""
    body = re.sub(r"[\[\]\(\)\s]", "", callout)
    if not body or not re.fullmatch(r"[\d,;\-–—]+", body):
        return None
    nums = set()
    for part in re.split(r"[,;]", body):
        if re.fullmatch(r"\d+[\-–—]\d+", part):
            a, b = map(int, re.split(r"[\-–—]", part))
            if 0 < b - a < 50:
                nums.update(range(a, b + 1))
        elif part.isdigit():
            nums.add(int(part))
    return nums or None


def name_tokens(callout: str):
    return [t for t in norm(YEAR.sub(" ", callout)).split() if len(t) >= 3 and t not in NAME_STOP
            and not t.isdigit()]


def parse_bibl(b, idx):
    analytic, monogr = b.find(f"{T}analytic"), b.find(f"{T}monogr")
    title = text_of(analytic.find(f"{T}title")) if analytic is not None else ""
    mtitle_el = monogr.find(f"{T}title") if monogr is not None else None
    mono_title, level = text_of(mtitle_el), (mtitle_el.get("level") if mtitle_el is not None else "")
    surnames = [text_of(s) for s in b.iter(f"{T}surname")]
    date = b.find(f".//{T}imprint/{T}date")
    when = (date.get("when") or text_of(date)) if date is not None else ""
    m = YEAR.search(when or "")
    idnos = {(i.get("type") or "").upper(): text_of(i) for i in b.iter(f"{T}idno")}
    ptr = b.find(f".//{T}ptr")
    if title and level == "j":
        kind = "article"
    elif title and level == "m":
        kind = "chapter"
    elif not title and level == "m":
        kind = "book_or_report"
    elif ptr is not None:
        kind = "web"
    else:
        kind = "other"
    raw = text_of(b.find(f"{T}note[@type='raw_reference']"))
    ref = {
        "bibl_id": b.get(XML_ID, f"b{idx}"), "position": idx + 1, "kind": kind,
        "title": title or mono_title, "container": mono_title if title else "",
        "first_author": surnames[0] if surnames else "", "year": m.group(1) if m else "",
        "doi": idnos.get("DOI", "").lower().removeprefix("https://doi.org/"),
        "url": ptr.get("target", "") if ptr is not None else "", "raw": raw[:800],
    }
    has_year = bool(ref["year"] or YEAR.search(raw))
    ref["ref_like"] = bool((has_year or ref["doi"]) and (ref["first_author"] or ref["title"])
                           and len(raw) >= 30)
    return ref


def check_link(callout, ref, slack):
    if not ref["ref_like"]:
        return "inconsistent"
    nums = expand_numbers(callout)
    if nums is not None:
        return "consistent" if any(0 <= ref["position"] - n <= slack for n in nums) else "inconsistent"
    years = {y[:4] for y in YEAR.findall(callout)}
    toks = name_tokens(callout)
    if not years and not toks:
        return "unverifiable"
    head = norm(ref["raw"])[:60] + " " + norm(ref["first_author"])
    year_ok = (not years) or ref["year"] in years or any(y in ref["raw"] for y in years)
    name_ok = (not toks) or any(t in head for t in toks)
    if years and toks:
        return "consistent" if (year_ok and name_ok) else "inconsistent"
    return "consistent" if (year_ok and name_ok) else "unverifiable"


def rescue(callout, refs):
    years = {y[:4] for y in YEAR.findall(callout)}
    toks = name_tokens(callout)
    if not years or not toks:
        return None
    cands = [r for r in refs if r["ref_like"]
             and (r["year"] in years or any(y in r["raw"][:250] for y in years))
             and any(t in norm(r["raw"])[:60] + " " + norm(r["first_author"]) for t in toks)]
    return cands[0] if len(cands) == 1 else None


def parse_article(tei_path, meta):
    root = ET.parse(tei_path).getroot()
    art = {"article_id": meta["article_id"], "lang_stratum": meta["lang_stratum"], "field": meta["field"]}
    text_el = root.find(f"{T}text")
    body = text_el.find(f"{T}body") if text_el is not None else None
    art["grobid_lang"] = text_el.get(XML_LANG, "") if text_el is not None else ""
    refs = [parse_bibl(b, i) for i, b in enumerate(root.findall(f".//{T}back//{T}listBibl/{T}biblStruct"))]
    by_id = {r["bibl_id"]: r for r in refs}

    raw_ctx, body_text = [], []
    for div in (body.findall(f"{T}div") if body is not None else []):
        head = text_of(div.find(f"{T}head"))
        sents = list(div.iter(f"{T}s"))
        for k, s in enumerate(sents):
            body_text.append(text_of(s))
            for ref_el in s.findall(f"{T}ref[@type='bibr']"):
                callout = text_of(ref_el)
                targets = [t.lstrip("#") for t in (ref_el.get("target") or "").split() if t.startswith("#")]
                for tgt in targets or [""]:
                    raw_ctx.append((head, sents, k, s, ref_el, callout, by_id.get(tgt)))

    # Surplus entries that can shift numeric positions: entries beyond the highest label cited.
    cited = [n for (_, _, _, _, _, c, _) in raw_ctx for n in (expand_numbers(c) or []) if n <= len(refs) + 10]
    slack = max(0, len(refs) - max(cited)) if cited else 0

    contexts = []
    for head, sents, k, s, ref_el, callout, ref in raw_ctx:
        if ref is not None:
            check = check_link(callout, ref, slack)
        else:
            ref = rescue(callout, refs)
            check = "rescued" if ref is not None else "unlinked"
        contexts.append({
            "article_id": meta["article_id"], "bibl_id": ref["bibl_id"] if ref else "",
            "callout": callout[:120], "section": head[:120], "methods_section": bool(METHODS_HEAD.search(head)),
            "sentence": marked(s, ref_el)[:1500],
            "prev_sentence": text_of(sents[k - 1])[:800] if k > 0 else "",
            "next_sentence": text_of(sents[k + 1])[:800] if k + 1 < len(sents) else "",
            "link_check": check,
        })
    for i, c in enumerate(contexts):
        c["context_id"] = f"{meta['article_id']}__c{i:03d}"

    sample = " ".join(body_text)[:6000]
    usable = sum(c["link_check"] in ("consistent", "rescued") for c in contexts)
    art.update({
        "n_body_sentences": len(body_text), "n_refs": len(refs),
        "n_refs_ref_like": sum(r["ref_like"] for r in refs), "slack": slack,
        "n_callouts": len(contexts), "n_usable_links": usable,
        "body_lang_detected": langid.classify(sample)[0] if len(sample) > 200 else "",
    })
    art["parse_failed"] = len(body_text) < 20 or art["n_refs_ref_like"] == 0
    art["linking_failed"] = (not art["parse_failed"]) and (len(contexts) == 0 or usable / len(contexts) < 0.5)
    counts = pd.Series([c["bibl_id"] for c in contexts if c["link_check"] in ("consistent", "rescued")],
                       dtype=str).value_counts()
    for r in refs:
        r["article_id"] = meta["article_id"]
        r["n_usable_contexts"] = int(counts.get(r["bibl_id"], 0))
    return art, refs, contexts


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    arts = pd.read_csv("data/sample/articles.csv", dtype=str, keep_default_na=False)
    A, R, C = [], [], []
    for meta in arts.to_dict("records"):
        base = {"article_id": meta["article_id"], "lang_stratum": meta["lang_stratum"], "field": meta["field"]}
        tei = TEI_DIR / f"{meta['article_id']}.tei.xml"
        if not tei.exists():
            A.append({**base, "tei": "missing"})
            continue
        try:
            art, refs, ctx = parse_article(tei, meta)
            art["tei"] = "ok"
        except Exception as e:
            art, refs, ctx = {**base, "tei": f"error_{type(e).__name__}"}, [], []
        A.append(art)
        R.extend(refs)
        C.extend(ctx)
    A, R, C = pd.DataFrame(A), pd.DataFrame(R), pd.DataFrame(C)
    A.to_csv(OUT / "parsed_articles.csv", index=False)
    R.to_csv(OUT / "references.csv", index=False)
    C.to_csv(OUT / "contexts.csv", index=False)

    ok = A[A["tei"] == "ok"]
    print(A["tei"].value_counts().to_string())
    print(f"parsed: {len(ok)}; parse failed: {int(ok['parse_failed'].sum())}; "
          f"linking failed: {int(ok['linking_failed'].sum())}")
    print(f"reference entries: {len(R)} (reference-like {int(R['ref_like'].sum())}); callouts: {len(C)}")
    print("body language vs stratum:\n", ok.groupby(["lang_stratum", "body_lang_detected"]).size().to_string())
    print("link check:\n", C["link_check"].value_counts().to_string())
    print("linking-failed articles:", ok[ok["linking_failed"]]["article_id"].tolist())


if __name__ == "__main__":
    main()
