import json
from pathlib import Path

RULES_PATH = Path("data/metadata/safety_rules_v0.1.json")
KNOWLEDGE_PATH = Path("data/metadata/health_knowledge_v1.jsonl")
TASKS_PATH = Path("data/metadata/micro_tasks_v1.jsonl")


def test_default_rules_path_is_independent_of_current_working_directory(tmp_path, monkeypatch):
    from weilv.safety_rules import load_safety_rules

    monkeypatch.chdir(tmp_path)

    assert len(load_safety_rules()) == 12


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _task(task_id: str) -> dict:
    return next(task for task in _jsonl(TASKS_PATH) if task["task_id"] == task_id)


def test_rule_file_has_frozen_schema_and_valid_evidence():
    payload = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    rules = payload["rules"]
    knowledge_ids = {item["chunk_id"] for item in _jsonl(KNOWLEDGE_PATH)}
    required = {
        "rule_id",
        "name",
        "category",
        "priority",
        "conditions",
        "actions",
        "applicable_domains",
        "evidence_chunk_ids",
        "enabled",
        "version",
    }

    assert payload["schema_version"] == "1.0"
    assert [rule["rule_id"] for rule in rules] == [f"SR-{number:03}" for number in range(1, 13)]
    assert all(required == set(rule) for rule in rules)
    assert all(rule["priority"] in {"critical", "high", "normal"} for rule in rules)
    assert all(rule["enabled"] is True and rule["version"] == "0.1" for rule in rules)
    assert all(set(rule["evidence_chunk_ids"]) <= knowledge_ids for rule in rules)
    priorities = {rule["rule_id"]: rule["priority"] for rule in rules}
    assert all(priorities[rule_id] in {"critical", "high"} for rule_id in (
        "SR-001", "SR-002", "SR-003", "SR-008", "SR-012"
    ))


def test_rules_load_in_priority_then_rule_id_order():
    from weilv.safety_rules import load_safety_rules

    rules = load_safety_rules()
    priority_order = {"critical": 0, "high": 1, "normal": 2}

    assert rules == sorted(rules, key=lambda rule: (priority_order[rule["priority"]], rule["rule_id"]))


def test_obvious_vision_abnormality_enters_help_seeking():
    from weilv.safety_rules import evaluate_input_risk

    result = evaluate_input_risk({"vision_abnormal": True})

    assert result == {
        "status": "help_seeking",
        "matched_rule_ids": ["SR-001"],
        "reason_codes": ["vision_abnormal_help_seeking"],
    }


def test_medical_request_blocks_normal_tasks_before_ranking():
    from weilv.safety_rules import evaluate_input_risk

    result = evaluate_input_risk({"medical_request": True, "ranking_score": 999})

    assert result["status"] == "blocked"
    assert result["matched_rule_ids"] == ["SR-003"]


def test_target_stage_context_and_time_mismatches_block_one_task():
    from weilv.safety_rules import filter_task_by_safety

    task = _task("MT-BREAK-004")

    assert filter_task_by_safety(task, {"target_stage": "college"})["matched_rule_ids"] == [
        "SR-004"
    ]
    assert filter_task_by_safety(task, {"current_context": "home"})["matched_rule_ids"] == [
        "SR-005"
    ]
    assert filter_task_by_safety(task, {"available_minutes": 0})["matched_rule_ids"] == [
        "SR-006"
    ]


def test_physical_discomfort_blocks_activity_task():
    from weilv.safety_rules import filter_task_by_safety

    result = filter_task_by_safety(_task("MT-OUT-001"), {"physical_discomfort": True})

    assert result["status"] == "blocked"
    assert "SR-002" in result["matched_rule_ids"]


def test_physical_discomfort_is_not_a_global_input_block():
    from weilv.safety_rules import evaluate_input_risk

    assert evaluate_input_risk({"physical_discomfort": True}) == {
        "status": "allowed",
        "matched_rule_ids": ["SR-002"],
        "reason_codes": ["physical_discomfort"],
    }


def test_physical_discomfort_filters_activity_but_keeps_formal_safe_non_activity_task():
    from weilv.safety_rules import select_safe_tasks

    activity = _task("MT-OUT-001")
    non_activity = _task("MT-SLEEP-001")

    result = select_safe_tasks(
        [activity, non_activity],
        {"physical_discomfort": True},
    )

    assert result["status"] == "allowed"
    assert [task["task_id"] for task in result["tasks"]] == ["MT-SLEEP-001"]
    assert result["matched_rule_ids"] == ["SR-002"]


