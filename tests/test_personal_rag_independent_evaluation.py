from pathlib import Path

import pytest

PROFILE_PATH = Path("evaluation/datasets/personal_rag_users_v1.jsonl")
SCENARIO_PATH = Path("evaluation/datasets/personal_rag_independent_scenarios_v1.jsonl")
MATRIX_PATH = Path("evaluation/datasets/personal_rag_independent_matrix_v1.jsonl")
MANIFEST_PATH = Path("evaluation/manifests/personal_rag_independent_v1.json")


def test_preregistered_datasets_have_six_profiles_eight_scenarios_and_24_cases():
    from evaluation.runners.run_personal_independent_evaluation import (
        load_matrix,
        load_profiles,
        load_scenarios,
    )

    task_ids = {
        "MT-BREAK-001",
        "MT-BREAK-002",
        "MT-BREAK-003",
        "MT-REC-001",
        "MT-SED-001",
        "MT-EYE-005",
        "MT-SLEEP-002",
        "MT-SLEEP-004",
    }
    profiles = load_profiles(PROFILE_PATH, task_ids)
    scenarios = load_scenarios(SCENARIO_PATH)
    matrix = load_matrix(MATRIX_PATH, profiles, scenarios)

    assert [profile["profile_id"] for profile in profiles] == [f"P0{i}" for i in range(1, 7)]
    assert [scenario["scenario_id"] for scenario in scenarios] == [f"S0{i}" for i in range(1, 9)]
    assert len(matrix) == len({case["case_id"] for case in matrix}) == 24
    assert all(profile["provenance_level"] == "C" for profile in profiles)
    assert all(scenario["provenance_level"] == "C" for scenario in scenarios)


def test_manifest_freezes_profiles_scenarios_and_gold_matrix_before_basic():
    from evaluation.runners.run_personal_independent_evaluation import load_manifest

    manifest = load_manifest(
        MANIFEST_PATH,
        profile_path=PROFILE_PATH,
        scenario_path=SCENARIO_PATH,
        matrix_path=MATRIX_PATH,
    )

    assert manifest["preregistered_before_basic_run"] is True
    assert len(manifest["profile_dataset_sha256"]) == 64
    assert len(manifest["scenario_dataset_sha256"]) == 64
    assert len(manifest["benchmark_matrix_sha256"]) == 64


def test_basic_scenarios_execute_each_unique_scenario_once_without_qwen_plus(monkeypatch):
    from evaluation.runners import run_personal_independent_evaluation as runner
    from weilv import basic_rag

    calls = []

    def forbidden(*_args, **_kwargs):
        raise AssertionError("qwen-plus must not run")

    monkeypatch.setattr(basic_rag, "explain_selected_task", forbidden)

    def screen(case, client, api_key):
        calls.append(case["case_id"])
        return {
            "case_id": case["case_id"],
            "status": "allowed",
            "matched_rule_ids": [],
            "eligible_task_ids": ["TASK-A"],
            "candidate_ranking": [{"task_id": "TASK-A", "base_rank": 1}],
            "selected_task_id": "TASK-A",
            "filtered_task_ids": [],
            "filter_reason_codes": {},
            "latency_ms": 1.0,
            "model_call_counts": {
                "text_embedding_v4": 1,
                "qwen3_rerank": 1,
                "qwen_plus": 0,
                "memory_retrieval": 0,
                "personalization": 0,
            },
        }

    scenarios = [
        {
            "scenario_id": f"S0{i}",
            "query": "query",
            "target_stage": "junior_high",
            "current_context": "home",
            "activity_context": "other",
            "available_minutes": 5,
            "safety_inputs": runner.false_safety_inputs(),
        }
        for i in range(1, 9)
    ]

    results = runner.run_basic_scenarios(
        scenarios, client=object(), api_key="key", screen_case_fn=screen
    )

    assert calls == [f"S0{i}" for i in range(1, 9)]
    assert len(results) == 8
    assert sum(row["model_call_counts"]["text_embedding_v4"] for row in results.values()) == 8
    assert sum(row["model_call_counts"]["qwen3_rerank"] for row in results.values()) == 8


