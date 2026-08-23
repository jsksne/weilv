"""Stage 9B.2 targeted re-audit mechanical repro for F-001 / F-002.

Runs against the CURRENT workspace src/weilv/collaborative_ranking.py.
Verifies the old crash paths are gone and fail-closed semantics hold.
Writes repro_results.json next to this script.
"""
from __future__ import annotations

import json
import sys

sys.path.insert(0, r"c:\Users\Thinkpad\Desktop\NewWeb AI智护\src")

from weilv.collaborative_ranking import (  # noqa: E402
    NEUTRAL_CF_SIGNAL,
    apply_cf_tiebreak,
)


def _task(task_id, adjusted_rank, base_rank, evidence_ids=("E-1",)):
    return {
        "task_id": task_id,
        "title": f"title-{task_id}",
        "instruction": f"instruction-{task_id}",
        "evidence_chunk_ids": list(evidence_ids),
        "personalization": {
            "adjusted_rank": adjusted_rank,
            "base_task_rank": base_rank,
            "personalization_delta": base_rank - adjusted_rank,
        },
    }


RESULTS: dict[str, dict] = {}


def record(case_id, exc, checks):
    RESULTS[case_id] = {
        "exception": None if exc is None else f"{type(exc).__name__}: {exc}",
        "checks": checks,
        "pass": exc is None and all(checks.values()),
    }


def run_case(case_id, tasks, signals, expect_reason=None):
    """Run apply_cf_tiebreak; record outcome; return (ordered, diagnostics)."""
    checks: dict[str, bool] = {}
    exc = None
    ordered = None
    diagnostics = None
    try:
        ordered, diagnostics = apply_cf_tiebreak(tasks, signals)
    except Exception as e:  # noqa: BLE001
        exc = e
    if exc is None and ordered is not None:
        before_ids = [t["task_id"] for t in tasks]
        after_ids = [t["task_id"] for t in ordered]
        checks["no_exception"] = True
        checks["original_ordering_preserved"] = after_ids == before_ids
        checks["multiset_identical"] = sorted(after_ids) == sorted(before_ids)
        checks["cardinality_identical"] = len(after_ids) == len(before_ids)
        checks["evidence_ids_unchanged"] = all(
            isinstance(t["evidence_chunk_ids"], list) for t in tasks
        )
        if diagnostics is not None:
            checks["cf_applied_false"] = diagnostics.get("cf_applied") is False
            if expect_reason is not None:
                checks["reason_matches"] = (
                    diagnostics.get("cf_fallback_reason") == expect_reason
                )
            checks["diag_before_eq_after_ids"] = (
                diagnostics.get("candidate_task_ids_after_cf")
                == diagnostics.get("candidate_task_ids_before_cf")
            )
    else:
        checks["no_exception"] = False
    record(case_id, exc, checks)
    return ordered, diagnostics


# =====================================================================
# F-001 scenario A: cf_signal = None (must fail closed, no exception)
# =====================================================================
tasks_a = [_task("A", 1, 1), _task("B", 2, 2)]
signals_a = {
    "A": {"cf_signal": None, "neighbor_count": 1, "model_version": "v1"},
    "B": {"cf_signal": None, "neighbor_count": 1, "model_version": "v1"},
}
ordered_a, diag_a = run_case(
    "F001_A_cf_signal_none", tasks_a, signals_a,
    expect_reason="nonfinite_or_out_of_range_signal",
)
if diag_a is not None:
    ok = diag_a["cf_signal_by_task"] == {"A": NEUTRAL_CF_SIGNAL, "B": NEUTRAL_CF_SIGNAL}
    RESULTS["F001_A_cf_signal_none"]["checks"]["diag_signal_neutral_fallback"] = ok
    RESULTS["F001_A_cf_signal_none"]["pass"] = (
        RESULTS["F001_A_cf_signal_none"]["pass"] and ok
    )

# Exact-tie variant: even with a tie, None signal must not reorder.
tasks_a2 = [_task("A", 1, 1), _task("B", 1, 2)]  # A wins by base rank
run_case(
    "F001_A2_cf_signal_none_with_tie", tasks_a2, signals_a,
    expect_reason="nonfinite_or_out_of_range_signal",
)

# =====================================================================
# F-001 scenario B: mixed-type model_version / data_version
# =====================================================================
tasks_b = [_task("A", 1, 1), _task("B", 2, 2)]
signals_b = {
    "A": {"cf_signal": 0.5, "neighbor_count": 1, "model_version": 5,
          "data_version": 20260818},
    "B": {"cf_signal": 0.5, "neighbor_count": 1, "model_version": "v1",
          "data_version": "2026-08-18"},
}
signals_b_clean = {
    "A": {"cf_signal": 0.5, "neighbor_count": 1, "model_version": "v1",
          "data_version": "d1"},
    "B": {"cf_signal": 0.5, "neighbor_count": 1, "model_version": "v1",
          "data_version": "d1"},
}
checks_b: dict[str, bool] = {}
exc_b = None
try:
    ordered_b, diag_b = apply_cf_tiebreak(tasks_b, signals_b)
    ordered_b_clean, _ = apply_cf_tiebreak(tasks_b, signals_b_clean)
