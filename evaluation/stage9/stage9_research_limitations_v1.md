# Stage 9A research limitations v1

1. **Population mismatch.** HeartSteps analyzed 37 healthy sedentary adults aged 18–60. 微律 targets grades 4–12. Adult response cannot establish youth acceptability, adherence, safety, or health effectiveness.
2. **Action mismatch.** HeartSteps has no stable versions of 微律's 23 tasks. It supports walking and antisedentary archetypes only. Exact task triggers, duration, evidence, and wording are not validated.
3. **Outcome mismatch.** Thirty-minute steps are a proximal activity response, not completion, preference, sustained behavior change, learning performance, eye health, sleep, or clinical benefit.
4. **Tiny stable item space.** Two intervention types plus no suggestion make matrix factorization/BPR inappropriate; the selected neighbor mechanism operates on coarse action x slot cells.
5. **Small independent N.** Thousands of decisions come from 37 people. Repeated rows do not create thousands of independent participants. All inference is participant-level and remains low power.
6. **Missingness/non-wear.** Jawbone/phone observations are incomplete. Official `.zero` fields can conflate missing/non-wear/travel with inactivity and are sensitivity-only.
7. **Public/paper row mismatch.** The release exposes 8,274 rows, while the paper's analytic exclusions yield 7,540 included and 6,061 available decision points. Public operational fields are nonblank on 7,539 rows. Stage 9B must publish its own row-flow rather than claim exact reconstruction.
8. **Context measurement error.** Phone activity recognition, location category, weather lookup, connectivity, and prefetch context can be stale or inaccurate. Context buckets reduce, not eliminate, this error.
9. **Rating ambiguity.** `good`/`bad` are message ratings; `no_response` and blanks are not negative preference. Completion is unobserved.
10. **Offline policy uncertainty.** SNIPS uses known randomization probabilities but may be variable with only 37 users. Effective sample size and action overlap must be reported; a positive point estimate without a participant-level CI lower bound above zero does not support CR-CF-001.
11. **Warm-start scope.** The primary test allows seven days of target history. It does not prove cold-start value. The frozen product behavior for cold start is neutral CF.
12. **No direct product validation.** External mechanism success would not support CR-CF-004. Only a consented, appropriately governed 微律 real-user pilot with exact formal task interactions can evaluate incremental value beyond Personal RAG.
13. **StudentLife limitation.** StudentLife is context-rich and student-focused but lacks repeated recommendation exposure/action-response records. Its official page did not expose an explicit standalone dataset license during this audit. It is secondary-only.
14. **Engineering evidence is not human evidence.** Synthetic adapter tests can establish candidate invariance, fallback, privacy, and safety wiring only.
15. **No Stage 9 result yet.** This ticket selects methods and claims before observation; it does not train a model, calculate a formal metric, or establish improvement.

Required cautious wording:

> HeartSteps is suitable for a bounded external test of cross-user behavioral action ranking in its own adult physical-activity setting. Product-level effectiveness, youth generalization, and exact 微律 task benefit remain untested and require a separate real-user pilot.
