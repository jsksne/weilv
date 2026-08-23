"""Stage 8 formal evaluator unit tests.

Covers: Gold-label leak guard, Gold Utility@1 scoring, Wilson CI, factor
coverage computation, memory alignment, and mechanical recomputation of
aggregate metrics from raw results.
"""

import json
import math

from evaluation.runners.run_stage8_formal_evaluation import (
    GOLD_ONLY_FIELDS,
    _memory_alignment,
    factor_coverage_metrics,
    input_hash,
    per_case_metrics,
    runtime_fields,
    system_metrics,
    wilson_ci,
)

GOLD_PATH = "evaluation/datasets/agentic_complex_gold_frozen_v1_2.jsonl"


def _load_gold():
    return [
        json.loads(line)
        for line in open(GOLD_PATH, encoding="utf-8").read().splitlines()
        if line.strip()
    ]


def _task_case():
    return {
        "case_id": "AGX-001",
        "case_type": "task",
        "query": "在家连续复习了四十多分钟，只想安静歇一下。",
        "target_stage": "primary_upper",
        "current_context": "home",
        "activity_context": "reading",
        "available_minutes": 10,
        "safety_flags": {
            "vision_abnormal": False,
            "physical_discomfort": False,
            "medical_request": False,
            "cannot_move": False,
            "unstable_environment": False,
            "sleep_being_crowded": False,
        },
        "preferred_task_ids": ["MT-BREAK-003"],
        "acceptable_task_ids": ["MT-BREAK-001"],
        "expected_status": "allowed",
        "gold_required_factors": [{"factor_type": "behavior_need", "description": "x"}],
        "gold_soft_preferences": ["prefers quiet rest"],
        "memory_enabled": False,
        "synthetic_memory_fixture": [],
    }


def test_runtime_fields_never_leak_gold_labels():
    for case in _load_gold():
        runtime = runtime_fields(case)
        assert not (GOLD_ONLY_FIELDS & set(runtime)), case["case_id"]
        assert "preferred_task_ids" not in runtime
        assert "gold_required_factors" not in runtime


def test_input_hash_is_deterministic_and_label_independent():
    case = _task_case()
    first = input_hash(case)
    assert first == input_hash(case)
    altered = {**case, "preferred_task_ids": ["MT-BREAK-001"]}
    assert input_hash(altered) == first


def _record(case_id, system, status="allowed", top1=None):
    return {
        "case_id": case_id,
        "case_type": "task",
        "system": system,
        "result": (
            {"status": status, "selected_task_id": top1, "sources": [], "explanation": ""}
            if status != "error"
            else None
        ),
        "error": status == "error",
    }


def test_utility_scoring():
    case = _task_case()
    # preferred top1 -> 2
    rows = per_case_metrics(
        [_record("AGX-001", "basic", top1="MT-BREAK-003")], [case]
    )
    assert rows[0]["utility"] == 2
    # acceptable top1 -> 1
    rows = per_case_metrics([_record("AGX-001", "basic", top1="MT-BREAK-001")], [case])
    assert rows[0]["utility"] == 1
    # invalid top1 -> 0
    rows = per_case_metrics([_record("AGX-001", "basic", top1="MT-EYE-001")], [case])
    assert rows[0]["utility"] == 0
    # non-allowed status -> 0 even if a task id is present
    rows = per_case_metrics(
        [_record("AGX-001", "basic", status="no_safe_task", top1=None)], [case]
    )
    assert rows[0]["utility"] == 0
    # error -> 0
    rows = per_case_metrics([_record("AGX-001", "basic", status="error")], [case])
    assert rows[0]["utility"] == 0


def test_wilson_ci():
    low, high = wilson_ci(20, 20)
    assert low > 0.8 and high == 1.0  # exact: ci converges to [~0.84, 1]
    low, high = wilson_ci(0, 20)
    assert low == 0.0 and high < 0.2


