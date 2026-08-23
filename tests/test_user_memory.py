from dataclasses import asdict

import pytest

VALID_TASK_IDS = {"MT-SED-001"}


def _profile(memory_enabled: bool = True):
    from weilv.user_memory import UserProfile

    return UserProfile(
        user_id="usr_anon_001",
        target_stage="junior_high",
        memory_enabled=memory_enabled,
        created_at="2026-08-13T10:00:00+08:00",
        updated_at="2026-08-13T10:00:00+08:00",
    )


def _feedback(**changes):
    from weilv.user_memory import UserMemoryCandidate

    values = {
        "memory_id": "mem_001",
        "user_id": "usr_anon_001",
        "memory_type": "task_feedback",
        "source_type": "structured_task_feedback",
        "task_id": "MT-SED-001",
        "domain": "sedentary",
        "memory_key": "task_feedback",
        "memory_value": {
            "completion_status": "completed",
            "helpfulness": 4,
            "burden": "easy",
        },
        "created_at": "2026-08-13T10:00:00+08:00",
        "updated_at": "2026-08-13T10:00:00+08:00",
    }
    values.update(changes)
    return UserMemoryCandidate(**values)


def test_enabled_structured_task_feedback_is_valid():
    from weilv.user_memory import validate_memory_candidate

    result = validate_memory_candidate(_profile(), _feedback(), VALID_TASK_IDS)

    assert result == {"valid": True, "reason_codes": []}


def test_disabled_memory_is_rejected():
    from weilv.user_memory import validate_memory_candidate

    result = validate_memory_candidate(_profile(False), _feedback(), VALID_TASK_IDS)

    assert result == {"valid": False, "reason_codes": ["memory_disabled"]}


def test_raw_chat_auto_extraction_source_is_rejected():
    from weilv.user_memory import validate_memory_candidate

    result = validate_memory_candidate(
        _profile(), _feedback(source_type="raw_chat_auto_extraction"), VALID_TASK_IDS
    )

    assert result == {"valid": False, "reason_codes": ["source_type_not_allowed"]}


def test_unknown_memory_type_is_rejected():
    from weilv.user_memory import validate_memory_candidate

    result = validate_memory_candidate(
        _profile(), _feedback(memory_type="inferred_personality"), VALID_TASK_IDS
    )

    assert result == {"valid": False, "reason_codes": ["memory_type_not_allowed"]}


@pytest.mark.parametrize(
    "field",
    [
        "vision_abnormal",
        "physical_discomfort",
        "medical_request",
        "unstable_environment",
        "sleep_being_crowded",
        "diagnosis",
        "medication",
        "treatment_record",
        "height",
        "weight",
        "mental_health_detail",
        "medical_history",
    ],
)
def test_safety_context_and_medical_fields_are_rejected(field):
    from weilv.user_memory import validate_memory_candidate

    candidate = _feedback(memory_value={field: True})

    assert validate_memory_candidate(_profile(), candidate, VALID_TASK_IDS) == {
        "valid": False,
        "reason_codes": ["forbidden_persistence_field"],
    }


def test_task_feedback_with_unknown_task_id_is_rejected():
    from weilv.user_memory import validate_memory_candidate

    result = validate_memory_candidate(_profile(), _feedback(task_id="MT-MISSING"), VALID_TASK_IDS)

    assert result == {"valid": False, "reason_codes": ["task_id_not_allowed"]}


@pytest.mark.parametrize(
    ("memory_value", "reason_code"),
    [
        (
            {"completion_status": "finished", "helpfulness": 4, "burden": "easy"},
            "invalid_completion_status",
        ),
        (
            {"completion_status": "completed", "helpfulness": 6, "burden": "easy"},
            "invalid_helpfulness",
        ),
        (
            {"completion_status": "completed", "helpfulness": 4, "burden": "heavy"},
            "invalid_burden",
        ),
    ],
)
def test_task_feedback_enums_and_rating_range_are_enforced(memory_value, reason_code):
    from weilv.user_memory import validate_memory_candidate

    result = validate_memory_candidate(
        _profile(), _feedback(memory_value=memory_value), VALID_TASK_IDS
    )

    assert result == {"valid": False, "reason_codes": [reason_code]}


def test_profile_and_candidate_must_belong_to_the_same_user():
    from weilv.user_memory import validate_memory_candidate

    result = validate_memory_candidate(
        _profile(), _feedback(user_id="usr_anon_002"), VALID_TASK_IDS
    )

    assert result == {"valid": False, "reason_codes": ["user_id_mismatch"]}


def test_source_type_must_match_memory_type():
    from weilv.user_memory import validate_memory_candidate

    result = validate_memory_candidate(
        _profile(), _feedback(source_type="explicit_user_setting"), VALID_TASK_IDS
    )

    assert result == {"valid": False, "reason_codes": ["source_type_mismatch"]}


@pytest.mark.parametrize(
    ("memory_type", "memory_value"),
    [
        (
            "task_feedback",
            {
                "completion_status": "completed",
                "helpfulness": 4,
                "burden": "easy",
                "notes": "extra",
            },
        ),
        ("task_preference", {"preference": "prefer_task", "reason": "extra"}),
        ("context_preference", {"preferred_context": "home", "mood": "extra"}),
        ("user_constraint", {"preferred_max_task_minutes": 5, "other": True}),
    ],
)
def test_each_memory_type_rejects_non_allowlisted_value_fields(memory_type, memory_value):
    from weilv.user_memory import validate_memory_candidate

    candidate = _feedback(
        memory_type=memory_type,
        source_type=(
            "structured_task_feedback"
            if memory_type == "task_feedback"
            else "explicit_user_setting"
        ),
        task_id="MT-SED-001" if memory_type in {"task_feedback", "task_preference"} else None,
        memory_key=memory_type,
        memory_value=memory_value,
    )

    assert validate_memory_candidate(_profile(), candidate, VALID_TASK_IDS) == {
        "valid": False,
        "reason_codes": ["memory_value_field_not_allowed"],
    }