except Exception as e:  # noqa: BLE001
    exc_b = e
    ordered_b = diag_b = ordered_b_clean = None
if exc_b is None:
    checks_b["no_exception"] = True
    checks_b["cf_applied_true"] = diag_b["cf_applied"] is True
    checks_b["metadata_fallback_not_affect_ranking"] = (
        [t["task_id"] for t in ordered_b] == [t["task_id"] for t in ordered_b_clean]
    )
    checks_b["version_fallbacks_neutral"] = (
        diag_b["cf_model_version"] == sorted({"neutral-v0.1", "v1"})
        and diag_b["cf_data_version"] == sorted({"none", "2026-08-18"})
    )
record("F001_B_mixed_type_versions", exc_b, checks_b)

# =====================================================================
# F-001 scenario C: malformed cf_signal VALUES (must fail closed) and
# malformed METADATA values (must degrade without affecting ranking).
# =====================================================================
malformed_signals = {
    "list": [1, 2, 3],
    "dict": {"x": 1},
    "bool": True,
    "nan": float("nan"),
    "inf": float("inf"),
    "neg_inf": float("-inf"),
}
for name, bad in malformed_signals.items():
    # B is lower-priority by base rank; a malformed high score on B must
    # NOT promote B -> must fail closed to original order.
    tasks_c = [_task("A", 1, 1), _task("B", 1, 2)]
    signals_c = {
        "A": {"cf_signal": 0.0, "neighbor_count": 1, "model_version": "v1"},
        "B": {"cf_signal": bad, "neighbor_count": 1, "model_version": "v1"},
    }
    run_case(
        f"F001_C_malformed_cf_signal_{name}", tasks_c, signals_c,
        expect_reason="nonfinite_or_out_of_range_signal",
    )

# Malformed metadata fields (non-signal): ranking still applies normally.
tasks_cm = [_task("A", 1, 1), _task("B", 1, 2)]
signals_cm = {
    "A": {"cf_signal": 0.9, "neighbor_count": [1], "model_version": [1, 2],
          "data_version": {"d": 1}},
    "B": {"cf_signal": -0.9, "neighbor_count": {"x": 1}, "model_version": True,
          "data_version": False},
}
checks_cm: dict[str, bool] = {}
exc_cm = None
try:
    ordered_cm, diag_cm = apply_cf_tiebreak(tasks_cm, signals_cm)
except Exception as e:  # noqa: BLE001
    exc_cm = e
    ordered_cm = diag_cm = None
if exc_cm is None:
    checks_cm["no_exception"] = True
    checks_cm["cf_applied_true"] = diag_cm["cf_applied"] is True
    checks_cm["cf_signal_decides_tie"] = (
        [t["task_id"] for t in ordered_cm] == ["A", "B"]
    )
    checks_cm["neighbor_fallback_zero"] = (
        diag_cm["cf_neighbor_count_by_task"] == {"A": 0, "B": 0}
    )
    checks_cm["version_fallbacks_neutral"] = (
        diag_cm["cf_model_version"] == ["neutral-v0.1"]
        and diag_cm["cf_data_version"] == ["none"]
    )
record("F001_C_malformed_metadata_ranking_unaffected", exc_cm, checks_cm)

# =====================================================================
# F-002: malformed neighbor_count values
# =====================================================================
for name, bad in {
    "string": "unknown",
    "none": None,
    "dict": {"x": 1},
    "nan": float("nan"),
    "inf": float("inf"),
}.items():
    tasks_f = [_task("A", 1, 1), _task("B", 1, 2)]  # tie -> base rank wins
    signals_f = {
        "A": {"cf_signal": 0.0, "neighbor_count": bad, "model_version": "v1"},
        "B": {"cf_signal": 0.0, "neighbor_count": bad, "model_version": "v1"},
    }
    case_id = f"F002_neighbor_count_{name}"
    checks_f: dict[str, bool] = {}
    exc_f = None
    try:
        ordered_f, diag_f = apply_cf_tiebreak(tasks_f, signals_f)
        signals_f_clean = {
            "A": {"cf_signal": 0.0, "neighbor_count": 0, "model_version": "v1"},
            "B": {"cf_signal": 0.0, "neighbor_count": 0, "model_version": "v1"},
        }
        ordered_f_clean, _ = apply_cf_tiebreak(tasks_f, signals_f_clean)
    except Exception as e:  # noqa: BLE001
        exc_f = e
        ordered_f = diag_f = ordered_f_clean = None
    if exc_f is None:
        checks_f["no_exception"] = True
        checks_f["ranking_unaffected"] = (
            [t["task_id"] for t in ordered_f] == [t["task_id"] for t in ordered_f_clean]
        )
        checks_f["fallback_neutral_zero"] = (
            diag_f["cf_neighbor_count_by_task"] == {"A": 0, "B": 0}
        )
        checks_f["cf_applied_true"] = diag_f["cf_applied"] is True
    record(case_id, exc_f, checks_f)

