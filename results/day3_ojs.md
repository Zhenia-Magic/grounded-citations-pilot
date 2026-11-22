# Day 3: what two judges said about 157 OJS citations

Judges: claude-opus-5-5 and gpt-6.2-sol, with the same prompt, output schema and publication rules. Labels are after those rules. The two-judge rule gives the label a note would carry: support only when both judges say supported, a negative only when both give one, otherwise cannot judge.

## Runs

| Judge | ok | refusal | fallback | error | missing | Quotes found in the source | Cost |
|---|---|---|---|---|---|---|---|
| claude-opus-5-5 | 157 | 0 | 0 | 0 | 0 | 323 of 323 | $5.42 |
| gpt-6.2-sol | 157 | 0 | 0 | 0 | 0 | 265 of 265 | $2.05 |

## Labels

| | Citations | supported | negative | unrelated | cannot judge |
|---|---|---|---|---|---|
| claude-opus-5-5 | 157 | 66 (42%) | 26 (17%) | 1 (1%) | 64 (41%) |
| gpt-6.2-sol | 157 | 33 (21%) | 38 (24%) | 0 (0%) | 86 (55%) |
| Two-judge rule | 157 | 33 (21%) | 24 (15%) | 0 (0%) | 100 (64%) |

Two-judge rule by evidence and by language stratum:

| | Citations | supported | negative | unrelated | cannot judge |
|---|---|---|---|---|---|
| Full text | 66 | 21 (32%) | 24 (36%) | 0 (0%) | 21 (32%) |
| Abstract only | 91 | 12 (13%) | 0 (0%) | 0 (0%) | 79 (87%) |
| English stratum | 139 | 28 (20%) | 22 (16%) | 0 (0%) | 89 (64%) |
| Spanish stratum | 18 | 5 (28%) | 2 (11%) | 0 (0%) | 11 (61%) |

## Agreement between the judges

- Same label group on 76% of the 157 citations both judged (Cohen's kappa 0.64 over the four groups).
- Negative labels: 26 from claude-opus-5-5, 38 from gpt-6.2-sol, 24 from both, which is what the two-judge rule keeps.
- Abstract-only evidence can never yield a negative label: the publication rules turn it into cannot judge.

## Day-4 hand-check kit

50 English citations in data/day4/: 22 negative under the two-judge rule; 8 negative by one judge only; 5 other disagreement; 15 supported by both judges.
The sheet and item files show the evidence the judges saw, without their labels. Label every item in handcheck_sheet.csv, with the minutes each took, before opening handcheck_key.csv.
