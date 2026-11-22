"""Harvest OAI-PMH Identify and recent Dublin Core records for the candidate journals.

Polite by design: one worker per host, a pause between requests to the same
host, a descriptive User-Agent with no personal details, a page cap per
journal, and no attempt to get past bot protection (those responses are
recorded as blocked). Results are cached per journal, so re-running resumes.

Usage: python src/harvest_oai.py            (reads data/sample/candidates.csv)
"""
import json
import os
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlsplit

import pandas as pd
import requests
import urllib3
from defusedxml import ElementTree as ET

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

UA = "ojs-citation-pilot/0.1 (academic research pilot; polite OAI-PMH harvester)"
FROM = "2025-01-01"   # datestamps are last-modified, so this is a superset of 2025+ articles
MAX_PAGES = 8         # OJS pages hold ~100 records; cap protects servers that re-stamped everything
PAUSE = 1.0           # seconds between requests to the same host
TIMEOUT = (15, 60)    # connect, read
WORKERS = 12
OUT = Path("data/raw/oai")

NS = {
    "oai": "http://www.openarchives.org/OAI/2.0/",
    "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
    "tk": "http://oai.dlib.vt.edu/OAI/metadata/toolkit",
    "oid": "http://www.openarchives.org/OAI/2.0/oai-identifier",
}
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
BAD_XML_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
GENERATOR = re.compile(r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']([^"\']{0,80})', re.I)


def slug_for(url: str) -> str:
    p = urlsplit(url)
    return re.sub(r"[^A-Za-z0-9]+", "_", f"{p.hostname}{p.path}").strip("_")[:120]


def fetch(session, url, params, state):
    """GET with one retry. Falls back to unverified TLS only on certificate errors
    (public metadata, nothing sent), and records that it did."""
    for attempt in range(2):
        try:
            r = session.get(url, params=params, timeout=TIMEOUT, verify=state["verify"])
            if r.status_code >= 500 and attempt == 0 and not is_bot_wall(r):
                time.sleep(5)
                continue
            return r, None
        except requests.exceptions.SSLError:
            if state["verify"]:
                state["verify"] = False
                state["tls_ok"] = False
                continue
            return None, "ssl_error"
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            if attempt == 0:
                time.sleep(5)
                continue
            return None, "timeout" if isinstance(e, requests.exceptions.Timeout) else "connection_error"
        except requests.exceptions.RequestException as e:
            return None, type(e).__name__
    return None, "retries_exhausted"


def is_bot_wall(r) -> bool:
    if r.status_code not in (202, 403, 429, 503):
        return False
    headers = {k.lower(): v.lower() for k, v in r.headers.items()}
    body = r.text[:4000].lower()
    return ("cloudflare" in headers.get("server", "") or "cf-ray" in headers
            or "just a moment" in body or "captcha" in body or "challenge" in body)


def http_problem(r):
    if is_bot_wall(r):
        return "blocked_bot_protection"
    if r.status_code != 200:
        return f"http_{r.status_code}"
    head = r.content[:600].lower()
    if b"<oai-pmh" not in head and b"<?xml" not in head:
        return "not_oai_xml"
    return None


def parse_xml(content: bytes):
    text = BAD_XML_CHARS.sub("", content.decode("utf-8", errors="replace"))
    return ET.fromstring(text.encode("utf-8"))  # defusedxml: no entity expansion or external refs


def parse_identify(root) -> dict:
    err = root.find("oai:error", NS)
    if err is not None:
        return {"oai_error": err.get("code", "unknown")}
    ident = root.find("oai:Identify", NS)
    if ident is None:
        return {"oai_error": "no_identify"}
    out = {
        "repository_name": (ident.findtext("oai:repositoryName", "", NS) or "").strip()[:200],
        "earliest_datestamp": ident.findtext("oai:earliestDatestamp", "", NS),
    }
    tk = ident.find(".//tk:toolkit", NS)
    if tk is not None:
        out["toolkit"] = (tk.findtext("tk:title", "", NS) or "").strip()
        out["toolkit_version"] = (tk.findtext("tk:version", "", NS) or "").strip()
    sample = ident.findtext(".//oid:sampleIdentifier", "", NS)
    if sample:
        out["sample_identifier"] = sample.strip()
    return out


def parse_records(root):
    err = root.find("oai:error", NS)
    if err is not None:
        return [], None, err.get("code", "unknown")
    lr = root.find("oai:ListRecords", NS)
    if lr is None:
        return [], None, "no_listrecords"
    recs = []
    for rec in lr.findall("oai:record", NS):
        h = rec.find("oai:header", NS)
        if h is None or h.get("status") == "deleted":
            continue
        d = {"oai_id": h.findtext("oai:identifier", "", NS),
             "datestamp": h.findtext("oai:datestamp", "", NS),
             "sets": [s.text for s in h.findall("oai:setSpec", NS) if s.text]}
        md = rec.find("oai:metadata/oai_dc:dc", NS)
        if md is not None:
            for el in md:
                tag = el.tag.rsplit("}", 1)[-1]
                val = (el.text or "").strip()
                if not val:
                    continue
                d.setdefault(tag, []).append(val[:2000])
                if tag == "title" and "title_lang" not in d:
                    d["title_lang"] = el.get(XML_LANG, "")
        recs.append(d)
    tok = lr.find("oai:resumptionToken", NS)
    token = (tok.text or "").strip() if tok is not None and tok.text else None
    return recs, token, None