# =====================================================================
# Ranking contract: sort semantics + CF exact-tie-only influence
# =====================================================================
tasks_r = [
    _task("A", 2, 1),
    _task("B", 1, 5),
    _task("C", 2, 2),
    _task("D", 1, 6),
    _task("E", 3, 1),
]
signals_r = {
    "A": {"cf_signal": -0.9, "neighbor_count": 0},
    "B": {"cf_signal": 0.9, "neighbor_count": 0},
    "C": {"cf_signal": 0.5, "neighbor_count": 0},
    "D": {"cf_signal": -0.5, "neighbor_count": 0},
    "E": {"cf_signal": 1.0, "neighbor_count": 0},
}
checks_r: dict[str, bool] = {}
exc_r = None
try:
    ordered_r, diag_r = apply_cf_tiebreak(tasks_r, signals_r)
except Exception as e:  # noqa: BLE001
    exc_r = e
    ordered_r = diag_r = None
if exc_r is None:
    ids_r = [t["task_id"] for t in ordered_r]
    # adjusted asc -> cf desc -> base asc -> task_id asc:
    # tie(1): B(0.9) before D(-0.5); tie(2): C(0.5) before A(-0.9); E last
    checks_r["no_exception"] = True
    checks_r["sort_semantics_exact"] = ids_r == ["B", "D", "C", "A", "E"]
    checks_r["adjusted_groups_ascending"] = (
        [t["personalization"]["adjusted_rank"] for t in ordered_r] == [1, 1, 2, 2, 3]
    )
    checks_r["multiset_identical"] = sorted(ids_r) == sorted(
        t["task_id"] for t in tasks_r
    )
    checks_r["cardinality_identical"] = len(ids_r) == len(tasks_r)
    checks_r["no_mutation_object_identity"] = all(
        any(o is t for t in tasks_r) for o in ordered_r
    )
    checks_r["evidence_ids_unchanged"] = all(
        t["evidence_chunk_ids"] == ["E-1"] for t in tasks_r
    )
record("RANKING_contract_sort_semantics", exc_r, checks_r)

# =====================================================================
# Fail-closed semantics: out-of-range must NOT be clamped
# =====================================================================
tasks_v = [_task("A", 1, 1), _task("B", 1, 2)]
checks_v: dict[str, bool] = {}
exc_v = None
try:
    ordered_v, diag_v = apply_cf_tiebreak(tasks_v, {
        "A": {"cf_signal": 0.0, "neighbor_count": 0},
        "B": {"cf_signal": 1.5, "neighbor_count": 0},
    })
    ordered_v2, diag_v2 = apply_cf_tiebreak(tasks_v, {
        "A": {"cf_signal": 0.0, "neighbor_count": 0},
        "B": {"cf_signal": -2.0, "neighbor_count": 0},
    })
except Exception as e:  # noqa: BLE001
    exc_v = e
    ordered_v = diag_v = ordered_v2 = diag_v2 = None
if exc_v is None:
    checks_v["no_exception"] = True
    checks_v["above_range_fails_closed_not_clamped"] = (
        diag_v["cf_applied"] is False
        and diag_v["cf_fallback_reason"] == "nonfinite_or_out_of_range_signal"
        and [t["task_id"] for t in ordered_v] == ["A", "B"]
    )
    checks_v["below_range_fails_closed_not_clamped"] = (
        diag_v2["cf_applied"] is False
        and diag_v2["cf_fallback_reason"] == "nonfinite_or_out_of_range_signal"
        and [t["task_id"] for t in ordered_v2] == ["A", "B"]
    )
record("FAILCLOSED_no_clamping_out_of_range", exc_v, checks_v)

# =====================================================================
# Blocked resurrection: forged maximal signal for a task NOT in the set
# =====================================================================
tasks_bl = [_task("A", 1, 1), _task("B", 2, 2)]
signals_bl = {
    "A": {"cf_signal": 0.0, "neighbor_count": 0},
    "B": {"cf_signal": 0.0, "neighbor_count": 0},
    "BLOCKED": {"cf_signal": 1.0, "neighbor_count": 9},
}
ordered_bl, _diag_bl = run_case(
    "GUARD_blocked_resurrection_zero", tasks_bl, signals_bl,
    expect_reason="unknown_task_signal",
)
if ordered_bl is not None:
    ok = all(t["task_id"] != "BLOCKED" for t in ordered_bl)
    RESULTS["GUARD_blocked_resurrection_zero"]["checks"]["no_blocked_task_present"] = ok
    RESULTS["GUARD_blocked_resurrection_zero"]["pass"] = (
        RESULTS["GUARD_blocked_resurrection_zero"]["pass"] and ok
    )

# =====================================================================
summary = {
    "all_pass": all(r["pass"] for r in RESULTS.values()),
    "cases": RESULTS,
}
out_path = (
    r"c:\Users\Thinkpad\Desktop\NewWeb AI智护\evaluation\stage9\audit"
    r"\stage9b2_repro_results_v1.json"
)
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)

print(json.dumps(summary, indent=2, ensure_ascii=False))
print(f"\nALL_PASS={summary['all_pass']}")
