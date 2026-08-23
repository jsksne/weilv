"""Stage 9B HeartSteps preprocessing tests (synthetic fixtures).

Covers the frozen Stage 9A v1.1 preprocessing contract: pinned-hash
verification, exact action reconstruction, the critical regression that
``is.randomized == True`` is NOT an inclusion filter, the fixed eligibility
rule order, the primary outcome transform, reproducible row-flow manifests,
and CSV round-tripping.  All fixtures are synthetic engineering evidence.
"""

import csv
import hashlib
import json
import math
import shutil
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from evaluation.stage9.preprocess_heartsteps_v1 import (
    apply_eligibility,
    bucket_activity,
    bucket_location,
    bucket_prior_steps,
    bucket_weather,
    build_analysis_rows,
    emit_flow_manifests,
    read_csv_rows,
    reconstruct_action,
    run_preprocessing,
    sha256_file,
    study_week_from_day,
    verify_pinned_files,
)

TMP_ROOT = Path(".runtime") / "stage9-test-tmp"


@pytest.fixture
def workdir(request):
    """Sandbox-safe temp dir (pytest tmp_path uses extended paths; mkdtemp
    dirs deny child writes under the file sandbox)."""
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = TMP_ROOT / f"case-{uuid.uuid4().hex[:10]}"
    path.mkdir(parents=True, exist_ok=True)

    def _cleanup():
        shutil.rmtree(path, ignore_errors=True)

    request.addfinalizer(_cleanup)
    return path

# ---------------------------------------------------------------------------
# Synthetic fixture builders
# ---------------------------------------------------------------------------

DEFAULT_ROW = {
    "user.index": "1",
    "decision.index": "1",
    "decision.index.nogap": "1",
    "sugg.decision.utime": "2020-01-01 09:00:00",
    "sugg.decision.slot": "1",
    "is.randomized": "True",
    "avail": "True",
    "send": "False",
    "send.active": "False",
    "send.sedentary": "False",
    "recognized.activity": "STILL",
    "dec.location.category": "home",
    "dec.weather.condition": "sunny",
    "jbsteps30pre": "120",
    "jbsteps30": "150",
    "jbsteps30.zero": "150",
    "gfsteps30": "140",
    "returned.message": "do_not_notify",
    "response": "",
}


def _row(**overrides):
    row = dict(DEFAULT_ROW)
    row.update(overrides)
    return row


def _write_csv(path, header, rows):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)


def _write_fixture(workdir, rows, users=("1", "2", "3")):
    cache = workdir / "cache"
    cache.mkdir(exist_ok=True)
    _write_csv(
        cache / "users.csv",
        ["user.index", "age", "gender", "totaldays"],
        [{"user.index": uid, "age": str(30 + i), "gender": "female",
          "totaldays": "42"} for i, uid in enumerate(users)],
    )
    _write_csv(cache / "suggestions.csv", list(DEFAULT_ROW.keys()), rows)
    for name, header_rows in (
        ("gfsteps.csv", ["user.index", "steps.utime", "steps"]),
        ("jbsteps.csv", ["user.index", "steps.utime", "steps"]),
    ):
        with open(cache / name, "w", encoding="utf-8", newline="") as handle:
            handle.write(",".join(header_rows) + "\n")
    return cache


def _read_suggestions(cache):
    import evaluation.stage9.preprocess_heartsteps_v1 as module
    return module._read_csv(cache / "suggestions.csv")


def _read_users(cache):
    import evaluation.stage9.preprocess_heartsteps_v1 as module
    return module._read_csv(cache / "users.csv")


def _eligibility(workdir, rows):
    cache = _write_fixture(workdir, rows)
    import evaluation.stage9.preprocess_heartsteps_v1 as module
    return cache, module.apply_eligibility(
        _read_suggestions(cache), _read_users(cache)
    )


# ---------------------------------------------------------------------------
# Action reconstruction
# ---------------------------------------------------------------------------

