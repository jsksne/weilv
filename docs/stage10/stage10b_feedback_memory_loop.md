# Stage 10B — User Feedback Loop + Memory Evolution

## 1. Purpose

Stage 10B completes the recommendation loop:

```
推荐微任务 → 用户执行 → 反馈 → 结构化记忆更新 → 影响后续个性化
```

Feedback writes **only** into the existing User Memory system. Safety rules,
Evidence Guard, Output Guard, Basic RAG, Agentic ranking, the CF evaluator,
and all Stage 9 experiment artifacts are untouched.

## 2. Feedback schema (API)

`POST /api/v1/users/{user_id}/recommendations/{recommendation_id}/feedback`

| Field | Values | Required | Notes |
|-------|--------|----------|-------|
| `completion_status` | `completed` / `skipped` / `partially_completed` | yes | 是否完成了推荐任务 |
| `usefulness` | `helpful` / `neutral` / `not_helpful` | yes | 帮助程度 |
| `difficulty` | `easy` / `suitable` / `difficult` | yes | 难度感受 |
| `reason` | 自由文本，≤100 字符 | no | 可选，仅作留档，**不写入记忆** |

No health or medical information is collected. The optional reason is stored
in the interaction log (`reason` mapping is `index: false`) and never enters
memory `retrieval_text`.

Response adds `memory_id` and `confidence` for observability.

## 3. Memory writeback

Each feedback event upserts **one** `task_feedback` memory document per
(user, task) — memory ids are deterministic, so repeated feedback never grows
storage. Every generated memory record carries:

- `source_type`: `structured_task_feedback`
- `created_at` / `updated_at`: timestamp
- `task_id`
- `memory_value.confidence`

To keep the frozen Personal RAG ranking working, the 3-level model is mapped
onto the fields the frozen ranking already reads:

| Feedback | Memory value field | Mapping |
|----------|--------------------|---------|
| `usefulness=helpful` | `helpfulness` | 5 |
| `usefulness=neutral` | `helpfulness` | 3 |
| `usefulness=not_helpful` | `helpfulness` | 2 |
| `difficulty=easy` | `burden` | `easy` |
| `difficulty=suitable` | `burden` | `acceptable` |
| `difficulty=difficult` | `burden` | `hard` |

Memory types used: `task_feedback` (primary). No fake `task_preference` or
`context_preference` is fabricated from feedback.

## 4. Confidence accumulation

Confidence lives on the single per-task `task_feedback` document
(`memory_value.confidence`, int 1..10).

- First feedback for a task: confidence = **1** (low).
- Repeated **consistent** feedback (same helpful / not-helpful polarity):
  confidence += 1, capped at 10.
- **Contradictory** feedback (polarity flips): confidence -= 1, floored at 1.
- Neutral signals leave confidence unchanged.

This is metadata on the frozen memory document; it does not change the frozen
ranking weights.

## 5. Priority rules

Behavior feedback takes priority over the initial questionnaire preference
simply through the frozen ranking arithmetic:

- Questionnaire `task_preference prefer_task` contributes `+3` to a task.
- One negative feedback event (`skipped` + `not_helpful` + `difficult`)
  contributes `-4` via `task_feedback` (`skipped` −1, `helpfulness≤2` −2,
  `burden=hard` −1).
- `+3 + (−4) = −1` → the task's adjusted rank flips from boosted to penalized,
  so one (or repeated) behavior feedback outweighs the weak cold-start
  preference without overwriting the questionnaire record.

`questionnaire_cold_start` memory is **never** deleted or overwritten; both
records coexist and the frozen mechanism combines their deltas.

## 6. Safety boundary

Feedback memory can only affect ranking among already-safety-approved
candidates. It must not — and does not:

- resurrect blocked tasks (Safety runs before personalization; a task excluded
  by `SR-*` never appears in the candidate list, so no memory can re-add it);
- bypass Safety or expand the candidate set;
- modify evidence binding or the Output Guard;
- override `current_context` / `available_minutes` constraints.

Pinned by `test_blocked_task_cannot_return_via_positive_feedback` and
`test_candidate_set_invariance_with_feedback_memory`.

## 7. UI

The feedback card appears after an allowed recommendation:

- 完成情况: 完成了 / 部分完成 / 没做
- 「这个建议有帮助吗？」 👍 有帮助 / 😐 一般 / 👎 不适合
- 难度如何: 很轻松 / 刚刚好 / 有点难
- 想说的话（可选）: 一行输入框

Deliberately minimal — no streaks, badges, or gamification overload.

## 8. Privacy considerations

- Only the structured enums are persisted to memory; the optional free-text
  reason is stored in the interaction log with `index: false` (stored but not
  searchable) and is never included in `retrieval_text`.
- No health, diagnosis, medication, or measurement data is collected.
- User isolation is enforced by the memory identity key (user_id is part of
  every memory id) and the existing owner checks.

## 9. Demo flow

`scripts/stage10b_feedback_loop_demo.py` runs offline (no ES, no model keys):

- Same request: `junior_high`, `home`, 10 minutes.
- **User A** feedback: likes quiet rest, dislikes movement tasks → top pick
  `MT-BREAK-003`.
- **User B** feedback: likes movement, dislikes quiet rest → top pick stays
  `MT-BREAK-001` with movement tasks boosted.
- Safe candidate set (22 tasks) identical; all Safety outcomes unchanged.

This is a product/demo verification fixture, not a formal research result.

## 10. Tests

Backend `tests/test_feedback_loop.py` covers: feedback save, provenance,
questionnaire preservation, feedback-overrides-weak-preference,
contradictory-confidence decay, user isolation, candidate invariance, blocked
task non-return, malformed fail-safe, and ranking change after repeated
feedback. The existing Personal RAG / Safety / memory / Stage 10A suites
continue to pass. Frontend `feedback-flow.test.ts` covers the new card
(helpfulness emoji row, difficulty, optional reason).
