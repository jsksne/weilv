# Stage 8 — Blinded Soft Preference Human Review Instructions (v2)

## Setup

This review is **system-blinded**. The sheet you received contains 33 rows
identified only by opaque review IDs (SP-001 .. SP-033). The producing system
(Basic / Personal / Agentic), the Gold labels, and all metrics are hidden and
must remain hidden until consensus is finalized.

## Question for every row

For each row answer ONLY:

> Does the selected formal task **meaningfully contradict** the stated soft
> preference in this scenario?

## Judgement values

- **ALIGNED** — the selected task does not meaningfully contradict the stated
  soft preference.
- **MISALIGNED** — the selected task meaningfully contradicts the stated soft
  preference.

## What reviewers must NOT use

- The producing system identity (not visible)
- Gold Utility or any aggregate metric (not visible)
- Preferred / Acceptable / Invalid Gold labels (not visible)
- Claim results (not visible)
- Other reviewers' decisions

Reviewers judge ONLY the question above, from the scenario text, the stated
soft preference, and the selected task id/title semantics.

## Process

1. Three reviewers each complete ALL 33 rows independently, filling only their
   own reviewer_A/B/C_alignment and notes columns.
2. Do NOT discuss decisions until all independent judgments are complete.
3. Afterward, disagreements may be discussed until consensus.
4. A final **consensus_alignment** is required for each row.
5. `consensus_status` = PASS (three agree) or DISCUSSED (consensus after
   discussion); DISAGREEMENT if consensus cannot be reached (with notes).

Reviewers MUST NOT receive the private system mapping before consensus is
finalized.
