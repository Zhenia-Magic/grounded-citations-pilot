# Grounded Citations: OJS citation-support pilot

A pilot for Grounded Citations, a tool that checks whether citations in open-access journal
articles are supported by the sources they cite, and shows the excerpt behind each verdict.
It measures how far an outside tool can do this, after publication, for journals running
Open Journal Systems (OJS).

## Results so far

- [Day 1](results/day1_summary.md): of 120 sampled OJS journals, 83% let a program list
  their articles through OAI-PMH, and about 76% publish only PDFs.
- [Day 2](results/day2_summary.md): of 1,081 in-text citations in 28 articles, 56% point to
  an open text or abstract, but only about 23% could be checked against full text that a
  script could actually fetch.
- [Day 3](results/day3_summary.md): on 300 citations already labelled by experts
  (Citation-Integrity), two AI judges' joint "supported" verdicts were right 81% of the
  time and their joint "not accurate" flags only 30%. Details in
  [day3_benchmark.md](results/day3_benchmark.md) and [day3_ojs.md](results/day3_ojs.md).

## What is not in this repository

- `data/`: third-party article PDFs and text, harvested metadata, the cited works' text,
  the model verdicts on identifiable articles (kept private by the project's own rule that
  no negative note is published before it is validated), and the blind hand-check kit.
  The scripts below rebuild it from public sources.
- API keys, which live in a git-ignored `.env`.

Developed on Ubuntu (WSL2) with Python 3.12 via uv; GROBID runs in Docker.

## Day 1: sample and harvest (done 2026-11-21)

```bash
uv venv --python 3.12
uv pip install requests defusedxml pandas py3langid
curl -L -o data/raw/doaj/doaj_journalcsv_20261021_2320_utf8.csv https://doaj.org/csv  # ~26 MB
.venv/bin/python src/sample_journals.py data/raw/doaj/doaj_journalcsv_20261021_2320_utf8.csv
.venv/bin/python src/harvest_oai.py       # ~3 min; cached per journal under data/raw/oai/
.venv/bin/python src/summarise_day1.py    # results/day1_summary.md and data/sample/*.csv
```

The sample is seeded (20261121), so rerunning on the same DOAJ file gives the same journals.
DOAJ's export changes monthly; keep the dated file for reproducibility.

## Day 2: fetch, parse, link and resolve (done 2026-11-21)

```bash
.venv/bin/python src/fetch_pdfs.py          # PDFs into data/raw/pdf/ (RETRY_FAILED=1 retries plain failures)
bash scripts/start_grobid.sh                # GROBID 0.9.1 CRF image on localhost:8070 (Docker in WSL)
.venv/bin/python src/run_grobid.py          # TEI into data/tei/
.venv/bin/python src/extract_contexts.py    # references, citation contexts, link checks -> data/day2/
ONLY_NEEDED=1 .venv/bin/python src/resolve_refs.py   # Crossref + OpenAlex for cited works (~15 min)
.venv/bin/python src/summarise_day2.py      # results/day2_summary.md
```

## Day 3: judge (done 2026-11-22; results in `results/day3_summary.md`)

Two judges from different model families: Claude Opus 5.5 and OpenAI's GPT-6.2 Sol.

```bash
uv pip install anthropic==2.12.0 openai==3.46.0   # openai pinned to a release at least two weeks old
.venv/bin/python src/benchmark_ci.py        # Citation-Integrity test sample -> data/day3/ci_inputs.jsonl
.venv/bin/python src/fetch_cited_texts.py   # 160 OJS citations sampled, open cited texts fetched -> ojs_inputs.jsonl (157)
# Calibration: 10 benchmark items per judge; check the measured cost per item before going on
.venv/bin/python src/judge_claude.py data/day3/ci_inputs.jsonl --limit 10 --budget 2
.venv/bin/python src/judge_openai.py data/day3/ci_inputs.jsonl --limit 10 --budget 2
# Full runs, each judge: the benchmark then the OJS citations, with a USD cap for each
bash scripts/run_day3_full.sh claude 12 8
bash scripts/run_day3_full.sh gpt 10 4
.venv/bin/python src/score_benchmark.py data/day3/judgments/claude-opus-5-5 data/day3/judgments/gpt-6.2-sol
.venv/bin/python src/summarise_day3.py data/day3/judgments/claude-opus-5-5 data/day3/judgments/gpt-6.2-sol
```

- `judge_prompt.py` holds the prompt, the output schema, quote verification and the
  publication rules shared by every judge model, including the two-judge rule
  (`combine`): a negative label stands only when both judges give one.
- `judge_common.py` holds the budget ledger, `.env` loading and grouping by cited source.
- Each judge writes one file per item under `data/day3/judgments/<model>/` and skips
  items already there, refusals and errors included, so a run stopped by its budget resumes.
- `--dry-run` builds the first request without calling the API. For `judge_openai.py` it
  also checks the schema against strict structured outputs and the request parameters
  against the installed SDK.
- GPT-6.2 Sol costs $2 input and $10 output per million tokens, half of Claude Opus 5.5.
  Other choices: `--model gpt-5.6-sol` (promotional price until 30 November 2026; from
  1 December the ledger assumes the implied pre-promotion $5 and $30) and
  `--model gpt-6.2-astra`, OpenAI's flagship, at four times 6.2 Sol's price.
- `estimate_cost.py <judgments folder>` projects full-run costs from a calibration's usage.
- Credentials: the OpenAI key goes in the git-ignored `.env` after `OPENAI_API_KEY=`
  (the file has a commented template). Claude uses an `ant auth login` sign-in made in
  Ubuntu, or an `ANTHROPIC_API_KEY` line in `.env`, which overrides the sign-in. Each
  judge makes a free models call first and stops with a message if its credential fails.

## Day 4: hand-check (kit built by `summarise_day3.py`)

- `data/day4/handcheck_sheet.csv`: up to 50 English citations. Give each one label from the
  seven in the item file, the minutes it took, and notes. Opens in Excel.
- `data/day4/items/NN_<item>.md`: the citing context and the same source text the judges saw.
- `data/day4/handcheck_key.csv`: the judges' labels and why each item was picked
  (negative by both judges, by one, other disagreement, or a random agreed item).
  Open it only after labelling, so the labels stay blind.

## Politeness and safety

- User-Agent `ojs-citation-pilot/0.1` with no personal details. One worker per host,
  1–2 s between requests to the same host, and a page cap per journal.
- robots.txt is respected for PDF downloads. Bot-protection pages are recorded, never bypassed.
- XML is parsed with defusedxml. Text from journal sites is treated as untrusted input,
  and later reaches a model only inside delimiters.
- On certificate errors the harvester retries without TLS verification, for public
  metadata only, and counts how often that happened.
- `data/raw/` is git-ignored: it holds third-party content (OAI XML, PDFs) that is
  analysed but must not be republished.

## Layout

| Path | Contents |
|---|---|
| `src/` | One script per step, plus `peek_results.py` and `check_day2_prereqs.py` helpers |
| `data/raw/` | Downloads: DOAJ list, OAI responses, PDFs (git-ignored) |
| `data/sample/` | Frame counts, candidates, harvest status, the 30 journals and 50 articles |
| `data/records_recent.csv` | One row per 2025–26 record from the 99 active journals |
| `results/` | Write-ups for each day |