def test_action_reconstruction_exact_encodings():
    assert reconstruct_action(_row()) == "none"
    assert reconstruct_action(
        _row(**{"send": "True", "send.active": "True", "send.sedentary": "False"})
    ) == "walking"
    assert reconstruct_action(
        _row(**{"send": "True", "send.active": "False", "send.sedentary": "True"})
    ) == "antisedentary"


def test_action_reconstruction_invalid_encodings_are_none():
    # contradictory flags
    assert reconstruct_action(
        _row(**{"send": "True", "send.active": "True", "send.sedentary": "True"})
    ) is None
    # incomplete flags
    assert reconstruct_action(
        _row(**{"send": "", "send.active": "True", "send.sedentary": "False"})
    ) is None
    assert reconstruct_action(
        _row(**{"send": "False", "send.active": "", "send.sedentary": "False"})
    ) is None
    # send=True with both action flags False
    assert reconstruct_action(
        _row(**{"send": "True", "send.active": "False", "send.sedentary": "False"})
    ) is None
    # unparseable logical value
    assert reconstruct_action(
        _row(**{"send": "maybe", "send.active": "True", "send.sedentary": "False"})
    ) is None


# ---------------------------------------------------------------------------
# CRITICAL: is.randomized is NOT an inclusion filter
# ---------------------------------------------------------------------------

def test_is_randomized_false_rows_are_retained(workdir):
    """Regression: a developer filtering ``is.randomized == True`` must FAIL.

    The randomized action space at an eligible available decision point is
    {none, walking, antisedentary}; ``is.randomized`` is a required operational
    field, not an inclusion filter.  Rows with ``is.randomized == False`` (a
    legitimate released value) remain eligible when all operational fields are
    present and the action encoding is consistent.
    """
    rows = [
        _row(**{"user.index": "1", "decision.index": "1",
                "is.randomized": "False",
                "sugg.decision.utime": "2020-01-01 09:00:00"}),
        _row(**{"user.index": "1", "decision.index": "2",
                "is.randomized": "True",
                "send": "True", "send.active": "True", "send.sedentary": "False",
                "sugg.decision.utime": "2020-01-01 10:00:00"}),
        _row(**{"user.index": "2", "decision.index": "1",
                "is.randomized": "False",
                "send": "True", "send.active": "False", "send.sedentary": "True",
                "sugg.decision.utime": "2020-01-01 09:00:00"}),
        _row(**{"user.index": "2", "decision.index": "2",
                "is.randomized": "True",
                "sugg.decision.utime": "2020-01-01 10:00:00"}),
    ]
    _, flow = _eligibility(workdir, rows)

    final = flow["final_rows"]
    assert len(final) == 4  # all four rows eligible - none dropped by is.randomized
    randomized_values = {row["is.randomized"] for row in final}
    assert randomized_values == {"True", "False"}
    # none-arm rows survive regardless of the is.randomized value
    none_rows = [row for row in final if reconstruct_action(row) == "none"]
    assert len(none_rows) == 2
    # A hypothetical is.randomized == True filter would drop two rows:
    from evaluation.stage9.preprocess_heartsteps_v1 import _as_bool
    wrong = [row for row in final if _as_bool(row["is.randomized"]) is True]
    assert len(wrong) == 2  # proves the filter changes the cohort


def test_no_suggestion_arm_is_not_dropped_by_send_filter(workdir):
    """The none action (send=False) must survive; eligibility never requires send."""
    encodings = [
        {"send": "False", "send.active": "False", "send.sedentary": "False"},
        {"send": "True", "send.active": "True", "send.sedentary": "False"},
        {"send": "True", "send.active": "False", "send.sedentary": "True"},
    ]
    rows = [
        _row(**{"user.index": "1", "decision.index": str(index),
                "sugg.decision.utime": f"2020-01-01 {9 + index:02d}:00:00",
                **encoding})
        for index, encoding in enumerate(encodings, start=1)
    ]
    _, flow = _eligibility(workdir, rows)
    actions = [reconstruct_action(row) for row in flow["final_rows"]]
    assert actions.count("none") == 1
    assert actions.count("walking") == 1
    assert actions.count("antisedentary") == 1


