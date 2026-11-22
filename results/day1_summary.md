# Day 1: OJS journal sample and full-text formats

Run 2026-11-21 on DOAJ's journal list `doaj_journalcsv_20261021_2320_utf8.csv`.

## Sampling frame

- DOAJ lists 23,660 journals; 7,285 have OJS-style `/index.php/<journal>` homepages.
- In scope: 3,933 that accept English but not Spanish (EN) and 2,528 that accept Spanish (ES).
- Seeded random draw (seed 20261121) within 8 strata (2 languages x 4 field groups): 120 candidates, 4x the quota of 30.

## Can an outside tool harvest them? (all candidates)

| Outcome | Journals | Share (95% CI) |
|---|---|---|
| OAI works | 100 | 100/120 = 83% (76–89%) |
| HTTP error | 9 | 9/120 = 8% (4–14%) |
| Unreachable (timeout, DNS, TLS) | 5 | 5/120 = 4% (2–9%) |
| Blocked by bot protection | 3 | 3/120 = 2% (1–7%) |
| Not an OAI response / other | 2 | 2/120 = 2% (0–6%) |
| Identify works, record listing fails | 1 | 1/120 = 1% (0–5%) |

- Confirmed OJS among working endpoints: 100/100 = 100% (96–100%).
- Working only after skipping certificate checks (broken TLS): 8/100 = 8% (4–15%).
- Active (at least 3 articles dated 2025–26): 99/100 = 99% (95–100%) of working endpoints.
- Journals whose record listing hit the 8-page cap: 1.

OJS versions among confirmed OJS journals with working endpoints:

- 3.3: 46
- 3.4–3.5: 35
- 3.0–3.2: 13
- 2.x: 6

## How full text is published (active journals, articles dated 2025–26)

99 active journals, 6,272 articles.

| Group | Articles | PDF only | Any HTML | Any XML | No file type listed |
|---|---|---|---|---|---|
| All | 6,272 | 5456/6272 = 87% (86–88%) | 516/6272 = 8% (8–9%) | 311/6272 = 5% (4–6%) | 43/6272 = 1% (1–1%) |
| EN journals | 4,987 | 4739/4987 = 95% (94–96%) | 113/4987 = 2% (2–3%) | 109/4987 = 2% (2–3%) | 20/4987 = 0% (0–1%) |
| ES journals | 1,285 | 717/1285 = 56% (53–58%) | 403/1285 = 31% (29–34%) | 202/1285 = 16% (14–18%) | 23/1285 = 2% (1–3%) |

Journal level: 78/99 = 79% (70–86%) of active journals published no HTML or XML full text for any 2025–26 article.
The median journal's share of PDF-only articles is 100%. Journals published a median of 45 articles in 2025–26 (range 5–495); the five largest supply 26% of the pooled articles, so read the article-level rows as descriptive.

Weighted to the in-scope DOAJ frame: about 76% of journals are PDF-only (approximate 95% CI 68–85%).

## DOIs and article languages

- Articles with a DOI in their OAI record: 5774/6272 = 92% (91–93%).
- Languages of 2025–26 articles in EN-stratum journals, as the journals tag them: en 4216, ru 183, uk 178, fr 163, it 86, hu 53.
- Records tagged English whose title or abstract is detected as another language too: 734/4216 = 17% (16–19%); most often fr (304), id (271), uk (55), it (37). Many are bilingual records (an English abstract beside the original), so the tag alone can't tell you the body's language. Day 2 checks each parsed body before the English hand-check.
- Day-2 articles whose title and abstracts are all detected as the stratum language: 43 of 50.

## Day-2 sample

| Stratum | Journals needed | Selected | Eligible found |
|---|---|---|---|
| EN/health | 5 | 5 | 17 |
| EN/humanities | 5 | 5 | 14 |
| EN/scitech | 5 | 5 | 19 |
| EN/social | 5 | 5 | 14 |
| ES/health | 2 | 2 | 4 |
| ES/humanities | 3 | 3 | 6 |
| ES/scitech | 2 | 2 | 6 |
| ES/social | 3 | 3 | 7 |

30 journals selected; 50 articles sampled (40 English, 10 Spanish). Eligible means working OAI, confirmed OJS and at least 3 2025–26 articles in the stratum's language.

## PDF downloads (Day 2, step 1)

- PDFs fetched: 42 of 50 (32 English, 10 Spanish).
- Journals whose PDF downloads sit behind bot protection, although their OAI endpoint works: 3 of 30. Recorded, not bypassed.
- Journals where no PDF could be reached from the galley links: 1.
- Downloads respected robots.txt and paused 2 s between requests to the same host.

## Caveats

- DOAJ-listed journals are better resourced than OJS's long tail, so the PDF-only share across all OJS journals is probably higher than this.
- File types come from the journals' own OAI records (`dc:format`); an HTML galley can still be a thin wrapper around a PDF.
- Article dates come from `dc:date`; records were requested from datestamp 2025-01-01, which catches every article published since then.
- Bot-protected endpoints were recorded, not bypassed.
