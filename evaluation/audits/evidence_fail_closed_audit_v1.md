# Evidence Fail-Closed Audit v1

- Audit date: 2026-08-17 (Stage 6F Phase B)
- Prior formal run (NOT modified): `20260816T155329Z_evidence_contract_v1`
- New integration run: `20260817T114145Z_evidence_fail_closed_integration_v1`

## B1. Actual production path (verified from source, not comments)

| Step | Source | Behavior |
|---|---|---|
| 1. Load evidence | `weilv/basic_rag.py:137-160` `load_task_evidence(client, selected_task, knowledge_index)` | ES terms query on `chunk_id`; keeps ONLY hits whose `chunk_id` is expected AND `review_status == "content_reviewed"` AND `"micro_task_evidence" in proposed_use`; silently drops everything else. |
| 2. Fail-closed check | `weilv/basic_rag.py:265-273` `_finalize_selected_task` | `[item["chunk_id"] for item in task_evidence] != selected_task["evidence_chunk_ids"]` → returns `status="no_safe_task"`, `selected_task=None`, `reason_codes=["selected_task_evidence_invalid"]`. |
| 3. Model call ordering | `weilv/basic_rag.py:275` | `explain_selected_task` (qwen-plus) runs only AFTER the equality check passes. On fail-closed it is never reached. |

## B2. Prior fail-closed fixtures audit — verdict: scenario B

The "3/3 fail-closed" rows in run `20260816T155329Z_evidence_contract_v1` were produced by
`evaluation/runners/_overnight_phase_c.py:162-233` (`_run_fail_closed`). That code:

- called `load_task_evidence` with perturbed REQUESTED lists, then
- performed its own array comparison INSIDE the evaluator
  (`caller_detected = returned_ids != caller_expected`, lines 190 / 201 / 211) and
- never invoked the production decision point `_finalize_selected_task`.

So the prior result demonstrated "the divergence would be caller-detectable", not that
production actually fails closed. **Old CR-EVID-002 "SUPPORTED" from that run must NOT be
treated as measured evidence of production fail-closed behavior.** (The Exact-Match /
Contamination / Missing = 0 results from the same run remain valid — they measured
`load_task_evidence` directly and are unaffected by this defect.)

## B3. Real integration test — new run

Runner: `evaluation/runners/evidence_fail_closed_integration_v1.py`
Run: `evaluation/runs/20260817T114145Z_evidence_fail_closed_integration_v1/`
Method: invokes the ACTUAL `weilv.basic_rag._finalize_selected_task` with a fake ES client
(no real index touched, no production code modified); `explain_selected_task` monkeypatched
with a spy — a real qwen-plus call is impossible (model_call_counts all 0).

| Case | Scenario | Result |
|---|---|---|
| EFC-MISSING-001 | one expected evidence ID missing from index | PASS — no_safe_task / selected_task_evidence_invalid, qwen-plus not called |
| EFC-NONEXISTENT-001 | expected evidence ID nonexistent | PASS — same fail-closed result |
| EFC-REVIEWSTATUS-001 | evidence present but `review_status="draft"` | PASS — filtered by `load_task_evidence` → mismatch → fail closed |
| EFC-PROPOSEDUSE-001 | evidence present but `proposed_use=["rag_knowledge"]` | PASS — same |
| EFC-CONTROL-VALID | complete valid evidence (positive control) | PASS — status allowed, task selected, explanation emitted |

## Claim status

- CR-EVID-001 (Exact Evidence Match): remains SUPPORTED (prior run, path measured directly).
- **CR-EVID-002 (Fail-Closed on Invalid Evidence): SUPPORTED — now measured via the real
  production finalization path** (supersedes the evaluator-internal comparison from
  2026-08-16; that earlier "measurement" is reclassified as non-measured simulation).
- CR-EVID-REAL-001: remains UNSUPPORTED (by definition).

## Production gap?

None. Production fails closed on all four invalid-evidence scenarios; no fix needed; no
STOP condition triggered by this phase.