def test_factor_coverage_macro_micro_all_covered():
    gold = [
        {
            "case_id": "AGX-001",
            "case_type": "task",
            "gold_required_factors": [{"factor_type": "a"}, {"factor_type": "b"}],
        },
        {
            "case_id": "AGX-002",
            "case_type": "task",
            "gold_required_factors": [{"factor_type": "a"}],
        },
        {"case_id": "AGX-021", "case_type": "safety"},
    ]
    judgment = [
        {"case_id": "AGX-001", "gold_factor_position": 1, "covered": "true", "evidence": "F1"},
        {"case_id": "AGX-001", "gold_factor_position": 2, "covered": "false", "evidence": ""},
        {"case_id": "AGX-002", "gold_factor_position": 1, "covered": "true", "evidence": "F1"},
    ]
    coverage = factor_coverage_metrics(gold, judgment)
    assert coverage["macro_required_factor_coverage"] == (0.5 + 1.0) / 2
    assert coverage["micro_required_factor_coverage"] == 2 / 3
    assert coverage["all_factors_covered_rate"] == 1 / 2
    assert coverage["covered_factors_total"] == 2
    assert coverage["required_factors_total"] == 3
    low, high = coverage["all_factors_covered_wilson_95_ci"]
    assert 0 <= low <= high <= 1


def test_memory_alignment():
    case = {
        "case_type": "task",
        "memory_enabled": True,
        "synthetic_memory_fixture": [
            {
                "memory_type": "task_preference",
                "task_id": "MT-BREAK-001",
                "memory_value": {"preference": "prefer_task"},
            },
            {
                "memory_type": "task_feedback",
                "task_id": "MT-SED-001",
                "memory_value": {
                    "completion_status": "partially_completed",
                    "helpfulness": 2,
                    "burden": "hard",
                },
            },
        ],
    }
    aligned = _memory_alignment(
        {"error": False, "result": {"status": "allowed", "selected_task_id": "MT-BREAK-001"}},
        case,
    )
    assert aligned is True
    violated = _memory_alignment(
        {"error": False, "result": {"status": "allowed", "selected_task_id": "MT-SED-001"}},
        case,
    )
    assert violated is False


def test_aggregate_recomputed_from_raw():
    gold = [_task_case(), {**_task_case(), "case_id": "AGX-002", "memory_enabled": True,
        "synthetic_memory_fixture": [{"memory_type": "task_preference", "task_id": "MT-BREAK-001",
            "memory_value": {"preference": "prefer_task"}}]}]
    records = [
        _record("AGX-001", "basic", top1="MT-BREAK-003"),
        _record("AGX-001", "personal", top1="MT-BREAK-003"),
        _record("AGX-001", "agentic", top1="MT-BREAK-003"),
        _record("AGX-002", "basic", top1="MT-BREAK-003"),
        _record("AGX-002", "personal", top1="MT-BREAK-003"),
        _record("AGX-002", "agentic", top1="MT-BREAK-003"),
    ]
    rows = per_case_metrics(records, gold)
    metrics = system_metrics(rows, gold)
    for system in ("basic", "personal", "agentic"):
        utility = metrics[f"Gold Utility@1|{system}"]
        assert utility["denominator"] == 2
        assert utility["numerator"] == 4
        assert math.isclose(utility["value"], 2.0)


def test_all_24_frozen_cases_have_complete_runtime_partition():
    gold = _load_gold()
    assert len(gold) == 24
    for case in gold:
        runtime = runtime_fields(case)
        if case["case_type"] == "task":
            assert case["preferred_task_ids"]
            assert not (set(case["preferred_task_ids"]) & set(case["acceptable_task_ids"]))


# ---------------------------------------------------------------------------
# post-run audit corrections
# ---------------------------------------------------------------------------


def _sp_case(case_id):
    return {
        "case_id": case_id,
        "case_type": "task",
        "target_stage": "junior_high",
        "current_context": "home",
        "activity_context": "reading",
        "available_minutes": 10,
        "safety_flags": {
            "vision_abnormal": False, "physical_discomfort": False,
            "medical_request": False, "cannot_move": False,
            "unstable_environment": False, "sleep_being_crowded": False,
        },
        "preferred_task_ids": [], "acceptable_task_ids": [],
        "gold_soft_preferences": ["x"],
        "memory_enabled": False, "synthetic_memory_fixture": [],
    }


def test_soft_preference_mechanical_scoring():
    from evaluation.runners.run_stage8_formal_evaluation import _soft_preference_aligned

    # AGX-001 "prefers quiet rest and no movement": a movement task misaligns.
    case = _sp_case("AGX-001")
    assert (
        _soft_preference_aligned(
            {"error": False, "result": {"status": "allowed", "selected_task_id": "MT-REC-001"}},
            case,
        )
        is False
    )
    assert (
        _soft_preference_aligned(
            {"error": False, "result": {"status": "allowed", "selected_task_id": "MT-BREAK-001"}},
            case,
        )
        is True
    )
    # AGX-007 must-finish-screen: MT-SLEEP-001 contradicts, MT-SLEEP-004 aligns.
    case = _sp_case("AGX-007")
    assert (
        _soft_preference_aligned(
            {"error": False, "result": {"status": "allowed", "selected_task_id": "MT-SLEEP-001"}},
            case,
        )
        is False
    )
    assert (
        _soft_preference_aligned(
            {"error": False, "result": {"status": "allowed", "selected_task_id": "MT-SLEEP-004"}},
            case,
        )
        is True
    )
    # No deterministic rule -> human review needed, never guessed.
    case = _sp_case("AGX-004")
    assert (
        _soft_preference_aligned(
            {"error": False, "result": {"status": "allowed", "selected_task_id": "MT-BREAK-004"}},
            case,
        )
        is None
    )


