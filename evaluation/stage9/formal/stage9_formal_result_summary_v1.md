# Stage 9 Formal Result Summary (v1)

Derived summary of the Stage 9 formal external CF run. No new analyses; all
numbers are transcribed as-is from the immutable run artifacts.

## Run identity

- Formal attempt: **2** (attempt 1 = FAILED_PRE_COMPUTATION, Stage 9C.1 repair)
- Freeze manifest: `stage9_evaluator_freeze_manifest_v3.json`
- Run directory: `evaluation/runs/20260819T103447Z_stage9_formal/`
- Exit code: 0; formal completed: true

## Data source

- HeartSteps V1, pinned commit `3016391de426116bdef41880d72bc8cd4b9b2477`
- 4/4 source file hashes verified PASS (users.csv, suggestions.csv, gfsteps.csv, jbsteps.csv)

## Cohort

- Raw suggestions rows: 8274
- Final public-release primary cohort rows: 5905 (frozen eligibility rules R1-R8)
- Participants: **37**
- Evaluation decision rows (days 8-42): 4878

## Policies

- Comparator: `EXTERNAL_PERSONAL_HISTORY` (HeartSteps target-user history; NOT 微律 Personal RAG)
- Method: `EXTERNAL_PERSONAL_PLUS_CF`

## Primary outcome

- `y = ln(jbsteps30.zero + 0.5)` (primary); complete-case and Google Fit sensitivities reported per participant in the run artifacts.

## Protocols

- **LOPO**: 37-fold leave-one-participant-out; held-out participant never in source fitting or neighbor construction.
- **SNIPS**: `w_t = I(A_t == pi(X_t)) / p(A_t | X_t)`; p(none)=0.4, p(walking)=0.3, p(antisedentary)=0.3; `V_u = sum(w*y)/sum(w)`; `ESS_u = (sum w)^2 / sum(w^2)`.
- Days 1-7 adaptation history; days 8-42 evaluation. Strict pre-prediction temporal censoring.

## Primary result (as-is)

- `EXTERNAL_PERSONAL_HISTORY` (mean participant SNIPS value): **2.972586980742795**
- `EXTERNAL_PERSONAL_PLUS_CF` (mean participant SNIPS value): **2.982641393385160**
- **Delta_V**: **0.01005441264236447**
- 95% participant-bootstrap CI: **[-0.08176908093327724, 0.09949781128525453]**
- Bootstrap replicates: **10000**; seed: **20260818**
- Zero-support participants: **0** (all 37 participants have positive denominator/ESS for both policies)

## ESS summary (participant-level)

- Comparator (`EXTERNAL_PERSONAL_HISTORY`): min 18.63, max 62.97, mean 42.81
- Method (`EXTERNAL_PERSONAL_PLUS_CF`): min 18.78, max 66.65, mean 42.70
- Both policies: ESS > 0 for every participant.

## Paired participant-level Delta distribution

- Wins (Delta_u > 0): **15**; Ties (Delta_u == 0): **0**; Losses (Delta_u < 0): **22**

## Leakage

- Held-out user in source: **0**
- Future target history: **0**
- Future source rows: **0**
- Post-response features: **0**
- Integrity gates: PASS (hashes PASS, duplicates 0, schema_ok true)

## Claim result

- **CR-CF-001: UNSUPPORTED**
- Reason: `bootstrap_ci_lower_not_greater_than_zero` (Delta_V > 0 but the
  participant-bootstrap 95% CI lower bound <= 0)

## Secondary sensitivity (frozen AM-001, is.randomized == True)

- Reported separately by the frozen evaluator (per-participant `randtrue_*` columns).
- Mean participant-level Delta (randtrue rows): **0.07497353891583505** (37 participants).
- Does NOT alter the primary Delta_V, primary CI, or CR-CF-001.

## Claim boundaries

- This run does NOT claim HeartSteps proves 微律 Personal RAG effectiveness,
  youth effectiveness, long-term health improvement, 35-day deployment value,
  or causal effectiveness of deploying 微律 CF.
- Interpretation is limited to: **ONE-STEP CONTEXTUAL OFF-POLICY VALUE UNDER
  THE RANDOMIZED LOGGED-HISTORY DISTRIBUTION** within the HeartSteps adult
  action space.
- CR-CF-004 remains NOT_EVALUATED; CR-CF-REAL-001 remains UNSUPPORTED.
