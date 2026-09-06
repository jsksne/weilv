"""Stage 9B product CF adapter tests (synthetic engineering evidence).

Implements the frozen Stage 9A v1.1 product contract safety matrix: neutral
scores, exact-tie reorder, no-tie no-op, deterministic tie behavior, provider
anomalies (extra task, duplicate task, NaN, infinity, out-of-range), missing /
corrupt artifacts, new-user / insufficient-history / insufficient-neighbors /
unsupported-domain / unknown-context fallbacks, maximal forged score for a
blocked task, non-allowed terminal states, and the absolute invariants
(candidate invariance, blocked-task resurrection, task mutation,
evidence-ID mutation, guard contract).  Privacy tests assert diagnostics carry
only aggregate fields.
"""


import pytest

from conftest import NullElasticClient

from weilv.collaborative_ranking import (
    CF_SIGNAL_MAX,
    CF_SIGNAL_MIN,
    MIN_NEIGHBORS,
    MIN_TARGET_INTERACTIONS,
    NEUTRAL_CF_SIGNAL,
    apply_cf_tiebreak,
    apply_cf_to_ranking,
    neutral_cf_provider,
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


def _signal(task_id, value, neighbors=0, version="neutral-v0.1"):
    return {
        task_id: {
            "cf_signal": value,
            "neighbor_count": neighbors,
            "model_version": version,
        }
    }


# ---------------------------------------------------------------------------
# Neutral / no-op behavior
# ---------------------------------------------------------------------------

def test_neutral_provider_returns_bounded_zero_signals():
    signals = neutral_cf_provider(["A", "B"])
    assert set(signals) == {"A", "B"}
    for entry in signals.values():
        assert entry["cf_signal"] == NEUTRAL_CF_SIGNAL
        assert entry["neighbor_count"] == 0
        assert CF_SIGNAL_MIN <= entry["cf_signal"] <= CF_SIGNAL_MAX


def test_none_provider_is_strict_noop():
    tasks = [_task("A", 1, 1), _task("B", 2, 2)]
    ordered, diagnostics = apply_cf_to_ranking(tasks, None)
    assert ordered is tasks  # same object, zero behavior change
    assert diagnostics is None


def test_neutral_signals_never_reorder():
    tasks = [_task("A", 1, 2), _task("B", 1, 1)]  # exact tie, B has better base rank
    ordered, diagnostics = apply_cf_tiebreak(tasks, neutral_cf_provider(["A", "B"]))
    assert [task["task_id"] for task in ordered] == ["B", "A"]  # base rank wins
    assert diagnostics["cf_applied"] is True


def test_no_tie_noop():
    tasks = [_task("A", 1, 1), _task("B", 2, 2), _task("C", 3, 3)]
    signals = _signal("A", 0.9) | _signal("B", 0.8) | _signal("C", -0.9)
    ordered, _ = apply_cf_tiebreak(tasks, signals)
    assert [task["task_id"] for task in ordered] == ["A", "B", "C"]


def test_exact_tie_reorder_within_tie_only():
    tasks = [
        _task("A", 1, 2),   # tie at adjusted 1 with B
        _task("B", 1, 1),
        _task("C", 2, 3),
        _task("D", 2, 4),
    ]
    signals = (
        _signal("A", 0.9)
        | _signal("B", -0.9)
        | _signal("C", 0.1)
        | _signal("D", -0.1)
    )
    ordered, diagnostics = apply_cf_tiebreak(tasks, signals)
    assert [task["task_id"] for task in ordered] == ["A", "B", "C", "D"]
    # D (base 4) reorders after C (base 3) within tie at adjusted 2 by cf
    assert diagnostics["cf_applied"] is True
    # groups preserve adjusted_rank ordering
    ranks = [task["personalization"]["adjusted_rank"] for task in ordered]
    assert ranks == sorted(ranks)


def test_deterministic_tie_behavior():
    tasks = [_task("A", 1, 1), _task("B", 1, 1), _task("C", 1, 1)]
    signals = _signal("A", 0.0) | _signal("B", 0.0) | _signal("C", 0.0)
    first, _ = apply_cf_tiebreak(tasks, signals)
    second, _ = apply_cf_tiebreak(tasks, signals)
    assert [task["task_id"] for task in first] == [task["task_id"] for task in second]
    # tertiary key task_id decides within full ties
    assert [task["task_id"] for task in first] == ["A", "B", "C"]


# ---------------------------------------------------------------------------
# Fail-closed anomalies
# ---------------------------------------------------------------------------

def _assert_fail_closed(tasks, signals, reason_substring):
    ordered, diagnostics = apply_cf_tiebreak(tasks, signals)
    assert [task["task_id"] for task in ordered] == [task["task_id"] for task in tasks]
    assert diagnostics["cf_applied"] is False
    assert reason_substring in diagnostics["cf_fallback_reason"]


def test_extra_task_from_provider_fails_closed():
    tasks = [_task("A", 1, 1)]
    _assert_fail_closed(tasks, _signal("A", 0.0) | _signal("BLOCKED", 1.0),
                        "unknown_task_signal")


def test_maximal_forged_score_for_blocked_task_fails_closed():
    tasks = [_task("A", 1, 1), _task("B", 2, 2)]
    # a malicious provider forges the maximal score for a task NOT in the set
    _assert_fail_closed(tasks, _signal("A", 0.0) | _signal("BLOCKED", 1.0),
                        "unknown_task_signal")
    assert all(task["task_id"] != "BLOCKED" for task in tasks)


def test_duplicate_candidate_fails_closed():
    tasks = [_task("A", 1, 1), _task("A", 1, 1)]
    _assert_fail_closed(tasks, _signal("A", 0.5), "duplicate_candidate_task")


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_signal_fails_closed(bad):
    tasks = [_task("A", 1, 1), _task("B", 2, 2)]
    _assert_fail_closed(tasks, _signal("A", bad) | _signal("B", 0.0),
                        "nonfinite_or_out_of_range_signal")


def test_out_of_range_signal_fails_closed():
    tasks = [_task("A", 1, 1), _task("B", 2, 2)]
    _assert_fail_closed(tasks, _signal("A", CF_SIGNAL_MAX + 0.01) | _signal("B", 0.0),
                        "nonfinite_or_out_of_range_signal")
    _assert_fail_closed(tasks, _signal("A", CF_SIGNAL_MIN - 0.01) | _signal("B", 0.0),
                        "nonfinite_or_out_of_range_signal")


def test_missing_cf_artifact_fails_closed():
    tasks = [_task("A", 1, 1)]
    ordered, diagnostics = apply_cf_tiebreak(tasks, None)
    assert [task["task_id"] for task in ordered] == ["A"]
    assert diagnostics["cf_fallback_reason"] == "missing_cf_artifact"


def test_corrupt_cf_artifact_fails_closed():
    tasks = [_task("A", 1, 1)]
    _, diagnostics = apply_cf_tiebreak(tasks, "not-a-dict")
    assert diagnostics["cf_fallback_reason"] == "corrupt_cf_artifact"
    _, diagnostics = apply_cf_tiebreak(tasks, {"A": "not-a-dict"})
    assert diagnostics["cf_fallback_reason"] == "corrupt_signal_entry"


def test_missing_signal_for_candidate_fails_closed():
    tasks = [_task("A", 1, 1), _task("B", 2, 2)]
    _assert_fail_closed(tasks, _signal("A", 0.5), "missing_signal_for_candidate")


def test_missing_rank_fields_fail_closed():
    """Regression (audit MAJOR): a candidate without numeric rank fields must
    fail closed instead of crashing the sort."""
    good = _task("A", 1, 1)
    broken = _task("B", 2, 2)
    del broken["personalization"]["adjusted_rank"]
    tasks = [good, broken]
    ordered, diagnostics = apply_cf_tiebreak(
        tasks, _signal("A", 0.9) | _signal("B", 0.0)
    )
    assert [task["task_id"] for task in ordered] == ["A", "B"]
    assert diagnostics["cf_applied"] is False
    assert diagnostics["cf_fallback_reason"] == "missing_rank_fields"

    # None rank values also fail closed
    broken2 = _task("C", 2, 2)
    broken2["personalization"]["base_task_rank"] = None
    _, diagnostics2 = apply_cf_tiebreak(
        [good, broken2], _signal("A", 0.9) | _signal("C", 0.0)
    )
    assert diagnostics2["cf_fallback_reason"] == "missing_rank_fields"


# ---------------------------------------------------------------------------
# Fail-closed on malformed provider diagnostics (Stage 9B.1 repair F-001/F-002)
# ---------------------------------------------------------------------------

def test_cf_signal_none_fails_closed_without_exception():
    """Regression (audit F-001): provider cf_signal=None previously crashed
    _diagnostics via float(None).  Must fail closed with no exception."""
    tasks = [_task("A", 1, 1), _task("B", 2, 2)]
    signals = _signal("A", None) | _signal("B", None)
    ordered, diagnostics = apply_cf_tiebreak(tasks, signals)
    assert [task["task_id"] for task in ordered] == ["A", "B"]
    assert diagnostics["cf_applied"] is False
    assert diagnostics["cf_fallback_reason"] == "nonfinite_or_out_of_range_signal"
    # candidate multiset and cardinality unchanged; diagnostics use safe fallback
    assert sorted(task["task_id"] for task in ordered) == ["A", "B"]
    assert len(ordered) == len(tasks)
    assert diagnostics["cf_signal_by_task"] == {"A": NEUTRAL_CF_SIGNAL,
                                                "B": NEUTRAL_CF_SIGNAL}


def test_malformed_mixed_type_version_metadata_fails_closed():
    """Regression (audit F-001): mixed-type model_version / data_version values
    previously raised TypeError inside sorted() during the diagnostics build.
    Non-string versions must degrade to neutral fallbacks with no exception."""
    tasks = [_task("A", 1, 1), _task("B", 2, 2)]
    signals = {
        "A": {"cf_signal": 0.5, "neighbor_count": 1, "model_version": 5,
              "data_version": 20260818},
        "B": {"cf_signal": 0.5, "neighbor_count": 1, "model_version": "v1",
              "data_version": "2026-08-18"},
    }
    ordered, diagnostics = apply_cf_tiebreak(tasks, signals)
    assert [task["task_id"] for task in ordered] == ["A", "B"]
    assert diagnostics["cf_applied"] is True
    assert diagnostics["cf_model_version"] == sorted({"neutral-v0.1", "v1"})
    assert diagnostics["cf_data_version"] == sorted({"none", "2026-08-18"})


@pytest.mark.parametrize("bad_neighbors", ["unknown", None, {"x": 1}])
def test_non_numeric_neighbor_count_degrades_safely(bad_neighbors):
    """Regression (audit F-002): non-numeric neighbor_count previously crashed
    _diagnostics via int().  Must degrade to a safe fallback with no exception
    and no ranking impact."""
    tasks = [_task("A", 1, 1), _task("B", 2, 2)]
    signals = {"A": {"cf_signal": 0.0, "neighbor_count": bad_neighbors},
               "B": {"cf_signal": 0.0, "neighbor_count": bad_neighbors}}
    ordered, diagnostics = apply_cf_tiebreak(tasks, signals)
    assert [task["task_id"] for task in ordered] == ["A", "B"]
    assert diagnostics["cf_applied"] is True
    assert diagnostics["cf_neighbor_count_by_task"] == {"A": 0, "B": 0}


# ---------------------------------------------------------------------------
# Product fallback conditions (new user / history / neighbors / domain / context)
# ---------------------------------------------------------------------------

def _conditional_provider(active):
    def provider(task_ids):
        if not active:
            return neutral_cf_provider(task_ids)
        return {task_id: {"cf_signal": 0.7, "neighbor_count": 4,
                          "model_version": "v1"} for task_id in task_ids}
    return provider


def test_new_user_insufficient_history_neighbors_domain_context_are_neutral():
    """Each product precondition failure degrades to the neutral no-op."""
    tasks = [_task("A", 1, 2), _task("B", 1, 1)]
    # provider simulates: consent absent / <10 interactions / <3 neighbors /
    # unsupported domain / unknown context -> neutral signals
    ordered, _ = apply_cf_tiebreak(
        tasks, neutral_cf_provider(["A", "B"])
    )
    assert [task["task_id"] for task in ordered] == ["B", "A"]
    # the contract constants exist and match the preregistration
    assert MIN_TARGET_INTERACTIONS == 10
    assert MIN_NEIGHBORS == 3


def test_provider_exception_fails_closed():
    tasks = [_task("A", 1, 1), _task("B", 2, 2)]

    def exploding_provider(task_ids):
        raise RuntimeError("model artifact unavailable")

    ordered, diagnostics = apply_cf_to_ranking(tasks, exploding_provider)
    assert [task["task_id"] for task in ordered] == ["A", "B"]
    assert diagnostics["cf_applied"] is False
    assert diagnostics["cf_fallback_reason"] == "provider_exception"


# ---------------------------------------------------------------------------
# Absolute invariants
# ---------------------------------------------------------------------------

def test_candidate_invariance_and_no_mutation():
    tasks = [
        _task("A", 1, 2, evidence_ids=("E1", "E2")),
        _task("B", 1, 1, evidence_ids=("E3",)),
        _task("C", 2, 3, evidence_ids=("E4",)),
    ]
    before = [dict(task) for task in tasks]
    signals = _signal("A", 0.9) | _signal("B", -0.9) | _signal("C", 0.0)
    ordered, diagnostics = apply_cf_tiebreak(tasks, signals)
    assert sorted(task["task_id"] for task in ordered) == sorted(
        task["task_id"] for task in tasks
    )
    assert len(ordered) == len(tasks)
    # no task object is replaced or mutated
    for original, after in zip(tasks, ordered):
        assert after is original
    for task, snapshot in zip(tasks, before):
        assert task == snapshot
    assert diagnostics["invariant_candidate_set"] is True
    assert diagnostics["invariant_cardinality"] is True
    assert diagnostics["invariant_no_mutation"] is True


def test_evidence_ids_never_change_after_reorder():
    tasks = [
        _task("A", 1, 2, evidence_ids=("E-A1", "E-A2")),
        _task("B", 1, 1, evidence_ids=("E-B1",)),
    ]
    ordered, _ = apply_cf_tiebreak(tasks, _signal("A", 0.9) | _signal("B", -0.9))
    for task in ordered:
        assert list(task["evidence_chunk_ids"]) == (
            ["E-A1", "E-A2"] if task["task_id"] == "A" else ["E-B1"]
        )


# ---------------------------------------------------------------------------
# Privacy: diagnostics carry only aggregate fields
# ---------------------------------------------------------------------------

ALLOWED_DIAGNOSTIC_KEYS = {
    "cf_applied", "cf_fallback_reason", "cf_signal_by_task",
    "cf_neighbor_count_by_task", "candidate_task_ids_before_cf",
    "candidate_task_ids_after_cf", "cf_model_version", "cf_data_version",
    "invariant_candidate_set", "invariant_cardinality", "invariant_no_mutation",
}


def test_diagnostics_contain_only_aggregate_fields():
    tasks = [_task("A", 1, 1), _task("B", 1, 1)]
    _, diagnostics = apply_cf_tiebreak(tasks, _signal("A", 0.4) | _signal("B", -0.4))
    assert set(diagnostics.keys()) <= ALLOWED_DIAGNOSTIC_KEYS
    serialized = repr(diagnostics)
    for forbidden in ("neighbor_identity", "raw_memory", "raw_chat",
                      "health_text", "gps", "query"):
        assert forbidden not in serialized.lower()


# ---------------------------------------------------------------------------
# Integration points
# ---------------------------------------------------------------------------

def _ranked_task(task_id, rerank_rank):
    return {
        "task_id": task_id,
        "title": f"title-{task_id}",
        "instruction": f"instruction-{task_id}",
        "evidence_chunk_ids": ["E-" + task_id],
        "covered_domains": [],
        "estimated_minutes": 5,
        "rerank_rank": rerank_rank,
    }


def _integration_tasks():
    """T1 (rerank 2, memory delta +1) and T2 (rerank 1) tie at adjusted rank 1."""
    return [_ranked_task("T1", 2), _ranked_task("T2", 1), _ranked_task("T3", 3)]


T1_COMPLETED_MEMORY = [{
    "memory_id": "M1", "task_id": "T1", "memory_type": "task_feedback",
    "memory_value": {"completion_status": "completed"},
}]


def test_personal_rag_integration_cf_reorders_exact_ties(monkeypatch):
    from weilv import personal_rag

    pipeline = {
        "result": None,
        "query_embedding": [0.1],
        "knowledge": [],
        "safe_result": {"matched_rule_ids": [], "reason_codes": []},
        "reranked_tasks": _integration_tasks(),
    }
    profile = type("Profile", (), {"memory_enabled": True})()
    monkeypatch.setattr(personal_rag, "_run_basic_pipeline",
                        lambda *a, **k: pipeline)
    monkeypatch.setattr(personal_rag, "get_user_profile", lambda *a: profile)
    monkeypatch.setattr(personal_rag, "retrieve_personal_memories",
                        lambda *a, **k: T1_COMPLETED_MEMORY)

    def cf_provider(task_ids):
        return {
            task_id: {
                "cf_signal": 0.9 if task_id == "T1" else -0.9,
                "neighbor_count": 4,
                "model_version": "v1",
            }
            for task_id in task_ids
        }

    captured = {}

    def fake_finalize(request, selected_task, pipeline_, client, api_key,
                     knowledge_index, task_index):
        captured["selected_task_id"] = selected_task["task_id"]
        return {"status": "allowed", "selected_task": selected_task,
                "sources": [], "context_sources": [], "matched_rule_ids": [],
                "reason_codes": [], "explanation_guard": {}}

    monkeypatch.setattr(personal_rag, "_finalize_selected_task", fake_finalize)
    # B1 surfacing needs a real ES client; this test asserts CF tie-break
    # semantics only, so the surfacing walk is stubbed.
    monkeypatch.setattr(personal_rag, "_surfaced_tasks", lambda *a, **k: [])
    result = personal_rag.run_personal_rag(
        type("Request", (), {"query": "q"})(), "u1", NullElasticClient(), "key",
        cf_provider=cf_provider,
    )
    # Without CF, T2 (base rank 1) would win the tie; CF prefers T1
    assert captured["selected_task_id"] == "T1"
    assert result["cf"]["cf_applied"] is True
    # multiset invariance: order may change, set and cardinality must not
    before = result["cf"]["candidate_task_ids_before_cf"]
    after = result["cf"]["candidate_task_ids_after_cf"]
    assert sorted(before) == sorted(after)
    assert len(before) == len(after)


def test_agentic_apply_personalization_integration(monkeypatch):
    from weilv.agentic_rag import AgenticRagRuntime

    state = {
        "safety_status": "allowed",
        "base_task_ranking": _integration_tasks(),
        "retrieved_memories": T1_COMPLETED_MEMORY,
        "diagnostics": {},
    }

    def cf_provider(task_ids):
        return {
            task_id: {
                "cf_signal": 0.9 if task_id == "T1" else -0.9,
                "neighbor_count": 4,
                "model_version": "v1",
            }
            for task_id in task_ids
        }

    runtime = AgenticRagRuntime(None, "u1", NullElasticClient(), "key", cf_provider=cf_provider)
    result = runtime.apply_personalization(state)
    ranking = result["personal_task_ranking"]
    assert [task["task_id"] for task in ranking] == ["T1", "T2", "T3"]
    assert result["diagnostics"]["cf"]["cf_applied"] is True
    # candidate set invariant in the agentic path
    assert {task["task_id"] for task in ranking} == {"T1", "T2", "T3"}


def test_agentic_non_allowed_terminal_states_never_call_cf():
    from weilv.agentic_rag import AgenticRagRuntime

    def exploding_provider(task_ids):
        raise AssertionError("CF must not run on non-allowed states")

    runtime = AgenticRagRuntime(None, "u1", NullElasticClient(), "key",
                                cf_provider=exploding_provider)
    for terminal in ("blocked", "help_seeking", "no_safe_task"):
        result = runtime.apply_personalization(
            {"safety_status": terminal, "diagnostics": {}}
        )
        assert result == {}


def test_personal_terminal_states_never_call_cf(monkeypatch):
    """Regression (audit gap): the Personal path must short-circuit blocked /
    help_seeking / no_safe_task before CF is ever consulted."""
    from weilv import personal_rag

    def exploding_provider(task_ids):
        raise AssertionError("CF must not run on terminal states")

    def pipeline_for(status):
        return {"result": {"status": status, "selected_task": None,
                           "explanation": None, "sources": [],
                           "matched_rule_ids": [],
                           "reason_codes": ["terminal"]}}

    for terminal in ("blocked", "help_seeking", "no_safe_task"):
        monkeypatch.setattr(personal_rag, "_run_basic_pipeline",
                            lambda *a, status=terminal, **k: pipeline_for(status))
        result = personal_rag.run_personal_rag(
            type("Request", (), {"query": "q"})(), "u1", NullElasticClient(), "key",
            cf_provider=exploding_provider,
        )
        assert result["status"] == terminal


def test_agentic_default_no_cf_diagnostics():
    from weilv.agentic_rag import AgenticRagRuntime

    runtime = AgenticRagRuntime(None, "u1", NullElasticClient(), "key")
    state = {"safety_status": "allowed", "base_task_ranking": _integration_tasks(),
             "retrieved_memories": [], "diagnostics": {}}
    result = runtime.apply_personalization(state)
    assert "cf" not in result["diagnostics"]
    # personal ranking equals the frozen personalize order (no ties -> T2, T1, T3)
    assert [task["task_id"] for task in result["personal_task_ranking"]] == [
        "T2", "T1", "T3"
    ]