def test_each_profile_reuses_one_eval_user_and_two_memories_across_four_cases():
    from evaluation.runners.run_personal_independent_evaluation import (
        evaluation_user_id,
        profile_case_groups,
    )

    matrix = [
        {"case_id": f"IND-P01-S0{i}", "profile_id": "P01", "scenario_id": f"S0{i}"}
        for i in range(1, 5)
    ]
    groups = profile_case_groups(matrix)

    assert groups == {"P01": [f"IND-P01-S0{i}" for i in range(1, 5)]}
    assert evaluation_user_id("P01", "run-123") == "eval_ind_p01_run_123"


def test_personal_candidate_set_cannot_expand(monkeypatch):
    from evaluation.runners.run_personal_independent_evaluation import (
        personalize_frozen_candidates,
    )
    from weilv import personal_rag

    monkeypatch.setattr(
        personal_rag,
        "personalize_task_candidates",
        lambda tasks, memories: [*tasks, {"task_id": "INVENTED"}],
    )

    with pytest.raises(RuntimeError, match="candidate set changed"):
        personalize_frozen_candidates([{"task_id": "TASK-A", "base_rank": 1}], [])


def test_metrics_are_calculated_from_all_raw_cases_including_ties():
    from evaluation.runners.run_personal_independent_evaluation import calculate_metrics

    results = []
    for index in range(24):
        preferred_available = index < 12
        avoided_available = index < 8
        if index < 8:
            basic_utility, personal_utility = 0, 1
        elif index < 12:
            basic_utility, personal_utility = 0, -1
        else:
            basic_utility = personal_utility = 0
        results.append(
            {
                "case_id": f"C{index:02d}",
                "profile_id": f"P0{index // 4 + 1}",
                "preferred_available": preferred_available,
                "avoided_available": avoided_available,
                "base_preferred_rank": 3 if preferred_available else None,
                "personal_preferred_rank": 2 if preferred_available else None,
                "base_avoided_rank": 2 if avoided_available else None,
                "personal_avoided_rank": 3 if avoided_available else None,
                "base_top1": (
                    "PREFERRED" if index < 3 else "AVOIDED" if index < 7 else "OTHER"
                ),
                "personal_top1": (
                    "PREFERRED" if index < 6 else "AVOIDED" if index < 8 else "OTHER"
                ),
                "preferred_task_id": "PREFERRED",
                "avoided_task_id": "AVOIDED",
                "basic_preference_utility": basic_utility,
                "personal_preference_utility": personal_utility,
                "utility_delta": personal_utility - basic_utility,
                "candidate_set_unchanged": True,
                "ranking_unchanged": not preferred_available and not avoided_available,
                "any_memory_hit": index < 18,
                "preferred_memory_retrieval_hit": index < 12,
                "avoided_memory_retrieval_hit": index < 6,
            }
        )

    metrics, profiles = calculate_metrics(results, "run-123")

    assert metrics["Mean Basic Preference Utility@1"]["value"] == 0.0
    assert metrics["Mean Personal Preference Utility@1"]["value"] == pytest.approx(1 / 6)
    assert metrics["Mean Utility Improvement"]["value"] == pytest.approx(1 / 6)
    assert metrics["Personal Wins"]["value"] == 8
    assert metrics["Ties"]["value"] == 12
    assert metrics["Personal Losses"]["value"] == 4
    assert metrics["Preferred Task Availability Rate"]["value"] == 0.5
    assert metrics["Basic Preferred Top1 Rate"]["value"] == 0.25
    assert metrics["Personal Preferred Top1 Rate"]["value"] == 0.5
    assert metrics["Basic Avoided Top1 Rate"]["value"] == 0.5
    assert metrics["Personal Avoided Top1 Rate"]["value"] == 0.25
    assert metrics["Mean Preferred Rank Gain"]["value"] == 1.0
    assert metrics["Mean Avoided Rank Demotion"]["value"] == 1.0
    assert metrics["Out-of-pool Memory No-op Rate"]["value"] == 1.0
    assert metrics["Candidate-set Invariance Rate"]["value"] == 1.0
    assert len(profiles) == 6
