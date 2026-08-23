import csv
import json
from pathlib import Path

import pytest

DATASET_PATH = Path("evaluation/datasets/personal_rag_screening_v1.jsonl")


def _task(task_id, *, contexts=("home",), capabilities=()):
    return {
        "task_id": task_id,
        "title": task_id,
        "instruction": f"instruction {task_id}",
        "trigger": "休息",
        "domain": "break",
        "covered_domains": ["break"],
        "context_tags": ["break"],
        "target_stage": ["junior_high"],
        "execution_contexts": list(contexts),
        "estimated_minutes": 10,
        "review_status": "content_reviewed",
        "safety_capabilities": list(capabilities),
    }


def _case():
    return {
        "case_id": "SC-TEST",
        "archetype_id": "CA-TEST",
        "description": "synthetic test scenario",
        "query": "刚完成一段学习，现在可以休息。",
        "target_stage": "junior_high",
        "current_context": "home",
        "activity_context": "writing",
        "available_minutes": 15,
        "safety_inputs": {
            "vision_abnormal": False,
            "physical_discomfort": False,
            "medical_request": False,
            "cannot_move": False,
            "unstable_environment": False,
            "sleep_being_crowded": False,
        },
        "provenance_level": "C",
        "dataset_version": "personal_rag_screening_v1",
    }


def test_dataset_loads_all_frozen_cases_against_formal_request_schema():
    from evaluation.runners.run_personal_screening import load_dataset

    cases = load_dataset(DATASET_PATH)
    archetype_counts = {}
    for case in cases:
        archetype_counts[case["archetype_id"]] = (
            archetype_counts.get(case["archetype_id"], 0) + 1
        )

    assert len(cases) == 24
    assert len({case["case_id"] for case in cases}) == 24
    assert archetype_counts == {f"CA-{index:02d}": 2 for index in range(1, 13)}
    assert all(case["provenance_level"] == "C" for case in cases)


def test_dataset_rejects_invalid_formal_enum(tmp_path):
    from evaluation.runners.run_personal_screening import load_dataset

    case = _case()
    case["current_context"] = "library"
    path = tmp_path / "invalid.jsonl"
    path.write_text(json.dumps(case, ensure_ascii=False) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="current_context"):
        load_dataset(path, expected_case_count=None, expected_archetype_count=None)


def test_basic_only_screening_reuses_production_task_pipeline_and_forbids_other_paths(
    monkeypatch,
):
    from evaluation.runners import run_personal_screening as screening
    from weilv import basic_rag, personal_memory_retrieval, personal_rag

    eligible_a = _task("TASK-A")
    eligible_b = _task("TASK-B")
    unsafe = _task("TASK-UNSAFE", capabilities=("continue_study",))
    wrong_context = _task("TASK-WRONG-CONTEXT", contexts=("school",))
    candidates = [eligible_a, eligible_b, unsafe, wrong_context]
    calls = {"embed": 0, "bm25": 0, "vector": 0, "rerank": 0}

    def forbidden(*_args, **_kwargs):
        raise AssertionError("disabled Stage 6A-PERS path was called")

    monkeypatch.setattr(personal_memory_retrieval, "retrieve_personal_memories", forbidden)
    monkeypatch.setattr(personal_rag, "personalize_task_candidates", forbidden)
    monkeypatch.setattr(basic_rag, "explain_selected_task", forbidden)

    def embed(*_args, **_kwargs):
        calls["embed"] += 1
        return [[0.1] * 1024]

    def bm25(*_args, **_kwargs):
        calls["bm25"] += 1
        return [{**task, "bm25_rank": index, "bm25_score": 1.0} for index, task in enumerate(candidates, 1)]

    def vector(*_args, **_kwargs):
        calls["vector"] += 1
        return [{**task, "vector_rank": index, "vector_score": 1.0} for index, task in enumerate(candidates, 1)]

    def rerank(query, documents, api_key):
        calls["rerank"] += 1
        assert documents == [basic_rag._task_document(eligible_a), basic_rag._task_document(eligible_b)]
        return [
            {"index": 1, "relevance_score": 0.9},
            {"index": 0, "relevance_score": 0.8},
        ]

    monkeypatch.setattr(basic_rag, "embed_texts", embed)
    monkeypatch.setattr(basic_rag, "bm25_search", bm25)
    monkeypatch.setattr(basic_rag, "vector_search", vector)
    monkeypatch.setattr(basic_rag, "rerank_texts", rerank)

    case = _case()
    case["safety_inputs"]["sleep_being_crowded"] = True
    result = screening.screen_case(case, client=object(), api_key="key")

    assert calls == {"embed": 1, "bm25": 1, "vector": 1, "rerank": 1}
    assert result["status"] == "allowed"
    assert result["eligible_task_ids"] == ["TASK-A", "TASK-B"]
    assert result["candidate_ranking"] == [
        {"task_id": "TASK-B", "base_rank": 1, "rerank_score": 0.9},
        {"task_id": "TASK-A", "base_rank": 2, "rerank_score": 0.8},
    ]
    assert result["selected_task_id"] == "TASK-B"
    assert result["filtered_task_ids"] == ["TASK-UNSAFE", "TASK-WRONG-CONTEXT"]
    assert result["filter_reason_codes"] == {
        "TASK-UNSAFE": ["sleep_displaced_by_study"],
        "TASK-WRONG-CONTEXT": ["metadata_filter_mismatch"],
    }
    assert result["model_call_counts"] == {
        "text_embedding_v4": 1,
        "qwen3_rerank": 1,
        "qwen_plus": 0,
        "memory_retrieval": 0,
        "personalization": 0,
    }


