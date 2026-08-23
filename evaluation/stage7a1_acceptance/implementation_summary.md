# Stage 7A.1 Patch Summary

Ticket: 微律 Stage 7A.1 — Agentic Explanation / Output Guard Compatibility Patch
Model used (ticket header): DeepSeek-V4-Flash (recommended)

## Scope

Small surgical patch. Stage 7A architecture, LangGraph topology, frozen semantics,
frozen Output Guard (`src/weilv/output_guard.py`), `safety_rules.py`, `basic_rag.py`,
`personal_rag.py`, retrieval constants, formal task corpus and Stage 6 artifacts were
NOT modified.

## What changed

| File | Change |
|---|---|
| `src/weilv/dashscope_models.py` | `compose_agentic_explanation(...)` prompt contract hardened (only file changed in `src/weilv/`) |
| `tests/test_stage7a1_agentic_guard_compat.py` | NEW — 9 deterministic contract + Guard-compatibility tests |
| `evaluation/runners/run_stage7a1_smoke.py` | NEW — Case A only live smoke runner (captures raw LLM explanation via a runner-side wrapper; no production change) |

## The prompt contract (generation-time fix, no post-hoc sanitizer)

System prompt now requires:
1. Do NOT repeat numbers/units from the user query or factors unless the exact
   number+unit is present verbatim in the selected task instruction or task evidence.
   This also applies when summarizing factor content; a concrete example is included
   (user says "只有5分钟" → explanation must NOT contain "5分钟", write "可用时间较短").
2. Express time constraints qualitatively (e.g. "只有几分钟" → "当前可用时间较短").
3. Do not invent any new number/unit.
4. No second task / health prescription / diagnosis; do not alter the task instruction.
5. Output ≤ 120 Chinese characters (margin below the frozen 200-char Guard limit).
6. Still explain factors considered, why the selected task fits, evidence grounding,
   and personalization only when it actually affected ranking.

User message also reminds the model that numbers/units in the query/factors are for
understanding only and must not be echoed unless grounded, including when summarizing
factors.

## Why this hardening

In the first live smoke run of this ticket the raw LLM explanation echoed the user's
quantity "5分钟" while summarizing the F4 factor ("5分钟极短时段难以开展有效调节（F4）"),
even though neither the selected task instruction nor the evidence contains "5分钟".
The frozen Guard correctly rejected with `adds_unsupported_quantity`. The Guard is
correct; the failure was live-model compliance with the new prompt contract. The prompt
was strengthened with the explicit worked example and a "summarizing factors counts too"
clause. The re-run below confirms compliance.

## Live smoke (exactly one run, Case A)

Query: "我刚连续写了一段时间作业，现在只有5分钟，而且已经比较接近平时睡觉时间，
我今天不太想做活动，怎么安排更合适？"

- selected task: `MT-SLEEP-002`
- Output Guard: **passed = true**, reason_codes = []
- fallback: **not used**
- raw explanation (88 chars, no unsupported quantity):
  "考虑连续用眼后的休息需求、临近就寝时间、活动意愿低及可用时间短，选择按时睡觉最合理。
  任务指令强调保持固定睡眠时间，证据指出稳定作息利于健康睡眠，且睡前避免刺激符合当前状态。"

Full JSON in `live_smoke_result.json`.
