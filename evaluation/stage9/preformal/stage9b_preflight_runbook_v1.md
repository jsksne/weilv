# Stage 9B pre-flight runbook (data-dependent steps)

Status: **AWAITING PINNED HEARTSTEPS DATA** — all implementation, tests, and
data-independent pre-formal artifacts are complete.  The four steps below run
once the pinned files are available locally.  No `--formal` flag is ever used
in this ticket.

## 0. Place the pinned source files

Copy from HeartSteps V1 commit
`3016391de426116bdef41880d72bc8cd4b9b2477` (`data_files/`):

| File | Expected SHA-256 |
|---|---|
| `users.csv` | `b07d93573b014e0ae1da822c616e9e811551ad77dc8390fb52a03202f7df0ed1` |
| `suggestions.csv` | `60ee7896183d7084a084f9a6e8ef2d0afea2e7fecdb41d6b15382ce1745c5ddb` |
| `gfsteps.csv` | `1c65688ef3ee6cb973ffa089b375947edb832166b00ccb3112fafe2ef72f956c` |
| `jbsteps.csv` | `bd4a2104037514d8a818465ad483218b56f6c2cd78d57a6643818715aebd77e3` |

into `.runtime/stage9_heartsteps/` (temporary/cache only — never vendored,
never in the acceptance bundle).

## 1. Real-data preflight (PRECHECK only)

```
.venv\Scripts\python.exe evaluation\runners\_stage9b_preflight.py
```

This verifies all pinned hashes, runs the frozen preprocessor (emits
`preprocessing_flow_v1.json`, `preprocessing_flow_by_user_v1.csv`,
`stage9_public_release_exclusion_rules_v1.json`), and runs the runner's
PRECHECK (emits `stage9_leakage_test_report_v1.json`).  It never computes
Delta_V / CI / CR-CF-001 and never executes the model on the real cohort.

## 2. Regenerate data-independent artifacts + acceptance ZIP

```
.venv\Scripts\python.exe evaluation\runners\_stage9b_preformal_bundle.py
```

Recomputes test counts, regenerates the freeze manifest / integrity /
contract-report / test-report artifacts, and builds
`evaluation/stage9b_preformal_implementation_acceptance_bundle.zip` with its
SHA-256 (printed; also written to
`preformal/stage9_acceptance_bundle_sha256_v1.txt`).

## 3. Gate review

- All frozen hashes PASS.
- 37 users PASS.
- Formal result executed: NO.
- Leakage structure violations: 0.
- No file in the bundle is a raw HeartSteps CSV, `.env`, key, secret, or
  dependency folder.

Then report `READY_FOR_PREFORMAL_CODE_AUDIT` (or `BLOCKED` with the exact
reason).  The formal `--formal` run stays CLOSED until an independent audit of
this implementation.
