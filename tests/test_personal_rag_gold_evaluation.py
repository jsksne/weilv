import json
from pathlib import Path

import pytest

GOLD_PATH = Path("evaluation/datasets/personal_rag_gold_v1.jsonl")
BASELINE_PATH = Path(
    "evaluation/runs/20260816T061751Z_personal_rag_screening_v1/per_case_results.jsonl"
)


class FakeClient:
    def __init__(self):
        self.documents = {}
        self.create_refreshes = []

    def index(self, *, index, id, document, refresh=None):
        self.documents[(index, id)] = dict(document)

    def create(self, *, index, id, document, refresh=None):
        self.create_refreshes.append(refresh)
        self.documents[(index, id)] = dict(document)

    def get(self, *, index, id):
        return {"_source": dict(self.documents[(index, id)])}

    def update(self, *, index, id, doc, refresh=None):
        self.documents[(index, id)].update(doc)

    def delete(self, *, index, id, refresh=None):
        self.documents.pop((index, id), None)


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_gold_dataset_has_twelve_unique_valid_interventions_grounded_in_frozen_baseline():
    from evaluation.runners.run_personal_gold_evaluation import load_baseline, load_gold

    baseline = load_baseline(BASELINE_PATH)
    gold, _sha = load_gold(GOLD_PATH, baseline)

    assert [case["gold_case_id"] for case in gold] == [f"G{index:02d}" for index in range(1, 13)]
    assert len({case["gold_case_id"] for case in gold}) == 12
    assert all(case["provenance_level"] == "B+C" for case in gold)


def test_g10_and_g11_use_current_production_memory_schema():
    from evaluation.runners.run_personal_gold_evaluation import (
        build_memory_candidate,
        load_baseline,
        load_gold,
    )
    from weilv.user_memory import UserProfile, validate_memory_candidate

    baseline = load_baseline(BASELINE_PATH)
    gold, _sha = load_gold(GOLD_PATH, baseline)
    cases = {case["gold_case_id"]: case for case in gold}
    profile = UserProfile("eval-user", "junior_high", True, "now", "now")

    g10 = build_memory_candidate(cases["G10"]["synthetic_memories"][0], "eval-user", "now")
    g11 = build_memory_candidate(cases["G11"]["synthetic_memories"][0], "eval-user", "now")

    assert validate_memory_candidate(profile, g10, set())["valid"] is True
    assert validate_memory_candidate(profile, g11, set())["valid"] is True
    assert g10.memory_value == {"preferred_context": "study_space"}
    assert g11.memory_value == {"preferred_max_task_minutes": 20}


def test_gold_case_uses_production_memory_creation_retrieval_and_personalization_only(
    monkeypatch,
):
    from evaluation.runners import run_personal_gold_evaluation as runner
    from weilv import basic_rag, personal_memory_retrieval

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Task retrieval/rerank/qwen-plus path must not run")

    for name in ("embed_texts", "bm25_search", "vector_search", "rerank_texts", "explain_selected_task"):
        monkeypatch.setattr(basic_rag, name, forbidden)

    client = FakeClient()
    embedded = []
    retrieved_users = []

    def embed_memory(client, user_id, memory_id, api_key):
        embedded.append((user_id, memory_id))
        return {"status": "embedded", "memory_id": memory_id}

    def retrieve(client, profile, query, api_key):
        retrieved_users.append(profile.user_id)
        return [
            document
            for (index, _id), document in client.documents.items()
            if index == "user_memory_v1" and document["user_id"] == profile.user_id
        ]

    monkeypatch.setattr(personal_memory_retrieval, "embed_memory", embed_memory)
    monkeypatch.setattr(personal_memory_retrieval, "retrieve_personal_memories", retrieve)
    baseline = {
        "case_id": "SC-01B",
        "eligible_task_ids": ["MT-BREAK-002", "MT-BREAK-003", "MT-BREAK-001"],
        "candidate_ranking": [
            {"task_id": "MT-BREAK-002", "base_rank": 1},
            {"task_id": "MT-BREAK-003", "base_rank": 2},
            {"task_id": "MT-BREAK-001", "base_rank": 3},
        ],
        "filtered_task_ids": [],
        "filter_reason_codes": {},
        "matched_rule_ids": [],
    }
    gold = {
        "gold_case_id": "G01",
        "source_scenario_id": "SC-01B",
        "synthetic_memories": [
            {
                "memory_type": "task_preference",
                "task_id": "MT-BREAK-003",
                "memory_key": "task_preference",
                "memory_value": {"preference": "prefer_task"},
            }
        ],
        "gold_expectation": {
            "target_ranks": [
                {
                    "task_id": "MT-BREAK-003",
                    "base_rank": 2,
                    "expected_personal_rank": 1,
                    "expected_direction": "promote",
                    "metric_role": "promotion",
                }
            ],
            "expected_top1": "MT-BREAK-003",
            "candidate_set_unchanged": True,
        },
    }
    scenario = {
        "query": "刚完成一段电脑上的学习任务。",
        "target_stage": "senior_high",
    }

    result = runner.execute_gold_case(
        gold,
        scenario,
        baseline,
        eval_user_id="eval_pers_g01_run",
        client=client,
        api_key="key",
        valid_task_ids={"MT-BREAK-001", "MT-BREAK-002", "MT-BREAK-003"},
    )

    assert result["personal_top1"] == "MT-BREAK-003"
    assert result["candidate_set_unchanged"] is True
    assert result["gold_pass"] is True
    assert client.create_refreshes == ["wait_for"]
    assert len(embedded) == 1
    assert retrieved_users == ["eval_pers_g01_run"]


