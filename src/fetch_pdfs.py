"""Day 2, step 1: download the sampled articles' PDF galleys, politely.

For each article, turn each OJS galley view URL (/article/view/<art>/<galley>)
into its download URL (/article/download/<art>/<galley>), keep the first
response that really is a PDF (checked by magic bytes, not by Content-Type),
and fall back to the download link on the galley view page. robots.txt is
respected; bot walls are recorded, not bypassed. Results are cached.

Usage: python src/fetch_pdfs.py
"""
import json
import os
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib import robotparser
from urllib.parse import unquote, urljoin, urlsplit

import pandas as pd
import requests
import urllib3

from harvest_oai import UA, is_bot_wall

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
OUT = Path("data/raw/pdf")
PAUSE = 2.0
TIMEOUT = (15, 90)
MAX_BYTES = 60_000_000
DOWNLOAD_LINK = re.compile(r'href=["\']([^"\']*/article/download/[^"\']+)["\']', re.I)
PDFJS_FILE = re.compile(r'viewer\.html\?file=([^"\'&\s]+)', re.I)  # themes that embed PDF.js


def download_links(html):
    links = [m.group(1) for m in DOWNLOAD_LINK.finditer(html)]
    links += [unquote(m.group(1)) for m in PDFJS_FILE.finditer(html)]
    return list(dict.fromkeys(l.replace("&amp;", "&") for l in links))[:3]


def robots_for(session, url, cache):
    host = urlsplit(url)
    key = f"{host.scheme}://{host.netloc}"
    if key not in cache:
        rp = robotparser.RobotFileParser()
        try:
            r = session.get(key + "/robots.txt", timeout=TIMEOUT, verify=False)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except requests.RequestException:
            rp.parse([])
        cache[key] = rp
    return cache[key].can_fetch(UA, url)


def get_pdf(session, url):
    """Return (bytes, note). Accepts only real PDFs up to MAX_BYTES."""
    try:
        r = session.get(url, timeout=TIMEOUT, stream=True, verify=False, allow_redirects=True)
    except requests.RequestException as e:
        return None, type(e).__name__
    if is_bot_wall(r):
        return None, "blocked_bot_protection"
    if r.status_code != 200:
        r.close()
        return None, f"http_{r.status_code}"
    try:  # read only through iter_content: mixing raw.read() with it breaks chunked responses
        it = r.iter_content(65536)
        first = b""
        for chunk in it:
            first += chunk
            if len(first) >= 1024:
                break
        if b"%PDF-" not in first[:1024]:  # the PDF header may sit anywhere in the first 1 KB
            body = first
            for chunk in it:
                body += chunk
                if len(body) > 200_000:
                    break
            return None, ("html", body.decode("utf-8", errors="replace"))
        chunks, size = [first], len(first)
        for chunk in it:
            size += len(chunk)
            if size > MAX_BYTES:
                return None, "too_large"
            chunks.append(chunk)
        return b"".join(chunks), "ok"
    except (requests.RequestException, urllib3.exceptions.HTTPError, OSError) as e:
        return None, f"read_error_{type(e).__name__}"
    finally:
        r.close()


def fetch_article(session, a, robots_cache):
    meta_p = OUT / f"{a['article_id']}.json"
    if meta_p.exists():
        cached = json.loads(meta_p.read_text())
        # RETRY_FAILED=1 re-tries plain failures; bot-protection results are never retried.
        if not (os.environ.get("RETRY_FAILED") and cached["status"] == "no_pdf"):
            return cached
    meta = {"article_id": a["article_id"], "status": "no_pdf", "tried": []}
    for view in [u for u in a["galley_urls"].split("|") if u]:
        dl = view.replace("/article/view/", "/article/download/", 1)
        for url in (dl, view):
            if not robots_for(session, url, robots_cache):
                meta["tried"].append([url, "robots_disallow"])
                continue
            time.sleep(PAUSE)
            data, note = get_pdf(session, url)
            if data:
                (OUT / f"{a['article_id']}.pdf").write_bytes(data)
                meta.update(status="ok", pdf_url=url, bytes=len(data))
                meta_p.write_text(json.dumps(meta, indent=1))
                return meta
            if isinstance(note, tuple):  # an HTML page: look for the galley's download link
                meta["tried"].append([url, "html"])
                if url != view:
                    continue
                for link in download_links(note[1]):
                    link = urljoin(view, link)
                    if link == dl or not robots_for(session, link, robots_cache):
                        continue
                    time.sleep(PAUSE)
                    data, note2 = get_pdf(session, link)
                    if data:
                        (OUT / f"{a['article_id']}.pdf").write_bytes(data)
                        meta.update(status="ok", pdf_url=link, bytes=len(data))
                        meta_p.write_text(json.dumps(meta, indent=1))
                        return meta
                    meta["tried"].append([link, note2 if isinstance(note2, str) else "html"])
            else:
                meta["tried"].append([url, note])
                if note == "blocked_bot_protection":
                    meta["status"] = "blocked_bot_protection"
                    meta_p.write_text(json.dumps(meta, indent=1))
                    return meta
    meta_p.write_text(json.dumps(meta, indent=1))
    return meta


def run_host(items):
    s = requests.Session()
    s.headers["User-Agent"] = UA
    cache, done = {}, []
    for a in items:
        try:
            done.append(fetch_article(s, a, cache))
        except Exception as e:  # never lose the rest of the host's queue or the final report
            done.append({"article_id": a["article_id"], "status": f"exception_{type(e).__name__}"})
    return done


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    arts = pd.read_csv("data/sample/articles.csv", dtype=str, keep_default_na=False)
    by_host = defaultdict(list)
    for a in arts.to_dict("records"):
        first = a["galley_urls"].split("|")[0]
        by_host[(urlsplit(first).hostname or "").lower()].append(a)
    results = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for fut in as_completed([ex.submit(run_host, v) for v in by_host.values()]):
            for m in fut.result():
                results.append(m)
                print(f"[{len(results):2d}/{len(arts)}] {m['status']:<22} {m['article_id'][:80]}", flush=True)
    pd.DataFrame(results).to_csv("data/sample/pdf_status.csv", index=False)
    print(pd.Series([m["status"] for m in results]).value_counts().to_string())


if __name__ == "__main__":
    main()
