import pytest

TASK = {
    "task_id": "MT-SED-001",
    "title": "写作业久坐后的起身活动",
    "instruction": "起身活动约10分钟再继续。",
}
EVIDENCE = [{"content": "久坐1小时后起身活动10分钟。"}]
FORMAL_TASKS = [
    {"task_id": "MT-SED-001", "title": "写作业久坐后的起身活动"},
    {"task_id": "MT-EYE-003", "title": "移动场景先暂停阅读"},
]


def test_short_grounded_explanation_passes():
    from weilv.output_guard import validate_explanation_output

    assert validate_explanation_output(
        "这个任务与当前久坐后的10分钟休息条件相符。", TASK, EVIDENCE, FORMAL_TASKS
    ) == {"passed": True, "reason_codes": []}


@pytest.mark.parametrize(
    ("explanation", "reason_code"),
    [
        ("改做 MT-EYE-003。", "mentions_other_task"),
        ("建议改做移动场景先暂停阅读。", "mentions_other_task"),
        ("再做10个深蹲。", "adds_unsupported_action"),
        ("每天做30分钟。", "adds_unsupported_quantity"),
        ("内容" * 201, "explanation_too_long"),
    ],
)
def test_guard_rejects_frozen_output_violations(explanation, reason_code):
    from weilv.output_guard import validate_explanation_output

    result = validate_explanation_output(explanation, TASK, EVIDENCE, FORMAL_TASKS)

    assert result["passed"] is False
    assert reason_code in result["reason_codes"]


def test_action_and_quantity_are_allowed_when_grounded():
    from weilv.output_guard import validate_explanation_output

    task = {**TASK, "instruction": "做10个深蹲，持续10分钟。"}

    assert validate_explanation_output(
        "按任务做10个深蹲，持续10分钟。", task, EVIDENCE, FORMAL_TASKS
    )["passed"] is True
