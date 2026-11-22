# Citation-Integrity benchmark results

## claude-opus-5-5

- Judged: 300 ({'ok': 250, 'fallback': 50}); spent $6.96.
- Quotes found verbatim in the source: 580 of 580.
- Answered by a fallback model and left out: 50 items, from 6 of the 20 cited sources (19, 16, 8, 5, 1, 1 items each), so the scores below do not cover those sources evenly.

### Model label

- Items: 250; accuracy (micro-F1) 0.62; macro-F1 0.45 (95% CI 0.38–0.52). Published best system: micro-F1 0.59, macro-F1 0.52.

| Gold \ predicted | ACCURATE | NOT_ACCURATE | NEI | Recall | F1 |
|---|---|---|---|---|---|
| ACCURATE | 130 | 23 | 2 | 0.84 | 0.79 |
| NOT_ACCURATE | 23 | 20 | 0 | 0.47 | 0.36 |
| NEI | 22 | 24 | 6 | 0.12 | 0.20 |

Precision: ACCURATE 0.74, NOT_ACCURATE 0.30, NEI 0.75

### After publication rules

- Items: 250; accuracy (micro-F1) 0.63; macro-F1 0.46 (95% CI 0.39–0.53). Published best system: micro-F1 0.59, macro-F1 0.52.

| Gold \ predicted | ACCURATE | NOT_ACCURATE | NEI | Recall | F1 |
|---|---|---|---|---|---|
| ACCURATE | 130 | 23 | 2 | 0.84 | 0.79 |
| NOT_ACCURATE | 23 | 20 | 0 | 0.47 | 0.37 |
| NEI | 22 | 23 | 7 | 0.13 | 0.23 |

Precision: ACCURATE 0.74, NOT_ACCURATE 0.30, NEI 0.78

#### claude-opus-5-5: precision by label

| Label | Given | Experts: ACCURATE | NOT_ACCURATE | NEI | Precision |
|---|---|---|---|---|---|
| supported | 175 | 130 | 23 | 22 | 0.74 |
| partly_supported | 54 | 22 | 17 | 15 | 0.31 |
| misquoted_number | 1 | 1 | 0 | 0 | 0.00 |
| not_supported | 9 | 0 | 1 | 8 | 0.11 |
| contradicted | 2 | 0 | 2 | 0 | 1.00 |
| unrelated | 3 | 0 | 0 | 3 | 1.00 |
| cannot_judge | 6 | 2 | 0 | 4 | 0.67 |

## gpt-6.2-sol

- Judged: 300 ({'ok': 300}); spent $8.69.
- Quotes found verbatim in the source: 618 of 618.

### Model label

- Items: 300; accuracy (micro-F1) 0.47; macro-F1 0.35 (95% CI 0.31–0.40). Published best system: micro-F1 0.59, macro-F1 0.52.

| Gold \ predicted | ACCURATE | NOT_ACCURATE | NEI | Recall | F1 |
|---|---|---|---|---|---|
| ACCURATE | 103 | 74 | 2 | 0.58 | 0.67 |
| NOT_ACCURATE | 16 | 37 | 0 | 0.70 | 0.34 |
| NEI | 10 | 56 | 2 | 0.03 | 0.06 |

Precision: ACCURATE 0.80, NOT_ACCURATE 0.22, NEI 0.50

### After publication rules

- Items: 300; accuracy (micro-F1) 0.48; macro-F1 0.37 (95% CI 0.32–0.42). Published best system: micro-F1 0.59, macro-F1 0.52.

| Gold \ predicted | ACCURATE | NOT_ACCURATE | NEI | Recall | F1 |
|---|---|---|---|---|---|
| ACCURATE | 103 | 71 | 5 | 0.58 | 0.67 |
| NOT_ACCURATE | 16 | 36 | 1 | 0.68 | 0.34 |
| NEI | 10 | 54 | 4 | 0.06 | 0.10 |

Precision: ACCURATE 0.80, NOT_ACCURATE 0.22, NEI 0.40

