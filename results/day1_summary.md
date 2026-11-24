# Day 1: can a program read OJS journals?

6,461 of the 23,660 journals in DOAJ's list (`doaj_journalcsv_20261021_2320_utf8.csv`) have OJS-style homepages and accept articles in English or Spanish. 120 of them were drawn at random, across 2 languages and 4 fields.

## Can a program list their articles?

OJS has a standard feed for this, OAI-PMH.

| Outcome | Journals | Share (95% CI) |
|---|---|---|
| OAI works | 100 | 83% (76-89%) |
| HTTP error | 9 | 8% (4-14%) |
| Unreachable (timeout, DNS, TLS) | 5 | 4% (2-9%) |
| Blocked by bot protection | 3 | 2% (1-7%) |
| Not an OAI response / other | 2 | 2% (0-6%) |
| Identify works, record listing fails | 1 | 1% (0-5%) |

99 of the 100 working journals published at least 3 articles in 2025-26. The rest of this page covers those active journals.

## How is the full text published?

6,272 articles dated 2025-26 in the 99 active journals:

| Journals | Articles | PDF only | Any HTML | Any XML |
|---|---|---|---|---|
| All | 6,272 | 87% (86-88%) | 8% (8-9%) | 5% (4-6%) |
| English-language | 4,987 | 95% (94-96%) | 2% (2-3%) | 2% (2-3%) |
| Spanish-language | 1,285 | 56% (53-58%) | 31% (29-34%) | 16% (14-18%) |

78 of the 99 active journals (79%) published no HTML or XML full text for any 2025-26 article. Weighted to the DOAJ list, that is about 76% of journals (95% CI 68-85%).

For Day 2, 30 of the active journals (20 English-language, 10 Spanish-language) and 50 of their articles were sampled.

## Caveats

- DOAJ lists better-resourced journals than the long tail of OJS, so across all OJS journals the PDF-only share is probably higher.
- File types come from the journals' own records, and an HTML version can still be a thin wrapper around a PDF.
