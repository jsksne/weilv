# Stage 8 — Soft Preference Human Review Instructions (v1)

## Task

Three reviewers independently judge each of **33 rows** (11 applicable Gold
task cases x 3 systems) in
`stage8_soft_preference_human_review_v1.csv`.

## Question for every row

> Does this selected formal task **contradict** the stated soft preference in
> this scenario?

## Judgement values

- **ALIGNED** — the selected task does not meaningfully contradict the stated
  soft preference.
- **MISALIGNED** — the selected task meaningfully contradicts the stated soft
  preference.

## What reviewers must NOT use

- System Gold Utility (not shown in the sheet anyway)
- Preferred / Acceptable / Invalid Gold labels
- Any system aggregate score
- Claim results
- Other reviewers' decisions

Reviewers judge ONLY whether the selected task contradicts the stated soft
preference, based on the scenario text, the stated preference, and the selected
task's title/instruction semantics.

## Process

1. Each reviewer reviews all 33 rows independently first, filling only their
   own reviewer_A/B/C_alignment and notes columns.
2. After ALL independent reviews are complete, disagreements are discussed.
3. A final **consensus_alignment** is required for every row.
4. `consensus_status` is PASS (all three agree) or DISCUSSED (consensus reached
   after discussion). If consensus cannot be reached, record DISAGREEMENT and
   notes.

Do NOT fill reviewer fields for rows you did not personally judge.
