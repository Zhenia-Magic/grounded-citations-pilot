# Day 3: two AI judges on real citations

Claude Opus 5.5 and GPT-6.2 Sol judged the same citations with the same prompt and rules, on
21 and 22 November 2026. Every verdict had to quote the cited source, and every quote in the
scored verdicts appears word for word in the source.

## Benchmark: 300 citations labelled by experts

The citations come from the test set of Citation-Integrity (Sarol et al., 2024), where experts
labelled each biomedical citation accurate, not accurate or not enough information.

| | Claude Opus 5.5 | GPT-6.2 Sol | Both must agree | Best published system |
|---|---|---|---|---|
| Items scored | 250 | 300 | 250 | full test set |
| Accuracy | 0.63 | 0.48 | 0.50 | 0.59 |
| Macro-F1 (95% CI) | 0.46 (0.39 to 0.53) | 0.37 (0.32 to 0.42) | 0.45 (0.39 to 0.51) | 0.52 |
| "Supported" verdicts the experts agree with | 74% of 175 | 80% of 129 | 81% of 104 | |
| Flags the experts agree with | 30% of 66 | 22% of 161 | 30% of 66 | |

- Claude roughly matches the best published system. Its accuracy is higher, and the published
  macro-F1 of 0.52 is inside Claude's confidence interval.
- Most flags are wrong. Of the 66 citations both judges flagged, the experts called 20 not
  accurate, 23 accurate and 23 not judgeable. Most flags were "partly supported": both judges
  are stricter than the experts about paraphrase.
- Requiring both judges to agree removed no flags, because GPT-6.2 Sol flagged every citation
  that Claude flagged.
- Claude declined 50 of the 300 items, most of them about three virus studies (SARS-CoV-2 in
  macaques, HIV and remdesivir). They are left out of its scores. It declined none of the
  journal citations.

## Journal citations: 157 from 28 OJS articles

| | Supported | Flagged | Can't judge |
|---|---|---|---|
| Claude Opus 5.5 | 42% | 17% (plus 1% unrelated) | 41% |
| GPT-6.2 Sol | 21% | 24% | 55% |
| Both must agree | 21% | 15% | 64% |

- 66 citations could be checked against the full source. Both judges flagged 24 of them (36%),
  about twice the roughly 17% error rate that studies report for medical citations. That fits
  the over-flagging seen on the benchmark.
- The other 91 could only be checked against an abstract. An abstract can confirm support but
  can't show that it is missing, so none of these can be flagged.

## Cost

$23.77 in API fees: $12.37 for Claude, $10.75 for GPT-6.2 Sol and $0.65 for a short test of
GPT-5.6 Sol. Each full run took about ten minutes.

## Caveats

- The judges' seven labels had to be mapped onto the benchmark's three classes. "Not supported"
  overlaps with the benchmark's "not enough information", so part of the false alarms may come
  from that mapping.
- The 300 benchmark items come from only 20 cited sources, so the confidence intervals, which
  resample items, understate the uncertainty.

## Next

A blind hand-check of 50 English journal citations, labelled without seeing the judges'
verdicts, to measure the over-flagging directly.

Full tables: [benchmark](day3_benchmark.md) and [journal citations](day3_ojs.md).