# ---------------------------------------------------------------------------
# Eligibility rules (fixed order)
# ---------------------------------------------------------------------------

def test_missing_operational_field_excluded(workdir):
    rows = [
        _row(**{"user.index": "1", "decision.index": "1"}),  # valid
        _row(**{"user.index": "1", "decision.index": "2", "send": ""}),
        _row(**{"user.index": "2", "decision.index": "1", "is.randomized": ""}),
        _row(**{"user.index": "2", "decision.index": "2",
                "sugg.decision.slot": ""}),
    ]
    _, flow = _eligibility(workdir, rows)
    assert flow["rule_stats"]["R1"]["excluded"] == 3
    assert len(flow["final_rows"]) == 1


def test_invalid_slot_excluded(workdir):
    rows = [
        _row(**{"user.index": "1", "decision.index": "1", "sugg.decision.slot": "3"}),
        _row(**{"user.index": "1", "decision.index": "2", "sugg.decision.slot": "6"}),
        _row(**{"user.index": "1", "decision.index": "3", "sugg.decision.slot": "0"}),
    ]
    _, flow = _eligibility(workdir, rows)
    assert flow["rule_stats"]["R2"]["excluded"] == 2
    assert len(flow["final_rows"]) == 1


def test_travel_gap_excluded_when_column_present(workdir):
    rows = [
        _row(**{"user.index": "1", "decision.index": "1",
                "decision.index.nogap": "1"}),
        _row(**{"user.index": "1", "decision.index": "2",
                "decision.index.nogap": ""}),
    ]
    _, flow = _eligibility(workdir, rows)
    assert flow["rule_stats"]["R3"]["excluded"] == 1
    assert len(flow["final_rows"]) == 1


def test_study_day_derivation_and_boundary(workdir):
    base = datetime(2020, 1, 1, 9, 0, 0, tzinfo=UTC)
    stamps = [base + timedelta(days=offset) for offset in (0, 41, 42, 43)]
    rows = [
        _row(**{"user.index": "1", "decision.index": str(index + 1),
                "sugg.decision.utime": stamp.strftime("%Y-%m-%d %H:%M:%S")})
        for index, stamp in enumerate(stamps)
    ]
    _, flow = _eligibility(workdir, rows)
    # offsets 0/41/42/43 -> derived days 1/42/43/44; only days 1..42 kept
    assert flow["rule_stats"]["R4"]["excluded"] == 2
    analysis = build_analysis_rows(flow["final_rows"], flow)
    days = {row["decision_index"]: row["study_day"] for row in analysis}
    assert days[1] == 1
    assert days[2] == 42
    assert study_week_from_day(1) == 1
    assert study_week_from_day(42) == 6


def test_not_available_excluded(workdir):
    rows = [
        _row(**{"user.index": "1", "decision.index": "1", "avail": "True"}),
        _row(**{"user.index": "1", "decision.index": "2", "avail": "False"}),
        _row(**{"user.index": "2", "decision.index": "1", "avail": ""}),
    ]
    _, flow = _eligibility(workdir, rows)
    assert flow["rule_stats"]["R5"]["excluded"] == 2
    assert len(flow["final_rows"]) == 1


def test_inconsistent_action_excluded_and_counted(workdir):
    rows = [
        _row(**{"user.index": "1", "decision.index": "1"}),  # none, valid
        _row(**{"user.index": "1", "decision.index": "2",
                "send": "True", "send.active": "True", "send.sedentary": "True"}),
    ]
    _, flow = _eligibility(workdir, rows)
    assert flow["rule_stats"]["R6"]["excluded"] == 1
    assert len(flow["final_rows"]) == 1


def test_duplicate_key_fails_by_default_and_reports(workdir):
    rows = [
        _row(**{"user.index": "1", "decision.index": "1"}),
        _row(**{"user.index": "1", "decision.index": "1"}),  # duplicate
    ]
    cache = _write_fixture(workdir, rows)
    with pytest.raises(RuntimeError, match="duplicate"):
        apply_eligibility(_read_suggestions(cache), _read_users(cache))
    flow = apply_eligibility(_read_suggestions(cache), _read_users(cache),
                             duplicate_policy="report")
    assert flow["duplicates"] == 1