def harvest_journal(session, cand: dict) -> dict:
    jdir = OUT / slug_for(cand["base_url"])
    res_path = jdir / "result.json"
    if res_path.exists():
        return json.loads(res_path.read_text())
    jdir.mkdir(parents=True, exist_ok=True)
    state = {"verify": True, "tls_ok": True}
    res = {k: cand[k] for k in ("lang", "field", "rank", "base_url", "oai_url")}
    res["slug"] = jdir.name

    def finish(status):
        res["status"] = status
        res["tls_ok"] = state["tls_ok"]
        res_path.write_text(json.dumps(res, ensure_ascii=False, indent=1))
        return res

    r, err = fetch(session, cand["oai_url"], {"verb": "Identify"}, state)
    if err:
        return finish(f"identify_{err}")
    res["identify_final_url"] = r.url[:300]
    problem = http_problem(r)
    if problem:
        return finish(f"identify_{problem}")
    (jdir / "identify.xml").write_bytes(r.content)
    try:
        info = parse_identify(parse_xml(r.content))
    except Exception:
        return finish("identify_bad_xml")
    res.update(info)
    if "oai_error" in info:
        return finish(f"identify_oai_{info['oai_error']}")

    params = {"verb": "ListRecords", "metadataPrefix": "oai_dc", "from": FROM}
    records, pages = [], 0
    res["records_error"] = None
    while True:
        time.sleep(PAUSE)
        r, err = fetch(session, cand["oai_url"], params, state)
        if err:
            res["records_error"] = err
            break
        problem = http_problem(r)
        if problem:
            res["records_error"] = problem
            break
        pages += 1
        (jdir / f"records_{pages:02d}.xml").write_bytes(r.content)
        try:
            recs, token, oai_err = parse_records(parse_xml(r.content))
        except Exception:
            res["records_error"] = "bad_xml"
            break
        if oai_err and oai_err != "noRecordsMatch":
            res["records_error"] = f"oai_{oai_err}"
            break
        records.extend(recs)
        if not token:
            break
        if pages >= MAX_PAGES:
            res["capped"] = True
            break
        params = {"verb": "ListRecords", "resumptionToken": token}
    res["pages"] = pages
    res["n_records"] = len(records)
    (jdir / "records.json").write_text(json.dumps(records, ensure_ascii=False))

    if not res.get("toolkit_version"):  # fall back to the homepage generator tag for the OJS version
        time.sleep(PAUSE)
        r, err = fetch(session, cand["base_url"], None, state)
        if not err and r.status_code == 200:
            m = GENERATOR.search(r.text[:20000])
            if m:
                res["generator"] = m.group(1).strip()
    return finish("ok" if not res["records_error"] else "records_failed")


def run_host(items):
    s = requests.Session()
    s.headers["User-Agent"] = UA
    done = []
    for c in sorted(items, key=lambda c: int(c["rank"])):
        try:
            done.append(harvest_journal(s, c))
        except Exception as e:  # never lose the rest of the host's queue
            done.append({**{k: c[k] for k in ("lang", "field", "rank", "base_url")},
                         "status": f"exception_{type(e).__name__}"})
        time.sleep(PAUSE)
    return done


def main():
    cands = pd.read_csv("data/sample/candidates.csv", dtype=str, keep_default_na=False)
    if os.environ.get("LIMIT"):  # smoke-test on the first N candidates
        cands = cands.head(int(os.environ["LIMIT"]))
    by_host = defaultdict(list)
    for c in cands.to_dict("records"):
        by_host[(urlsplit(c["oai_url"]).hostname or "").lower()].append(c)
    print(f"{len(cands)} journals on {len(by_host)} hosts, {WORKERS} workers", flush=True)
    results, t0 = [], time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for fut in as_completed([ex.submit(run_host, v) for v in by_host.values()]):
            for res in fut.result():
                results.append(res)
                print(f"[{len(results):3d}/{len(cands)}] {time.time() - t0:5.0f}s "
                      f"{res['lang']}/{res['field']:<10} {res['status']:<32} "
                      f"n={res.get('n_records', '-')} {res['base_url'][:70]}", flush=True)
    pd.DataFrame(results).to_csv("data/sample/harvest_status.csv", index=False)
    print("status counts:\n", pd.Series([r["status"] for r in results]).value_counts().to_string())


if __name__ == "__main__":
    main()
