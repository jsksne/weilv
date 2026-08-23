"""Stage 7A.1 — Agentic explanation / frozen Output Guard compatibility contract.

These tests prove the `compose_agentic_explanation` prompt contract keeps the
generated explanation compatible with the frozen `output_guard` without
weakening the Guard itself.
"""

from types import SimpleNamespace

from weilv.output_guard import validate_explanation_output

QUERY = "我刚连续写了一段时间作业，现在只有5分钟，而且已经比较接近平时睡觉时间"
FACTORS = [
    {"factor_id": "F1", "subquery": "连续学习后只剩5分钟，接近睡觉时间"},
]
SELECTED_TASK = {
    "title": "接近睡觉时间前的准备",
    "instruction": "闭眼休息3分钟。",
}
EVIDENCE = [{"content": "接近平时睡觉时间时应提前准备睡眠，闭眼休息有助于放松。"}]
KNOWLEDGE = [{"content": "睡前放松有助于更快入睡。"}]
FORMAL_TASKS = [
    {"task_id": "MT-SLEEP-002", "title": "接近睡觉时间前的准备"},
    {"task_id": "MT-SED-001", "title": "写作业久坐后的起身活动"},
]


def _capture_call():
    calls = []

    def fake_call(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            status_code=200,
            output={"choices": [{"message": {"content": "合规解释文本。"}}]},
        )

    return calls, fake_call


def _compose(calls, fake_call, monkeypatch):
    from weilv import dashscope_models

    monkeypatch.setattr(dashscope_models.Generation, "call", fake_call)
    return dashscope_models.compose_agentic_explanation(
        QUERY,
        FACTORS,
        SELECTED_TASK,
        EVIDENCE,
        KNOWLEDGE,
        None,
        api_key="test-key",
    )


def test_prompt_forbids_repeating_user_query_quantities(monkeypatch):
    calls, fake_call = _capture_call()
    _compose(calls, fake_call, monkeypatch)
    system = calls[0]["messages"][0]["content"]

    assert "不得复述用户问题或因素中的数字或单位" in system
    assert "分钟" in system
    assert "小时" in system
    assert "次" in system
    assert "天" in system
    assert "个" in system


def test_prompt_uses_qualitative_wording_for_user_time_constraints(monkeypatch):
    calls, fake_call = _capture_call()
    _compose(calls, fake_call, monkeypatch)
    system = calls[0]["messages"][0]["content"]

    assert "定性表述" in system
    assert "当前可用时间较短" in system
    assert "只有几分钟" in system


def test_prompt_targets_120_chars_below_guard_limit(monkeypatch):
    calls, fake_call = _capture_call()
    _compose(calls, fake_call, monkeypatch)
    system = calls[0]["messages"][0]["content"]

    assert "不超过120字" in system


def test_prompt_forbids_new_task_and_prescription(monkeypatch):
    calls, fake_call = _capture_call()
    _compose(calls, fake_call, monkeypatch)
    system = calls[0]["messages"][0]["content"]

    assert "第二个任务" in system
    assert "健康处方" in system
    assert "诊断治疗" in system
    assert "不得修改或违背任务指令" in system


def test_prompt_still_requires_factor_evidence_and_personalization_coverage(monkeypatch):
    calls, fake_call = _capture_call()
    _compose(calls, fake_call, monkeypatch)
    system = calls[0]["messages"][0]["content"]
    user = calls[0]["messages"][1]["content"]

    assert "为什么" in system
    assert "证据如何支持" in system
    assert "个性化仅在确实影响排序时提及" in system

    assert "用户情况：" in user and QUERY in user
    assert "F1" in user and "连续学习后只剩5分钟" in user
    assert "已选任务：接近睡觉时间前的准备" in user
    assert "任务指令：闭眼休息3分钟。" in user
    assert "精确任务证据" in user and "接近平时睡觉时间" in user
    assert "相关检索知识" in user
    assert "个性化：无个性化排序影响" in user


def test_prompt_reminds_user_message_numbers_are_for_understanding_only(monkeypatch):
    calls, fake_call = _capture_call()
    _compose(calls, fake_call, monkeypatch)
    user = calls[0]["messages"][1]["content"]

    assert "不得在解释中复述" in user
    assert "除非该数字与单位原样出现在已选任务指令或任务证据中" in user


def test_compliant_explanation_passes_frozen_guard_with_5_minutes_in_query():
    explanation = (
        "该任务结合了连续学习后的休息需求和接近睡觉时间的因素，"
        "其指令与证据支持入睡前的放松安排，适合当前情况。"
    )
    task = {"task_id": "MT-SLEEP-002", **SELECTED_TASK}

    assert validate_explanation_output(explanation, task, EVIDENCE, FORMAL_TASKS) == {
        "passed": True,
        "reason_codes": [],
    }


def test_explanation_repeating_unsupported_5_minutes_is_rejected_by_frozen_guard():
    task = {"task_id": "MT-SLEEP-002", **SELECTED_TASK}

    result = validate_explanation_output(
        "考虑到只有5分钟，建议先闭眼休息。", task, EVIDENCE, FORMAL_TASKS
    )

    assert result["passed"] is False
    assert "adds_unsupported_quantity" in result["reason_codes"]


def test_mocked_compliant_explanation_round_trips_through_real_guard(monkeypatch):
    from weilv import dashscope_models

    compliant = (
        "该任务依据连续学习后的休息需求与接近睡觉时间的因素，"
        "其指令和证据支持入睡前的放松安排，适合当前情况。"
    )
    monkeypatch.setattr(
        dashscope_models.Generation,
        "call",
        lambda **_: SimpleNamespace(
            status_code=200,
            output={"choices": [{"message": {"content": compliant}}]},
        ),
    )
    explanation = dashscope_models.compose_agentic_explanation(
        QUERY,
        FACTORS,
        SELECTED_TASK,
        EVIDENCE,
        KNOWLEDGE,
        None,
        api_key="test-key",
    )
    task = {"task_id": "MT-SLEEP-002", **SELECTED_TASK}

    assert explanation == compliant
    assert validate_explanation_output(explanation, task, EVIDENCE, FORMAL_TASKS) == {
        "passed": True,
        "reason_codes": [],
    }
