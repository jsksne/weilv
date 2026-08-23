# Stage 10A — Cold-start Questionnaire + User Memory Initialization

## 1. Purpose

微律 Stage 10A adds a lightweight first-use questionnaire that answers
"什么推荐更适合这个用户？" — not "这个用户有什么病？".

The questionnaire **initializes the existing User Memory system**. It does not
create a second personalization engine, does not fabricate `task_feedback`
history, and does not touch the frozen Safety / Evidence / Output Guard /
Agentic RAG / CF contracts.

Supported stages: `primary_upper`, `junior_high`, `senior_high`.

Target completion time: **60–90 seconds** (7 questions, one per screen).

## 2. Questionnaire questions and options

School stage is **not re-asked**: it already lives in the user profile
(`target_stage`), so the questionnaire only confirms it implicitly and avoids
re-collecting known data.

| # | question_id | Question (youth-friendly) | Options | Required |
|---|-------------|---------------------------|---------|----------|
| 1 | `bedtime` | 平时几点睡觉？ | `before_2130` / `2130_2230` / `2230_2330` / `after_2330` / `varies` | no |
| 2 | `screen_duration` | 一次连续学习或看屏幕，通常持续多久？ | `under_30` / `30_60` / `60_120` / `over_120` / `varies` | no |
| 3 | `rest_preference` | 学习一段时间后有点累了，你更喜欢哪种休息？ | `quiet_rest` / `far_view` / `light_activity` / `outdoor` / `depends` | yes |
| 4 | `annoying_reminders` | 哪些提醒会让你觉得有点烦？(multi) | `activity` / `stop_phone` / `long_rest` / `interrupt_study` / `none` | yes |
| 5 | `main_context` | 你大多数时候在哪里学习？ | `home` / `school` / `both` | yes |
| 6 | `leave_seat_allowed` | 上课或自习时，允许离开座位活动吗？ | `allowed` / `not_allowed` / `sometimes` | yes |
| 7 | `break_minutes` | 课间或休息，一般有多长时间？ | `under_5` / `5_10` / `10_20` / `over_20` / `varies` | yes |

The multi-select option `none` is exclusive: choosing it clears all other
choices, and choosing another option clears `none`.

## 3. Answer → memory mapping

Every generated memory record uses the existing memory persistence gate and
is stamped `source_type="questionnaire_cold_start"` so it is clearly
distinguishable from later behavioral feedback (`structured_task_feedback`).

| Answer value | Generated memory record(s) | Memory type |
|--------------|----------------------------|-------------|
| `rest_preference=quiet_rest` | prefer `MT-BREAK-003` (纯休息) | `task_preference` |
| `rest_preference=far_view` | prefer `MT-BREAK-001`, `MT-BREAK-002` (远眺) | `task_preference` |
| `rest_preference=light_activity` | prefer `MT-REC-001`, `MT-REC-002` (轻微活动) | `task_preference` |
| `rest_preference=outdoor` | prefer `MT-OUT-001` (户外休息) | `task_preference` |
| `annoying_reminders` contains `activity` | avoid `MT-REC-001`, `MT-REC-002`, `MT-SED-001`, `MT-SED-002`, `MT-BREAK-004` | `task_preference` |
| `annoying_reminders` contains `stop_phone` | avoid `MT-SLEEP-001` | `task_preference` |
| `annoying_reminders` contains `long_rest` | avoid `MT-BREAK-001`, `MT-BREAK-002`, `MT-BREAK-003` | `task_preference` |
| `annoying_reminders` contains `interrupt_study` | avoid `MT-BREAK-001`, `MT-BREAK-002`, `MT-BREAK-003`, `MT-SED-001`, `MT-OUT-001`, `MT-REC-001`, `MT-REC-002` | `task_preference` |
| `main_context=home` | `{preferred_context: home}` | `context_preference` |
| `main_context=school` | `{preferred_context: school}` | `context_preference` |
| `leave_seat_allowed=not_allowed` | avoid `MT-BREAK-004`, `MT-SED-001` | `task_preference` |
| `break_minutes=under_5` | `{preferred_max_task_minutes: 5}` | `user_constraint` |
| `break_minutes=5_10` | `{preferred_max_task_minutes: 10}` | `user_constraint` |
| `break_minutes=10_20` | `{preferred_max_task_minutes: 20}` | `user_constraint` |
| `break_minutes=over_20` | `{preferred_max_task_minutes: 30}` | `user_constraint` |

Rules that keep the mapping defensible:

- All referenced task IDs come from the **formal 23-task corpus**
  (`data/metadata/micro_tasks_v1.jsonl`); no new formal task IDs are created.
