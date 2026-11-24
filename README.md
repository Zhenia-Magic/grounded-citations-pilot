# Grounded Citations: OJS pilot

Grounded Citations is a planned tool that checks whether the sources cited in a journal article
support the sentences that cite them, and shows the passage it relied on. This pilot, run in
November 2026, tested how well that works for open-access journals that use Open Journal Systems (OJS).

## What the pilot found

- Most journals let a program list their articles. 100 of 120 sampled OJS journals (83%) do so
  through OAI-PMH, a standard feed built into OJS.
- Most publish full text only as PDF. About 76% have no HTML or XML version of their articles.
- About a quarter of citations can be checked against the full source. Of 1,081 citations in
  28 articles, 56% point to a source with an open full text or abstract, but only about 23% to
  full text that a script could actually download.
- AI judges can confirm support but are not yet good at finding problems. On 300 citations
  already labelled by experts, when both judges (Claude Opus 5.5 and GPT-6.2 Sol) said a citation
  was supported, the experts agreed 81% of the time. When both flagged a problem, the experts
  agreed only 30% of the time.
- Claude Opus 5.5 alone scored about as well as the best published system on that benchmark:
  accuracy 0.63 against 0.59, and macro-F1 0.46 against 0.52.
- The whole pilot cost $23.77 in API fees.

More detail: [day 1](results/day1_summary.md) (journals), [day 2](results/day2_summary.md)
(citations) and [day 3](results/day3_summary.md) (AI judges).

## How it works

1. Draw 120 OJS journals at random from the DOAJ journal list and read their article lists.
2. Download the PDFs of 50 sampled articles, turn them into text with GROBID and link each
   in-text citation to its reference.
3. Look up the cited works in Crossref and OpenAlex and download the open copies.
4. Ask two AI judges whether each cited source supports the sentence that cites it. Every
   verdict must quote the source, and the code checks each quote word for word.
5. Score the judges against expert labels from the Citation-Integrity benchmark
   (Sarol et al., 2024).

## Run it

You need Python 3.12, uv, Docker (for GROBID) and API keys for Anthropic and OpenAI. Put the keys
in a file called `.env` in this folder (git ignores it):

```
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
```

Then run each step from this folder:

```bash
uv venv --python 3.12
uv pip install requests defusedxml pandas py3langid anthropic==2.12.0 openai==3.46.0
PY=.venv/bin/python

# Day 1: sample journals and list their articles
curl -L --create-dirs -o data/raw/doaj/doaj.csv https://doaj.org/csv
$PY src/sample_journals.py data/raw/doaj/doaj.csv
$PY src/harvest_oai.py
$PY src/summarise_day1.py

# Day 2: download and parse the articles, find the cited works
$PY src/fetch_pdfs.py
bash scripts/start_grobid.sh
$PY src/run_grobid.py
$PY src/extract_contexts.py
ONLY_NEEDED=1 $PY src/resolve_refs.py
$PY src/summarise_day2.py
$PY src/fetch_cited_texts.py
$PY src/summarise_day2.py    # again, to add the download check

# Day 3: judge, with each run capped at a budget in US dollars
$PY src/get_ci_corpus.py
$PY src/benchmark_ci.py
$PY src/judge_claude.py data/day3/ci_inputs.jsonl --budget 12
$PY src/judge_claude.py data/day3/ojs_inputs.jsonl --budget 8
$PY src/judge_openai.py data/day3/ci_inputs.jsonl --budget 10
$PY src/judge_openai.py data/day3/ojs_inputs.jsonl --budget 4
$PY src/score_benchmark.py data/day3/judgments/claude-opus-5-5 data/day3/judgments/gpt-6.2-sol
$PY src/summarise_day3.py data/day3/judgments/claude-opus-5-5 data/day3/judgments/gpt-6.2-sol
```

DOAJ updates its list, so a new download draws different journals. The pilot used
`doaj_journalcsv_20261021_2320_utf8.csv`.

## What is not here

The `data/` folder is private. It holds other people's articles, and AI verdicts on identifiable
papers, which this project won't publish until the judge is validated. The steps above rebuild it
from public sources.

The scripts identify themselves, pause between requests to the same site, respect robots.txt
for downloads and never get around bot protection.