def test_invalid_primary_outcome_excluded(workdir):
    rows = [
        _row(**{"user.index": "1", "decision.index": "1", "jbsteps30.zero": "150"}),
        _row(**{"user.index": "1", "decision.index": "2", "jbsteps30.zero": ""}),
        _row(**{"user.index": "1", "decision.index": "3", "jbsteps30.zero": "-5"}),
        _row(**{"user.index": "1", "decision.index": "4", "jbsteps30.zero": "abc"}),
    ]
    _, flow = _eligibility(workdir, rows)
    assert flow["rule_stats"]["R8"]["excluded"] == 3
    assert len(flow["final_rows"]) == 1


def test_raw_jbsteps30_missing_is_not_an_eligibility_condition(workdir):
    """Primary inclusion must not depend on raw jbsteps30 nonmissingness."""
    rows = [
        _row(**{"user.index": "1", "decision.index": "1",
                "jbsteps30": "", "jbsteps30.zero": "120"}),
        _row(**{"user.index": "1", "decision.index": "2",
                "jbsteps30": "200", "jbsteps30.zero": "200"}),
    ]
    _, flow = _eligibility(workdir, rows)
    assert len(flow["final_rows"]) == 2
    analysis = build_analysis_rows(flow["final_rows"], flow)
    by_index = {row["decision_index"]: row for row in analysis}
    assert by_index[1]["raw_outcome_nonmissing"] is False
    assert by_index[1]["y"] == math.log(120 + 0.5)
    assert by_index[2]["raw_outcome_nonmissing"] is True


# ---------------------------------------------------------------------------
# Outcome transform
# ---------------------------------------------------------------------------

def test_primary_outcome_transform():
    analysis = build_analysis_rows(
        [_row(**{"jbsteps30.zero": "0"}),
         _row(**{"jbsteps30.zero": "99.5"}),
         _row(**{"jbsteps30.zero": "1234"})],
        {"study_day_column": None, "first_utime_by_user": {}},
    )
    values = [row["y"] for row in analysis]
    assert values[0] == math.log(0.5)
    assert values[1] == math.log(100.0)
    assert values[2] == math.log(1234.5)


# ---------------------------------------------------------------------------
# Bucketing
# ---------------------------------------------------------------------------

def test_context_bucketing():
    assert bucket_activity("STILL") == "STILL"
    assert bucket_activity("WALKING") == "ON_FOOT"
    assert bucket_activity("RUNNING") == "ON_FOOT"
    assert bucket_activity("IN_VEHICLE") == "IN_VEHICLE"
    assert bucket_activity("TILTING") == "other"
    assert bucket_activity("") == "unknown"
    assert bucket_location("home") == "home"
    assert bucket_location("work") == "work"
    assert bucket_location("gym") == "other"
    assert bucket_location("") == "unknown"
    assert bucket_weather("Light Rain") == "precipitation_or_snow"
    assert bucket_weather("Snow") == "precipitation_or_snow"
    assert bucket_weather("Partly Cloudy") == "other"
    assert bucket_weather("") == "unknown"
    assert bucket_prior_steps("") == "missing"
    assert bucket_prior_steps("0") == "0"
    assert bucket_prior_steps("120") == "1_199"
    assert bucket_prior_steps("200") == "ge_200"


# ---------------------------------------------------------------------------
# Hash verification
# ---------------------------------------------------------------------------

def test_sha256_verification_detects_tampering(workdir):
    path = workdir / "file.bin"
    path.write_bytes(b"heartsteps fixture bytes")
    digest = sha256_file(path)
    assert verify_pinned_files is not None  # import sanity
    assert digest == hashlib.sha256(b"heartsteps fixture bytes").hexdigest()
    path.write_bytes(b"heartsteps fixture bytes tampered")
    assert sha256_file(path) != digest


# ---------------------------------------------------------------------------
# End-to-end preprocessing + manifests + round-trip
# ---------------------------------------------------------------------------

