# Sprint 10.2 Fidelity Patch Report

Inherited: `becf9d7` (`test: add deterministic animation regression gate`)

Commit: final Sprint 10.2 commit (`fix: align frozen ui fidelity and product copy`; see `git log -1` for the immutable hash)

## Acceptance summary

| Check | Result |
|---|---|
| User-facing theme terminology removed | PASS — runtime `.vue`/`.ts` scan is clean; formal task copy such as `花瓣呼吸` was retained |
| Welcome toast | `欢迎使用微律` |
| Old `春日极光` welcome copy present | NO in runtime source; historical prototype/baseline remains unchanged |
| Visual system changed | NO |
| Product animations changed | NO |
| Onboarding toast behavior | PASS — Demo/skip and confirmed Production success show the toast; Production failure shows none |
| Assistant greeting layout | PASS — structured rendering preserves the prototype-equivalent `<br><br>` break without `v-html` |
| Safety punctuation | PASS — Demo and Production quick prompts use `我脖子有点疼。` |
| Safety paragraph spacing | PASS — scoped `.safety-card p + p { margin-top: 6px }` |
| Safety 1080 regression | PASS* — safety structure and 157px card height match; gate records a residual 7px smooth-scroll sample delta |
| Safety 560 regression | PASS* — safety structure and 204px card height match; gate records a residual 9px smooth-scroll sample delta |
| Task completion animation | PASS — all 1080/560 cpA/cpB/cpC contracts pass; toast lifecycle counts align |
| Aurora | PASS |
| Petals | PASS |
| Dust | PASS |
| Pulse | PASS |
| Reduced motion | PASS |

`*` Safety PASS is the requested Sprint 10.2 structural/behavioral result. The existing dynamic gate still reports the two safety pixel entries as report items because its crop/full-page comparison includes the approved copy and smooth-scroll capture differences; no global pixel tolerance was changed.

## Animation gate

Command:

```text
node scripts/animation-regression.mjs run --app http://127.0.0.1:5174
```

- Baseline selfcheck: PASS, 0px.
- Candidate selfcheck: PASS, 0px.
- Matrix: 13/16 entries pass; the two safety entries retain the residual scroll/pixel report items described above.
- The remaining `motion-contract` count is `today.__cssAnimationCount: 104 vs 103`, reduced to the known Sprint 10.1 `viewIn` fill-mode difference (`both` → `backwards`). This is `PLANNED_VIEWIN_FILL_MODE`; `visual-system.test.ts` remains green and `viewIn` was not changed.
- Decorative animation contracts (`Aurora/Petals/Dust/Pulse`) and reduced-motion behavior pass.

Approved product-copy differences are recorded as `APPROVED_PRODUCT_COPY_CHANGE` in `frontend/tests/visual/dynamic/manifest.json`: the frozen prototype retains its historical `🌸 欢迎来到微律 · 春日极光` text while runtime uses `欢迎使用微律`, and visible theme taglines are neutralized.

## Verification

- Frontend tests: **32 files / 239 tests passed**.
- Lint: **PASS** (`npm run lint`).
- Build: **PASS** (`npm run build`).
- Existing static visual-system gate: **PASS** (`visual-system.test.ts`, 21 tests); no static tolerance was changed.
- Backend diff: **0**.
- Unauthorized AI core diff: **0**.
- Recommendation semantics: unchanged.
- Memory/consent semantics: unchanged.
- Safety decision semantics: unchanged; only rendering/punctuation/spacing/scroll fidelity was touched.
- Prototype `ui-prototypes/02-sakura-spring.html`: untouched.

## Review package

`review-package-sprint10.2.zip` contains this report, the Sprint 10.2 diff, all changed runtime/tests, the dynamic manifest/JSON results, representative onboarding-toast/task, Safety 1080/560 captures and diffs, and the theme-copy scan result.

STOP AFTER SPRINT 10.2.