def test_evidence_matcher_detects_unexpected_kc_reference():
    from evaluation.runners.run_stage8_formal_evaluation import _evidence_contaminated
    from weilv.micro_tasks import load_formal_micro_tasks

    task = next(t for t in load_formal_micro_tasks() if t["task_id"] == "MT-BREAK-001")
    frozen_ids = task["evidence_chunk_ids"]
    case = {
        "case_type": "task", "target_stage": "junior_high",
        "current_context": "home", "activity_context": "reading",
        "available_minutes": 10, "safety_flags": {}, "query": "q",
    }
    clean = {
        "error": False,
        "result": {
            "status": "allowed", "selected_task_id": "MT-BREAK-001",
            "sources": [{"chunk_id": chunk_id} for chunk_id in frozen_ids],
            "explanation": "休息一下",
        },
    }
    assert _evidence_contaminated(clean, case) is False
    contaminated = {
        "error": False,
        "result": {
            "status": "allowed", "selected_task_id": "MT-BREAK-001",
            "sources": [{"chunk_id": chunk_id} for chunk_id in frozen_ids],
            "explanation": "依据KC-UNKNOWN-999的知识",  # KC id not in frozen evidence
        },
    }
    assert _evidence_contaminated(contaminated, case) is True


def test_candidate_invariance_from_records():
    from evaluation.runners.run_stage8_formal_evaluation import (
        candidate_invariance_from_records,
    )

    records = [
        {
            "system": "agentic",
            "case_id": "AGX-001",
            "result": {
                "agentic_diagnostics": {
                    "task_candidate_ids": ["A", "B"],
                    "personal_task_ranking": ["B", "A"],
                }
            },
        },
        {
            "system": "agentic",
            "case_id": "AGX-002",
            "result": {
                "agentic_diagnostics": {
                    "task_candidate_ids": ["A", "B"],
                    "personal_task_ranking": ["B", "A", "C"],  # resurrection
                }
            },
        },
        {"system": "basic", "case_id": "AGX-001", "result": None},
    ]
    rows = candidate_invariance_from_records(records)
    by_case = {row["case_id"]: row for row in rows}
    assert by_case["AGX-001"]["invariant"] is True
    assert by_case["AGX-002"]["invariant"] is False
    assert by_case["AGX-002"]["resurrected_count"] == 1


def test_guard_unsafe_leakage_is_not_fallback_count():
    from evaluation.runners.run_stage8_formal_evaluation import (
        SAFE_EXPLANATION_FALLBACK,
        guard_and_leakage_audit,
    )

    records = [
        # guard rejected -> safe fallback served -> blocked, not leaked
        {
            "system": "agentic", "case_id": "AGX-001",
            "result": {
                "selected_task_id": "MT-BREAK-001",
                "explanation_guard": {"passed": False, "fallback_used": True},
                "explanation": SAFE_EXPLANATION_FALLBACK,
            },
        },
        # guard rejected but unsafe text still served -> leaked
        {
            "system": "agentic", "case_id": "AGX-002",
            "result": {
                "selected_task_id": "MT-BREAK-001",
                "explanation_guard": {"passed": False, "fallback_used": True},
                "explanation": "请执行MT-SED-001任务。",  # unsafe text escaped
            },
        },
        # guard passed -> fine
        {
            "system": "agentic", "case_id": "AGX-003",
            "result": {
                "selected_task_id": "MT-BREAK-001",
                "explanation_guard": {"passed": True, "fallback_used": False},
                "explanation": "该任务适合当前情况。",
            },
        },
    ]
    audit = guard_and_leakage_audit(records)
    agentic = audit["agentic"]
    assert agentic["guard_fallback_count"] == 2
    assert agentic["output_guard_pass_count"] == 1
    assert agentic["unsafe_leakage_count"] == 1
    assert agentic["unsafe_leakage_case_ids"] == ["AGX-002"]
