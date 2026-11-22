# Citation-Integrity benchmark results

## claude-opus-5-5

- Judged: 10 ({'ok': 9, 'fallback': 1}); spent $0.71.
- Quotes found verbatim in the source: 21 of 21.

### Model label

- Items: 9; accuracy (micro-F1) 0.78; macro-F1 0.69 (95% CI 0.29–1.00). Published best system: micro-F1 0.59, macro-F1 0.52.

| Gold \ predicted | ACCURATE | NOT_ACCURATE | NEI | Recall | F1 |
|---|---|---|---|---|---|
| ACCURATE | 5 | 0 | 0 | 1.00 | 0.91 |
| NOT_ACCURATE | 1 | 1 | 0 | 0.50 | 0.50 |
| NEI | 0 | 1 | 1 | 0.50 | 0.67 |

Precision: ACCURATE 0.83, NOT_ACCURATE 0.50, NEI 1.00

### After publication rules

- Items: 9; accuracy (micro-F1) 0.78; macro-F1 0.69 (95% CI 0.29–1.00). Published best system: micro-F1 0.59, macro-F1 0.52.

| Gold \ predicted | ACCURATE | NOT_ACCURATE | NEI | Recall | F1 |
|---|---|---|---|---|---|
| ACCURATE | 5 | 0 | 0 | 1.00 | 0.91 |
| NOT_ACCURATE | 1 | 1 | 0 | 0.50 | 0.50 |
| NEI | 0 | 1 | 1 | 0.50 | 0.67 |

Precision: ACCURATE 0.83, NOT_ACCURATE 0.50, NEI 1.00

## gpt-5.6-sol

- Judged: 10 ({'ok': 10}); spent $0.65.
- Quotes found verbatim in the source: 26 of 26.

### Model label

- Items: 10; accuracy (micro-F1) 0.70; macro-F1 0.45 (95% CI 0.22–0.65). Published best system: micro-F1 0.59, macro-F1 0.52.

| Gold \ predicted | ACCURATE | NOT_ACCURATE | NEI | Recall | F1 |
|---|---|---|---|---|---|
| ACCURATE | 6 | 0 | 0 | 1.00 | 0.86 |
| NOT_ACCURATE | 1 | 1 | 0 | 0.50 | 0.50 |
| NEI | 1 | 1 | 0 | 0.00 | 0.00 |

Precision: ACCURATE 0.75, NOT_ACCURATE 0.50, NEI 0.00

### After publication rules

- Items: 10; accuracy (micro-F1) 0.70; macro-F1 0.45 (95% CI 0.24–0.65). Published best system: micro-F1 0.59, macro-F1 0.52.

| Gold \ predicted | ACCURATE | NOT_ACCURATE | NEI | Recall | F1 |
|---|---|---|---|---|---|
| ACCURATE | 6 | 0 | 0 | 1.00 | 0.86 |
| NOT_ACCURATE | 1 | 1 | 0 | 0.50 | 0.50 |
| NEI | 1 | 1 | 0 | 0.00 | 0.00 |

Precision: ACCURATE 0.75, NOT_ACCURATE 0.50, NEI 0.00

## Both judges: claude-opus-5-5 and gpt-5.6-sol

- Items both judged: 9. The judges agree with each other on 89% of them (Cohen's kappa 0.74; three classes, after the publication rules).
- Rule: support only when both say supported; a negative only when both give one (the milder if they differ); otherwise cannot judge.
- Each judge is also scored on these shared items alone, so that items one judge lost to a refusal or fallback do not tilt the comparison.

### Two-judge rule

- Items: 9; accuracy (micro-F1) 0.78; macro-F1 0.69 (95% CI 0.28–1.00). Published best system: micro-F1 0.59, macro-F1 0.52.

| Gold \ predicted | ACCURATE | NOT_ACCURATE | NEI | Recall | F1 |
|---|---|---|---|---|---|
| ACCURATE | 5 | 0 | 0 | 1.00 | 0.91 |
| NOT_ACCURATE | 1 | 1 | 0 | 0.50 | 0.50 |
| NEI | 0 | 1 | 1 | 0.50 | 0.67 |

Precision: ACCURATE 0.83, NOT_ACCURATE 0.50, NEI 1.00

### claude-opus-5-5 on the shared items

- Items: 9; accuracy (micro-F1) 0.78; macro-F1 0.69 (95% CI 0.29–1.00). Published best system: micro-F1 0.59, macro-F1 0.52.

| Gold \ predicted | ACCURATE | NOT_ACCURATE | NEI | Recall | F1 |
|---|---|---|---|---|---|
| ACCURATE | 5 | 0 | 0 | 1.00 | 0.91 |
| NOT_ACCURATE | 1 | 1 | 0 | 0.50 | 0.50 |
| NEI | 0 | 1 | 1 | 0.50 | 0.67 |

Precision: ACCURATE 0.83, NOT_ACCURATE 0.50, NEI 1.00

### gpt-5.6-sol on the shared items

- Items: 9; accuracy (micro-F1) 0.67; macro-F1 0.44 (95% CI 0.20–0.64). Published best system: micro-F1 0.59, macro-F1 0.52.

| Gold \ predicted | ACCURATE | NOT_ACCURATE | NEI | Recall | F1 |
|---|---|---|---|---|---|
| ACCURATE | 5 | 0 | 0 | 1.00 | 0.83 |
| NOT_ACCURATE | 1 | 1 | 0 | 0.50 | 0.50 |
| NEI | 1 | 1 | 0 | 0.00 | 0.00 |

Precision: ACCURATE 0.71, NOT_ACCURATE 0.50, NEI 0.00

