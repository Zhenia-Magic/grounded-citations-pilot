#!/usr/bin/env bash
# Re-run Day 2 from the parsed TEI onwards. Crossref, OpenAlex and PDF downloads are cached,
# so this only makes requests for references or open copies not seen before.
set -euo pipefail
cd ~/ml/ojs-citation-pilot
PY=.venv/bin/python
bash scripts/start_grobid.sh >/dev/null
ONLY_NEEDED=1 $PY src/resolve_refs.py | tail -12
$PY src/summarise_day2.py >/dev/null      # writes contexts_usable.csv for the sampler
$PY src/fetch_cited_texts.py | tail -9
$PY src/summarise_day2.py >/dev/null      # adds the retrieval check
echo "--- day 2 summary written: results/day2_summary.md"