def test_cannot_move_blocks_movement_task():
    from weilv.safety_rules import filter_task_by_safety

    result = filter_task_by_safety(_task("MT-OUT-001"), {"cannot_move": True})

    assert result["matched_rule_ids"] == ["SR-009"]


def test_caller_matched_contraindication_and_stop_condition_block_task():
    from weilv.safety_rules import filter_task_by_safety

    task = _task("MT-BREAK-001")

    contraindicated = filter_task_by_safety(
        task, {"matched_contraindication_task_ids": [task["task_id"]]}
    )
    stopped = filter_task_by_safety(task, {"matched_stop_condition_task_ids": [task["task_id"]]})

    assert contraindicated["matched_rule_ids"] == ["SR-007"]
    assert stopped["matched_rule_ids"] == ["SR-008"]


def test_unstable_screen_context_allows_only_simple_pause_task():
    from weilv.safety_rules import filter_task_by_safety

    context = {"unstable_reading_or_screen": True}
    pause_task = _task("MT-EYE-003")
    complex_task = _task("MT-EYE-001")

    assert filter_task_by_safety(pause_task, context)["status"] == "allowed"
    assert filter_task_by_safety(complex_task, context)["matched_rule_ids"] == ["SR-010"]


def test_sleep_displaced_by_study_blocks_continue_study_task():
    from weilv.safety_rules import filter_task_by_safety

    task = _task("MT-EYE-001")
    result = filter_task_by_safety(task, {"sleep_displaced_by_study": True})

    assert result["matched_rule_ids"] == ["SR-011"]


def test_formal_break_003_declares_continue_study_and_hits_sr011():
    from weilv.safety_rules import filter_task_by_safety

    task = _task("MT-BREAK-003")

    assert "continue_study" in task["safety_capabilities"]
    assert filter_task_by_safety(
        task, {"sleep_displaced_by_study": True}
    )["matched_rule_ids"] == ["SR-011"]


def test_formal_tasks_have_the_complete_safety_capability_contract():
    from weilv.safety_rules import SAFETY_CAPABILITIES

    tasks = _jsonl(TASKS_PATH)

    assert SAFETY_CAPABILITIES == {
        "pause_reading_or_screen",
        "requires_standing",
        "requires_movement",
        "requires_outdoor",
        "continue_study",
    }
    assert len(tasks) == 23
    assert all("safety_capabilities" in task for task in tasks)
    assert all(type(task["safety_capabilities"]) is list for task in tasks)
    assert all(set(task["safety_capabilities"]) <= SAFETY_CAPABILITIES for task in tasks)
    assert set().union(*(set(task["safety_capabilities"]) for task in tasks)) == (
        SAFETY_CAPABILITIES
    )


def test_formal_pause_task_and_complex_task_take_opposite_sr010_paths():
    from weilv.safety_rules import filter_task_by_safety

    context = {"current_context": "commute", "unstable_reading_or_screen": True}

    assert filter_task_by_safety(_task("MT-EYE-003"), context)["status"] == "allowed"
    assert filter_task_by_safety(_task("MT-EYE-006"), context)["matched_rule_ids"] == [
        "SR-010"
    ]


def test_no_safe_task_and_low_risk_pass_through():
    from weilv.safety_rules import filter_task_by_safety, select_safe_tasks

    task = _task("MT-BREAK-004")

    assert filter_task_by_safety(task, {}) == {
        "status": "allowed",
        "matched_rule_ids": [],
        "reason_codes": [],
    }
    assert select_safe_tasks([task], {"target_stage": "college"}) == {
        "status": "no_safe_task",
        "matched_rule_ids": ["SR-012", "SR-004"],
        "reason_codes": ["no_safe_whitelist_task", "target_stage_mismatch"],
        "tasks": [],
    }


def test_high_priority_input_risk_precedes_task_filtering_and_ranking():
    from weilv.safety_rules import select_safe_tasks

    result = select_safe_tasks(
        [_task("MT-BREAK-004")],
        {"vision_abnormal": True, "target_stage": "college", "ranking_score": 999},
    )

    assert result == {
        "status": "help_seeking",
        "matched_rule_ids": ["SR-001"],
        "reason_codes": ["vision_abnormal_help_seeking"],
        "tasks": [],
    }