#### gpt-6.2-sol: precision by label

| Label | Given | Experts: ACCURATE | NOT_ACCURATE | NEI | Precision |
|---|---|---|---|---|---|
| supported | 129 | 103 | 16 | 10 | 0.80 |
| partly_supported | 136 | 67 | 30 | 39 | 0.22 |
| misquoted_number | 1 | 1 | 0 | 0 | 0.00 |
| not_supported | 23 | 3 | 5 | 15 | 0.22 |
| contradicted | 1 | 0 | 1 | 0 | 1.00 |
| unrelated | 1 | 0 | 0 | 1 | 1.00 |
| cannot_judge | 9 | 5 | 1 | 3 | 0.33 |

## Both judges: claude-opus-5-5 and gpt-6.2-sol

- Items both judged: 250. The judges agree with each other on 70% of them (Cohen's kappa 0.47; three classes, after the publication rules).
- Rule: support only when both say supported; a negative only when both give one (the milder if they differ); otherwise cannot judge.
- Each judge is also scored on these shared items alone, so that items one judge lost to a refusal or fallback do not tilt the comparison.

### Two-judge rule

- Items: 250; accuracy (micro-F1) 0.50; macro-F1 0.45 (95% CI 0.39–0.51). Published best system: micro-F1 0.59, macro-F1 0.52.

| Gold \ predicted | ACCURATE | NOT_ACCURATE | NEI | Recall | F1 |
|---|---|---|---|---|---|
| ACCURATE | 84 | 23 | 48 | 0.54 | 0.65 |
| NOT_ACCURATE | 13 | 20 | 10 | 0.47 | 0.37 |
| NEI | 7 | 23 | 22 | 0.42 | 0.33 |

Precision: ACCURATE 0.81, NOT_ACCURATE 0.30, NEI 0.28

#### Two-judge rule: precision by label

| Label | Given | Experts: ACCURATE | NOT_ACCURATE | NEI | Precision |
|---|---|---|---|---|---|
| supported | 104 | 84 | 13 | 7 | 0.81 |
| partly_supported | 56 | 22 | 18 | 16 | 0.32 |
| misquoted_number | 1 | 1 | 0 | 0 | 0.00 |
| not_supported | 8 | 0 | 1 | 7 | 0.12 |
| contradicted | 1 | 0 | 1 | 0 | 1.00 |
| unrelated | 1 | 0 | 0 | 1 | 1.00 |
| cannot_judge | 79 | 48 | 10 | 21 | 0.27 |

### claude-opus-5-5 on the shared items

- Items: 250; accuracy (micro-F1) 0.63; macro-F1 0.46 (95% CI 0.39–0.52). Published best system: micro-F1 0.59, macro-F1 0.52.

| Gold \ predicted | ACCURATE | NOT_ACCURATE | NEI | Recall | F1 |
|---|---|---|---|---|---|
| ACCURATE | 130 | 23 | 2 | 0.84 | 0.79 |
| NOT_ACCURATE | 23 | 20 | 0 | 0.47 | 0.37 |
| NEI | 22 | 23 | 7 | 0.13 | 0.23 |

Precision: ACCURATE 0.74, NOT_ACCURATE 0.30, NEI 0.78

### gpt-6.2-sol on the shared items

- Items: 250; accuracy (micro-F1) 0.47; macro-F1 0.37 (95% CI 0.31–0.43). Published best system: micro-F1 0.59, macro-F1 0.52.

| Gold \ predicted | ACCURATE | NOT_ACCURATE | NEI | Recall | F1 |
|---|---|---|---|---|---|
| ACCURATE | 84 | 66 | 5 | 0.54 | 0.65 |
| NOT_ACCURATE | 13 | 30 | 0 | 0.70 | 0.33 |
| NEI | 7 | 41 | 4 | 0.08 | 0.13 |

Precision: ACCURATE 0.81, NOT_ACCURATE 0.22, NEI 0.44

