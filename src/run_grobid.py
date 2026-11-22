"""Day 2, step 2: parse the downloaded PDFs into TEI XML with a local GROBID server.

Start GROBID first (light CRF models, ~0.5 GB image):
    docker run --rm -d --name grobid -p 8070:8070 grobid/grobid:0.9.1-crf

Sentence segmentation is on, so every in-text citation lands inside an <s> element,
which is what the context extractor needs. Citation consolidation is off: we
resolve references ourselves against Crossref and OpenAlex, with our own thresholds.
"""
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

GROBID = "http://localhost:8070"
IN, OUT = Path("data/raw/pdf"), Path("data/tei")
PARAMS = {"consolidateHeader": "0", "consolidateCitations": "0", "includeRawCitations": "1",
          "includeRawAffiliations": "0", "segmentSentences": "1"}


def alive() -> bool:
    try:
        return requests.get(f"{GROBID}/api/isalive", timeout=5).text.strip() == "true"
    except requests.RequestException:
        return False


def parse(pdf: Path):
    out = OUT / f"{pdf.stem}.tei.xml"
    if out.exists():
        return pdf.stem, "cached", 0.0
    t0 = time.time()
    for attempt in range(6):
        with pdf.open("rb") as fh:
            r = requests.post(f"{GROBID}/api/processFulltextDocument", files={"input": fh},
                              data=PARAMS, timeout=300)
        if r.status_code == 503:  # GROBID's worker pool is busy: back off and retry
            time.sleep(2 * (attempt + 1))
            continue
        if r.status_code == 200:
            out.write_bytes(r.content)
            return pdf.stem, "ok", time.time() - t0
        return pdf.stem, f"http_{r.status_code}", time.time() - t0
    return pdf.stem, "busy", time.time() - t0


def main():
    if not alive():
        sys.exit("GROBID is not answering on localhost:8070; start the container first.")
    OUT.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(IN.glob("*.pdf"))
    with ThreadPoolExecutor(max_workers=4) as ex:
        for stem, status, secs in ex.map(parse, pdfs):
            print(f"{status:<9} {secs:5.1f}s {stem}", flush=True)


if __name__ == "__main__":
    main()