@pytest.mark.parametrize(
    ("memory_type", "memory_value"),
    [
        ("task_preference", {"preference": "prefer_task"}),
        ("context_preference", {"preferred_context": "home"}),
        ("context_preference", {"avoid_context": "school"}),
        ("context_preference", {"school_device_unavailable": True}),
        ("user_constraint", {"preferred_max_task_minutes": 5}),
        ("user_constraint", {"school_device_unavailable": False}),
    ],
)
def test_allowed_structured_memory_values_are_valid(memory_type, memory_value):
    from weilv.user_memory import validate_memory_candidate

    candidate = _feedback(
        memory_type=memory_type,
        source_type="explicit_user_setting",
        task_id="MT-SED-001" if memory_type == "task_preference" else None,
        memory_key=memory_type,
        memory_value=memory_value,
    )

    assert validate_memory_candidate(_profile(), candidate, VALID_TASK_IDS) == {
        "valid": True,
        "reason_codes": [],
    }


@pytest.mark.parametrize(
    ("memory_type", "memory_value"),
    [
        ("task_preference", {"preference": "sometimes"}),
        ("context_preference", {"preferred_context": "hospital"}),
        ("context_preference", {"school_device_unavailable": "yes"}),
        ("user_constraint", {"preferred_max_task_minutes": 0}),
        ("user_constraint", {"preferred_max_task_minutes": 61}),
        ("user_constraint", {"school_device_unavailable": 1}),
    ],
)
def test_structured_memory_value_types_and_enums_are_enforced(memory_type, memory_value):
    from weilv.user_memory import validate_memory_candidate

    candidate = _feedback(
        memory_type=memory_type,
        source_type="explicit_user_setting",
        task_id="MT-SED-001" if memory_type == "task_preference" else None,
        memory_key=memory_type,
        memory_value=memory_value,
    )

    assert validate_memory_candidate(_profile(), candidate, VALID_TASK_IDS)["valid"] is False


def test_recursive_sensitive_field_guard_still_precedes_allowlist_validation():
    from weilv.user_memory import validate_memory_candidate

    candidate = _feedback(
        memory_type="context_preference",
        source_type="explicit_user_setting",
        task_id=None,
        memory_key="context_preference",
        memory_value={"preferred_context": {"diagnosis": "private"}},
    )

    assert validate_memory_candidate(_profile(), candidate, VALID_TASK_IDS) == {
        "valid": False,
        "reason_codes": ["forbidden_persistence_field"],
    }


def test_user_profile_rejects_legacy_target_stage():
    from weilv.user_memory import UserProfile

    with pytest.raises(ValueError, match="target_stage"):
        UserProfile("user", "middle_school", True, "created", "updated")


def test_retrieval_text_is_deterministic_and_machine_formatted():
    from weilv.user_memory import build_retrieval_text

    first = build_retrieval_text(_feedback())
    second = build_retrieval_text(
        _feedback(
            memory_value={
                "burden": "easy",
                "helpfulness": 4,
                "completion_status": "completed",
            }
        )
    )

    assert first == second == (
        "type=task_feedback\n"
        "task=MT-SED-001\n"
        "completion=completed\n"
        "burden=easy\n"
        "helpfulness=4"
    )


def test_structured_setting_retrieval_text_is_deterministic_for_nested_values():
    from weilv.user_memory import build_retrieval_text

    first = _feedback(
        memory_type="context_preference",
        source_type="explicit_user_setting",
        task_id=None,
        memory_key="context_preference",
        memory_value={"avoid_context": "school", "preferred_context": "home"},
    )
    second = _feedback(
        memory_type="context_preference",
        source_type="explicit_user_setting",
        task_id=None,
        memory_key="context_preference",
        memory_value={"preferred_context": "home", "avoid_context": "school"},
    )

    assert build_retrieval_text(first) == build_retrieval_text(second) == (
        'type=context_preference\nkey=context_preference\n'
        'value={"avoid_context":"school","preferred_context":"home"}'
    )

@pytest.mark.parametrize("raw_field", ["query", "chat_text", "raw_chat", "raw_query"])
def test_raw_query_or_chat_text_cannot_enter_retrieval_text(raw_field):
    from weilv.user_memory import build_retrieval_text

    candidate = _feedback(memory_value={**_feedback().memory_value, raw_field: "private raw text"})

    with pytest.raises(ValueError, match="forbidden persistence field"):
        build_retrieval_text(candidate)


def test_user_profile_and_memory_schemas_keep_only_v01_contract_fields():
    profile = _profile()
    candidate = _feedback()

    assert asdict(profile) == {
        "user_id": "usr_anon_001",
        "target_stage": "junior_high",
        "memory_enabled": True,
        "created_at": "2026-08-13T10:00:00+08:00",
        "updated_at": "2026-08-13T10:00:00+08:00",
    }
    assert set(asdict(candidate)) == {
        "memory_id",
        "user_id",
        "memory_type",
        "source_type",
        "task_id",
        "domain",
        "memory_key",
        "memory_value",
        "retrieval_text",
        "created_at",
        "updated_at",
        "active",
        "review_status",
        "embedding",
    }
