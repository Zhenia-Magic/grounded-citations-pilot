# Day 2: how many citations can be checked?

The sampled articles were downloaded and turned into text with GROBID 0.9.1, and each in-text citation was linked to its reference. The cited works were looked up in Crossref and OpenAlex. Intervals resample whole articles.

## Which articles could be used

| Stage | English journals | Spanish journals | Total |
|---|---|---|---|
| Sampled | 40 | 10 | 50 |
| PDF downloaded | 32 | 10 | 42 |
| Parsed into body text and a reference list | 30 | 7 | 37 |
| At least half the citations linked to a reference | 26 | 5 | 31 |
| Body text in the expected language | 23 | 5 | 28 |

3 of the 30 journals put their PDFs behind bot protection, although their article lists were open. The script recorded this and did not get around it. Linking failed mostly in articles with footnote citations, and 3 articles were in a different language from the one their journals' records gave.

## What happens to each citation

1,081 in-text citations in the 28 usable articles:

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

- Can be checked at all (open full text or an abstract): 56% (41-66%).
- Can be checked against full text: 49% (37-59%).
- Abstract only: 6% (4-9%). An abstract can confirm support but can't show that it is missing.

## Can the open copies actually be downloaded?

For 157 sampled citations, a script tried to download each open copy the way any outside tool would: the PDF link OpenAlex gives, or else the one on the article's page.

- Of 122 cited works listed as open access, 58 were downloaded (48%). 24 were behind bot protection and 40 had no PDF to find.
- Full text was obtained for 66 of the 138 citations whose source is listed as open (48%). The rest fall back to the abstract where there is one.
- So only about 23% of all citations can be checked against full text that a script can actually get, not 49%.

## Caveats

- Crossref matches had to agree on title and year or author, so some findable works count as unresolved.
- GROBID ran with its light models. Its larger deep-learning models link more citations.
- Small sample: 28 usable articles from 18 journals.