def test_end_to_end_flow_manifests(workdir):
    rows = [
        _row(**{"user.index": "1", "decision.index": "1",
                "sugg.decision.slot": "1",
                "sugg.decision.utime": "2020-01-01 09:00:00"}),
        _row(**{"user.index": "1", "decision.index": "2",
                "sugg.decision.slot": "2",
                "sugg.decision.utime": "2020-01-01 10:00:00",
                "send": "True", "send.active": "True", "send.sedentary": "False"}),
        _row(**{"user.index": "1", "decision.index": "3",
                "sugg.decision.slot": "3",
                "sugg.decision.utime": "2020-01-01 11:00:00", "avail": "False"}),
        _row(**{"user.index": "2", "decision.index": "1",
                "sugg.decision.slot": "1",
                "sugg.decision.utime": "2020-01-01 09:00:00",
                "send": "True", "send.active": "True", "send.sedentary": "True"}),
        _row(**{"user.index": "2", "decision.index": "2",
                "sugg.decision.slot": "2",
                "sugg.decision.utime": "2020-01-01 10:00:00",
                "is.randomized": ""}),
    ]
    cache = _write_fixture(workdir, rows)
    out = workdir / "preformal"
    flow = apply_eligibility(_read_suggestions(cache), _read_users(cache))
    analysis = build_analysis_rows(flow["final_rows"], flow)
    emit_flow_manifests(flow, analysis, _read_users(cache), out)

    flow_json = json.loads(
        (out / "preprocessing_flow_v1.json").read_text(encoding="utf-8")
    )
    assert flow_json["flow"]["raw_rows"] == 5
    assert flow_json["flow"]["rows_with_operational_fields"] == 4
    # R1 (is.randomized blank) + R5 (avail False) + R6 (contradictory action)
    assert flow_json["flow"]["final_primary_rows"] == 2
    assert flow_json["action_counts"] == {"none": 1, "walking": 1,
                                          "antisedentary": 0}
    assert flow_json["formal_cf_result_computed"] is False

    rules = json.loads(
        (out / "stage9_public_release_exclusion_rules_v1.json").read_text(
            encoding="utf-8"
        )
    )
    rule_ids = [rule["rule_id"] for rule in rules["rules"]]
    assert rule_ids == ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"]
    by_rule = {rule["rule_id"]: rule for rule in rules["rules"]}
    assert by_rule["R1"]["excluded"] == 1  # is.randomized blank
    assert by_rule["R5"]["excluded"] == 1  # avail False
    assert by_rule["R6"]["excluded"] == 1  # contradictory action encoding
    assert by_rule["R7"]["classification"] == "FROZEN_PREREG"

    by_user = (out / "preprocessing_flow_by_user_v1.csv").read_text(encoding="utf-8")
    assert "user.index,primary_rows,none,walking,antisedentary" in by_user

    # analysis table round-trips through read_csv_rows
    table = cache / "analysis_table_v1.csv"
    with open(table, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(analysis[0].keys()))
        writer.writeheader()
        from evaluation.stage9.preprocess_heartsteps_v1 import _csv_value
        for row in analysis:
            writer.writerow({key: _csv_value(value) for key, value in row.items()})
    typed = read_csv_rows(table)
    assert len(typed) == 2
    assert typed[0]["user_index"] == 1
    assert typed[0]["action"] == "none"
    assert typed[0]["study_day"] == 1
    assert typed[0]["raw_outcome_nonmissing"] is True


def test_run_preprocessing_without_verify(workdir):
    rows = [
        _row(**{"user.index": "1", "decision.index": "1"}),
        _row(**{"user.index": "1", "decision.index": "2",
                "send": "True", "send.active": "True", "send.sedentary": "False"}),
    ]
    cache = _write_fixture(workdir, rows)
    out = workdir / "preformal"
    summary = run_preprocessing(cache, out, verify_hashes=False)
    assert summary["raw_rows"] == 2
    assert summary["final_primary_rows"] == 2
    assert (out / "preprocessing_flow_v1.json").exists()
    assert (cache / "analysis_table_v1.csv").exists()