- `bedtime`, `screen_duration`, `varies`/`depends`/`both`/`allowed`/`sometimes`
  answers are stored as **provenance only** and generate no memory record when
  no mapping is defensible.
- No `task_feedback` memory is ever fabricated — the questionnaire produces
  only `task_preference`, `context_preference`, and `user_constraint` records.

## 4. Storage

- Questionnaire record: `user_questionnaire_v1` index (one document per user,
  document id = `user_id`).
- Fields: `questionnaire_id` (version `v1`), `completion_state`
  (`not_started` / `partially_completed` / `completed` / `skipped`),
  `updated_at`, `completed_at` (set on completion/skip), `answers`
  (provenance, `enabled: false` — stored but **not searchable**), and
  `memory_record_ids` (the generated memory documents).
- Generated memory records live in the existing `user_memory_v1` index through
  the existing `create_memory` / `update_memory` gate with
  `source_type="questionnaire_cold_start"`.
- No parallel profile database was introduced; the existing Elasticsearch
  user-data indices are reused.

## 5. Privacy and data-minimization rationale

- No medical, health-symptom, diagnosis, medication, or measurement data is
  collected. The questionnaire collects only lifestyle/context preferences.
- Free text is not collected anywhere; every answer is a closed enum value.
- Raw answers are stored for provenance but are not indexed (`enabled: false`),
  so they cannot be searched and never enter `retrieval_text`.
- Known data (school stage) is not re-asked.

## 6. Cold-start behavior, skip, and resume

- **Before** the questionnaire: recommendations work via Basic / current-context
  behavior exactly as before. No memory is consulted.
- **After completion**: the generated preference/context memory is immediately
  available to the frozen Personal RAG ranking mechanism.
- **Skip** (`POST .../questionnaire/skip`): stores `skipped`, generates no
  memory, and never blocks product use.
- **Resume**: saving a partial answer set stores
  `partially_completed`; memory records are upserted idempotently (stable
  memory ids), so resuming from a previous session converges to the same state.
- Users may also decline to answer optional rhythm questions; only the five
  required questions gate the `completed` state.

## 7. Safety boundaries (unchanged invariants)

Questionnaire memory can only influence ranking through the **existing frozen**
`personalize_task_candidates` mechanism. It must not — and does not:

- bypass Safety (`evaluate_input_risk` / `select_safe_tasks` run before any
  personalization and never read questionnaire memory);
- resurrect a blocked task (a task excluded by Safety never enters the
  reranked candidate list, so no memory can re-add it);
- expand the candidate set (personalization reorders only the safety-approved
  list);
- override context mismatch or duration constraints (`current_context`,
  `available_minutes` filtering still runs on the request, not on memory);
- create health advice or alter evidence binding / Output Guard.

Tests pin these invariants: `test_candidate_set_invariance_after_cold_start_memory`
and `test_blocked_task_cannot_resurrect_via_memory`.

## 8. API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/questionnaire` | questionnaire schema (questions + options) |
| GET | `/api/v1/users/{user_id}/questionnaire` | current state (defaults to `not_started`) |
| PUT | `/api/v1/users/{user_id}/questionnaire` | save answers (auto completion state) |
| POST | `/api/v1/users/{user_id}/questionnaire/skip` | mark skipped |

Malformed answers (unknown question id, invalid option value, empty answers,
`none` combined with other multi options) are rejected with 422 and never
touch storage.

## 9. Demo flow

`scripts/stage10a_demo_fixture.py` runs offline (no ES, no model keys) and shows:

- One shared request: `junior_high`, `home`, 10 minutes, "连续读写快40分钟了，想休息一下".
- **User A** (quiet rest, dislikes activity interruptions, seat restricted):
  top pick moves to `MT-BREAK-003` (纯休息).
- **User B** (light activity / outdoor preference, no annoying reminders):
  keeps `MT-BREAK-001` at the top.
- The **safe candidate set is identical** (22 tasks) for both users and no
  Safety rule outcome changes.

This is a product/demo verification fixture, not a formal research result.

## 10. Tests

Backend: `tests/test_questionnaire.py` (completion, skip, resume, valid stage
mapping, preference/constraint mapping, no fake task_feedback, candidate-set
invariance, blocked-task non-resurrection, malformed/partial fail-safe,
provenance, existing-users-without-questionnaire, API contracts).

Frontend: `frontend/src/questionnaire-flow.test.ts` (completion flow, skip,
back navigation, multi-select `none` exclusivity, resume).

The existing Personal RAG / Safety / memory persistence regression suites
continue to pass unmodified (see test run output in the acceptance bundle).