def test_personalization_output_cannot_expand_or_remove_frozen_candidate_set(monkeypatch):
    from evaluation.runners import run_personal_gold_evaluation as runner
    from weilv import personal_rag

    monkeypatch.setattr(
        personal_rag,
        "personalize_task_candidates",
        lambda tasks, memories: [*tasks, {"task_id": "INVENTED"}],
    )

    with pytest.raises(RuntimeError, match="candidate set changed"):
        runner.personalize_frozen_candidates(
            [{"task_id": "TASK-A", "base_rank": 1}], []
        )


def test_evaluation_user_ids_are_isolated_by_gold_case_and_run():
    from evaluation.runners.run_personal_gold_evaluation import evaluation_user_id

    ids = {evaluation_user_id(f"G{index:02d}", "run-123") for index in range(1, 13)}

    assert len(ids) == 12
    assert ids == {f"eval_pers_g{index:02d}_run_123" for index in range(1, 13)}


def test_frozen_file_hash_detects_gold_or_baseline_mutation(tmp_path):
    from evaluation.runners.run_personal_gold_evaluation import (
        assert_file_hash_unchanged,
        file_sha256,
    )

    path = tmp_path / "frozen.jsonl"
    path.write_text('{"version":1}\n', encoding="utf-8")
    frozen_sha = file_sha256(path)
    path.write_text('{"version":2}\n', encoding="utf-8")

    with pytest.raises(RuntimeError, match="Frozen Gold changed"):
        assert_file_hash_unchanged(path, frozen_sha, "Frozen Gold")


def test_production_personalization_keeps_g12_frozen_weights_and_tie_break():
    from evaluation.runners.run_personal_gold_evaluation import personalize_frozen_candidates

    base = [
        {"task_id": "MT-BREAK-001", "base_rank": 1},
        {"task_id": "MT-BREAK-003", "base_rank": 2},
        {"task_id": "MT-REC-001", "base_rank": 3},
        {"task_id": "MT-SED-001", "base_rank": 4},
        {"task_id": "MT-REC-002", "base_rank": 5},
    ]
    memories = [
        {
            "memory_id": "UM-G12",
            "memory_type": "task_feedback",
            "task_id": "MT-REC-002",
            "memory_value": {
                "completion_status": "completed",
                "helpfulness": 5,
                "burden": "easy",
            },
        }
    ]

    ranking = personalize_frozen_candidates(base, memories)

    assert [(item["task_id"], item["personal_rank"]) for item in ranking[:2]] == [
        ("MT-BREAK-001", 1),
        ("MT-REC-002", 2),
    ]
    target = next(item for item in ranking if item["task_id"] == "MT-REC-002")
    assert target["personalization_delta"] == 4
    assert target["adjusted_rank"] == 1


def test_metrics_are_computed_from_per_case_rank_observations():
    from evaluation.runners.run_personal_gold_evaluation import calculate_metrics

    results = []
    promotion_changes = {"G01": 1, "G03": 1, "G05": 1, "G12": 3}
    demotion_changes = {"G02": 2, "G04": 3, "G05": 3}
    for index in range(1, 13):
        case_id = f"G{index:02d}"
        results.append(
            {
                "gold_case_id": case_id,
                "valid": True,
                "candidate_set_unchanged": True,
                "promotion_rank_gains": (
                    [promotion_changes[case_id]] if case_id in promotion_changes else []
                ),
                "demotion_rank_changes": (
                    [demotion_changes[case_id]] if case_id in demotion_changes else []
                ),
                "basic_controlled_top1_aligned": False if index <= 5 else None,
                "personal_controlled_top1_aligned": True if index <= 5 else None,
                "safety_invariance_pass": True if case_id in {"G06", "G07"} else None,
                "context_non_resurrection_pass": True if case_id == "G08" else None,
                "irrelevant_memory_noop_pass": True if case_id == "G09" else None,
                "unsupported_memory_noop_pass": (
                    True if case_id in {"G10", "G11"} else None
                ),
                "bounded_personalization_pass": True if case_id == "G12" else None,
            }
        )

    metrics = calculate_metrics(results, "run-123")

    assert metrics["Promotion Success Rate"]["value"] == 1.0
    assert metrics["Demotion Success Rate"]["value"] == 1.0
    assert metrics["Basic Controlled Synthetic Preference-aligned Top1 Rate"]["value"] == 0.0
    assert metrics["Personal Controlled Synthetic Preference-aligned Top1 Rate"]["value"] == 1.0
    assert metrics["Mean Promotion Rank Gain"]["value"] == 1.5
    assert metrics["Median Promotion Rank Gain"]["value"] == 1.0
    assert metrics["Mean Demotion Rank Change"]["value"] == pytest.approx(8 / 3)
    assert metrics["Median Demotion Rank Change"]["value"] == 3.0
    assert metrics["Candidate-set Invariance Rate"]["value"] == 1.0
    assert metrics["G12 Bounded Personalization Pass"]["value"] == 1.0
