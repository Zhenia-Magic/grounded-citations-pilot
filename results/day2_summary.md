# Day 2: can the citations be judged at all?

Pipeline: GROBID 0.9.1 (CRF models) on the Day-1 PDFs, citation links checked against the callouts, references resolved through Crossref and OpenAlex. Intervals resample whole articles.

## Article funnel

| Stage | English stratum | Spanish stratum | Total |
|---|---|---|---|
| Sampled | 40 | 10 | 50 |
| PDF downloaded | 32 | 10 | 42 |
| Parsed with body text and a reference list | 30 | 7 | 37 |
| Citation links mostly resolvable (≥50% of callouts) | 26 | 5 | 31 |
| Body text in the stratum's language | 23 | 5 | 28 |

Usable articles: 28. 3 parsed articles were in another language than their stratum (id, id, id), all tagged as the stratum language by their journals. Articles where linking failed mostly use footnote citation styles, which GROBID reads as numbered callouts.

## What happens to each citation (usable articles)

1,081 in-text citations in 28 articles.

| Outcome | Citations | Share |
|---|---|---|
| Full text open (OpenAlex) | 531 | 49% |
| Abstract only | 70 | 6% |
| Resolved, no abstract or open text | 79 | 7% |
| Unresolved: book or report | 152 | 14% |
| Unresolved: web page | 43 | 4% |
| Unresolved: other | 88 | 8% |
| Linked to the wrong or a junk entry | 12 | 1% |
| Not linked to any reference | 106 | 10% |

- **Judgeable at all** (full text or abstract): 56% (41–66%) of citations.
- **Judgeable against full text**: 49% (37–59%).
- Abstract only, which can confirm support but never refute it: 6% (4–9%).
- Citations in methods sections, which the design treats as cannot-judge by default: 5%.
- For comparison, the proposal's untested guess was 25–40% full text, 10–20% abstract only and 40–65% not judgeable.

## By language and field

| Group | Articles | Citations | Judgeable at all | Full text |
|---|---|---|---|---|
| English stratum | 23 | 1020 | 56% (41–67%) | 50% (36–60%) |
| Spanish stratum | 5 | 61 | 46% (18–56%) | 43% (17–54%) |
| health | 9 | 296 | 76% (65–82%) | 71% (60–76%) |
| scitech | 9 | 211 | 50% (31–64%) | 47% (31–60%) |
| social | 3 | 137 | 55% (33–59%) | 47% (33–50%) |
| humanities | 7 | 437 | 45% (13–66%) | 36% (10–53%) |

## Cited works (references cited at least once in a usable article)

- Distinct cited works: 670. Across all parsed articles GROBID also produced 68 junk entries such as checklist lines, which are excluded.
- DOI printed in the reference: 370; found by Crossref search: 115; no DOI found: 185.
- Kinds as parsed: article 468, book_or_report 137, chapter 55, other 10.
- Open access per OpenAlex: 360 of 457 resolved works.
- Retracted works cited: 0.


## Caveats

- Open access means OpenAlex knows an open copy. Day 3 has to fetch those copies, and some will be behind bot walls or dead links, so full-text shares here are upper bounds.
- Crossref matches had to agree on title and year or author, so some findable works count as unresolved: precision was preferred to recall.
- GROBID ran with its light CRF models; its deep-learning models link more callouts but need a 15 GB image.
- Small sample: 28 usable articles from 18 journals, so per-field rows are indicative only.

## Retrieval check: can the open copies actually be fetched?

For the 157 citations prepared for judging, the open copies were fetched as a client would: the OpenAlex PDF link, else the landing page's `citation_pdf_url` tag, respecting robots.txt.

- Cited works listed as open access: 122; PDF retrieved: 58 (48%); behind bot protection: 24; no PDF found: 40.
- Sampled citations whose source OpenAlex lists as open: 138; full text actually obtained for 66 (48%); the rest fall back to the abstract where one exists.
- Applied to the headline, citations judgeable against retrieved full text are roughly 23% rather than 49%. Publisher text-mining access, Europe PMC and repository copies could close part of that gap.