def test_run_outputs_fixed_jsonl_csv_config_and_complete_provenance(tmp_path, monkeypatch):
    from evaluation.runners import run_personal_screening as screening

    cases = [_case()]
    fake_result = {
        "case_id": "SC-TEST",
        "archetype_id": "CA-TEST",
        "status": "allowed",
        "matched_rule_ids": [],
        "eligible_candidate_count": 1,
        "eligible_task_ids": ["TASK-A"],
        "candidate_ranking": [{"task_id": "TASK-A", "base_rank": 1}],
        "selected_task_id": "TASK-A",
        "filtered_task_ids": [],
        "filter_reason_codes": {},
        "latency_ms": 1.25,
        "model_call_counts": {
            "text_embedding_v4": 1,
            "qwen3_rerank": 1,
            "qwen_plus": 0,
            "memory_retrieval": 0,
            "personalization": 0,
        },
    }
    monkeypatch.setattr(screening, "screen_case", lambda *_args, **_kwargs: fake_result)
    dataset_path = tmp_path / "dataset.jsonl"
    dataset_path.write_text(
        json.dumps(cases[0], ensure_ascii=False) + "\n", encoding="utf-8"
    )

    run_dir = screening.run_screening(
        cases,
        client=object(),
        api_key="key",
        dataset_path=dataset_path,
        output_root=tmp_path,
        run_id="screening-test-run",
    )

    assert {path.name for path in run_dir.iterdir()} == {
        "config.json",
        "provenance.json",
        "per_case_results.jsonl",
        "screening_summary.csv",
    }
    provenance = json.loads((run_dir / "provenance.json").read_text(encoding="utf-8"))
    assert set(provenance) >= {
        "run_id",
        "created_at",
        "git_commit",
        "dataset_name",
        "dataset_version",
        "dataset_sha256",
        "pipeline",
        "memory",
        "personalization",
        "BM25_RECALL_K",
        "VECTOR_RECALL_K",
        "embedding_model",
        "embedding_dim",
        "reranker_model",
        "qwen_plus_used",
        "model_call_counts",
    }
    assert provenance["pipeline"] == "basic_rag_screening"
    assert provenance["memory"] == "off"
    assert provenance["personalization"] == "off"
    assert provenance["qwen_plus_used"] is False
    assert provenance["BM25_RECALL_K"] == provenance["VECTOR_RECALL_K"] == 10

    rows = list(csv.DictReader((run_dir / "screening_summary.csv").open(encoding="utf-8-sig")))
    assert rows[0]["rank_1_task_id"] == "TASK-A"
    assert rows[0]["rank_2_task_id"] == ""
    assert set(rows[0]) == {
        "case_id",
        "archetype_id",
        "status",
        "eligible_candidate_count",
        "rank_1_task_id",
        "rank_2_task_id",
        "rank_3_task_id",
        "rank_4_task_id",
        "rank_5_task_id",
        "selected_task_id",
        "matched_rule_ids",
        "latency_ms",
    }
