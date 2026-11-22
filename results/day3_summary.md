# Day 3: two AI judges on real citations

Run on 21–22 November 2026. Judges: Claude Opus 5.5 and GPT-6.2 Sol, with the same prompt, output
format and rules. Every verdict must quote the cited source word for word, and code checks each quote.
Details: `results/day3_benchmark.md` (benchmark) and `results/day3_ojs.md` (journal citations).

## Benchmark: 300 expert-labelled citations from the Citation-Integrity test set

| | Claude Opus 5.5 | GPT-6.2 Sol | Both must agree | Best published system (2024) |
|---|---|---|---|---|
| Items scored | 250 | 300 | 250 | Full test set |
| Accuracy | 0.63 | 0.48 | 0.50 | 0.59 |
| Macro-F1 (95% CI) | 0.46 (0.39–0.53) | 0.37 (0.32–0.42) | 0.45 (0.39–0.51) | 0.52 |
| "Supported" verdicts the experts agree with | 74% of 175 | 80% of 129 | 81% of 104 | – |
| "Not accurate" flags the experts agree with | 30% of 66 | 22% of 161 | 30% of 66 | – |

- **Claude roughly matches the best published system.** It beats it on accuracy, 0.63 against 0.59. Its macro-F1, 0.46, is lower than the published 0.52, but the published figure sits inside its confidence interval. GPT-6.2 Sol is clearly weaker: 0.37 on the 250 items both judges answered.
- **Flags are mostly wrong.** Of the 66 citations both judges flagged, the experts called 20 not accurate, 23 accurate and 23 not judgeable. That is 30% precision and about 78% specificity, against the 97% the design requires before any negative note. Most flags use the label "partly supported": both judges are stricter than the experts about paraphrase and generalising. GPT-6.2 Sol used that label 136 times.
- **Requiring both judges to agree removed no flags.** GPT-6.2 Sol flagged every citation Claude flagged, and more, so the rule kept exactly Claude's flags. It helps only when the two judges make different mistakes.
- **"Supported" verdicts are right about four times in five.** That makes notes confirming support the realistic first product, still reviewed before anything is published.
- **Claude declined virus papers.** Opus 5.5 declined 50 of the 300 items, so a backup model answered them; those items are flagged and left out of the scores. Almost all came from three sources:
  - a SARS-CoV-2 study in macaques (19 of 27 items),
  - an HIV paper (16 of 16),
  - a remdesivir trial (8 of 11).

  The others were 5 of 18 on a COVID-19 gene study and one item each from two other sources. Claude declined none of the 157 journal citations.
- **The judges agree with each other on 70% of benchmark items** (Cohen's kappa 0.47).

## Journal citations: 157 sampled from 28 OJS articles

| | Supported | Negative | Can't judge |
|---|---|---|---|
| Claude Opus 5.5 | 42% | 17% (plus 1% unrelated) | 41% |
| GPT-6.2 Sol | 21% | 24% | 55% |
| Both must agree | 21% (33) | 15% (24) | 64% |

- **Full text (66 citations):** both judges agree on "supported" for 32% and on a negative for 36% (24 citations); 32% can't be judged.
- **Abstract only (91 citations):** 13% supported. None can be negative, because an abstract can't show that support is missing.
- **The judges agree on 76% of journal citations** (kappa 0.64).
- **The negative share looks too high.** Negatives make up 36% of full-text citations, about twice the roughly 17% error rate studies report for medical citations. That fits the over-flagging seen on the benchmark. The hand-check will measure it directly.

## Cost and running

- **Total API spend: $23.77.** Claude cost $12.37 and GPT-6.2 Sol $10.75, both including their calibrations, plus $0.65 for the GPT-5.6 Sol calibration. Each full run took about ten minutes.
- **Caching:** Claude read 75% of its input tokens from its cache. OpenAI's cache never helped (0 of 457 requests), yet every request was billed at the cache-write rate, 25% above the normal input price.

## What this means for the pitch

- **Validation is the centre of the project.** Unvalidated negative notes would be wrong most of the time. Notes confirming support, with the quoted passage and an editor reviewing them, come first.
- **The over-flagging has a specific cause:** one label boundary, "partly supported". That gives the grant a concrete research task: recalibrate that boundary against expert labels on one part of the test set, then measure on a held-out part.
- **This result is the case for the open test set.** It exposed false alarms on sound citations, which a benchmark built only from planted errors cannot measure.
- **A better second judge is an open question.** A more conservative or stronger model, such as GPT-5.6 Sol (about $19 for the benchmark) or GPT-6.2 Astra, might make the agreement rule worth having.

## Caveats

- **Label mismatch:** the judges' seven labels map onto the benchmark's three classes. "Not supported" overlaps with the benchmark's "not enough information"; most failed "not supported" flags are on such items, so part of the measured false alarm rate may come from that mismatch.
- **Clustering:** the 300 items come from 20 cited sources. The confidence intervals resample items, not sources, so they understate the uncertainty.
- **Uneven coverage:** Claude's 250 scored items exclude most citations to three virology sources.

## Next: Day 4 hand-check

50 English journal citations in `data/day4/`:
- 22 that both judges flag,
- 8 that one judge flags,
- 5 other disagreements,
- 15 that both call supported.

The sheet doesn't show what the judges said. Label every item and note the minutes each took, then open `handcheck_key.csv`.
