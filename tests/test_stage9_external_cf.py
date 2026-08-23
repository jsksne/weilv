"""Stage 9B external CF evaluator tests (synthetic fixtures).

Covers the frozen Stage 9A v1.1 external evaluator contract: base score
shrinkage, personal-signal fallback, cf_signal contributor/clipping rules,
SNIPS weights/ESS/value, deterministic tie order, bootstrap seed determinism,
zero-support -> NOT_EVALUABLE / CANNOT_BE_SUPPORTED, temporal leakage checks
(held-out user, future target, future source, post-response features),
PRECHECK mode never computing the formal result, and deterministic
reproducibility.  All fixtures are synthetic engineering evidence.
"""

import json
import math
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from evaluation.stage9.run_stage9_external_cf import (
    BOOTSTRAP_REPLICATES,
    BOOTSTRAP_SEED,
    CONTEXT_WHITELIST,
    MIN_CONTRIBUTORS,
    PredictionResult,
    _cosine_on_common,
    base_scores_from_stats,
    build_parser,
    compute_cf_signal,
    evaluate_all_folds,
    evaluate_claim,
    participant_bootstrap_ci,
    personal_signal,
    policy_choice,
    record_leakage_violations,
    run_precheck,
    run_synthetic_evaluator_tests,
    snips_metrics,
    verify_temporal_structure,
    zero_support_reason,
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
# Frozen model math
# ---------------------------------------------------------------------------

def test_base_scores_action_means_and_shrinkage():
    stats = {
        "y": np.array([10.0, 10.0, 10.0, 100.0]),
        "action": np.array([0, 0, 0, 1]),
        "slot": np.array([0, 1, 0, 0]),
        "activity": np.array([0, 0, 0, 0]),
        "location": np.array([0, 0, 0, 0]),
        "weather": np.array([0, 0, 0, 0]),
        "prior_steps": np.array([0, 0, 0, 0]),
        "week": np.array([0, 0, 0, 0]),
    }
    mask = np.ones(4, dtype=bool)
    context = {"slot": 0, "activity": 0, "location": 0, "weather": 0,
               "prior_steps": 0, "week": 0}
    base = base_scores_from_stats(stats, mask, context)
    assert base["none"] == pytest.approx(10.0)
    assert base["walking"] == pytest.approx(100.0)

    # shrinkage: action mean 20; slot0 cell mean 10 with n=1
    # -> adj = (10 - 20) * 1/11; base(slot0) = 20 - 10/11
    stats2 = {
        "y": np.array([10.0, 30.0]),
        "action": np.array([0, 0]),
        "slot": np.array([0, 1]),
        "activity": np.array([0, 0]),
        "location": np.array([0, 0]),
        "weather": np.array([0, 0]),
        "prior_steps": np.array([0, 0]),
        "week": np.array([0, 0]),
    }
    base2 = base_scores_from_stats(stats2, np.ones(2, dtype=bool), context)
    assert base2["none"] == pytest.approx(20.0 - 10.0 * (1 / 11))


def test_base_scores_empty_mask_falls_back_to_zero():
    stats = {
        "y": np.array([10.0]),
        "action": np.array([0]),
        "slot": np.array([0]),
        "activity": np.array([0]),
        "location": np.array([0]),
        "weather": np.array([0]),
        "prior_steps": np.array([0]),
        "week": np.array([0]),
    }
    base = base_scores_from_stats(stats, np.zeros(1, dtype=bool),
                                  {"slot": 0, "activity": 0, "location": 0,
                                   "weather": 0, "prior_steps": 0, "week": 0})
    assert base == {"none": 0.0, "walking": 0.0, "antisedentary": 0.0}


def test_personal_signal_fallback_chain():
    cells = {(0, 0): (2.0, 5)}
    actions = {0: (1.0, 3)}
    overall = (0.5, 10)
    # exact cell preferred
    assert personal_signal(cells, actions, overall, 0, 0) == pytest.approx(
        2.0 * 5 / 15
    )
    # fallback to action
    assert personal_signal(cells, actions, overall, 0, 4) == pytest.approx(
        1.0 * 3 / 13
    )
    # fallback to overall
    assert personal_signal(cells, actions, overall, 1, 4) == pytest.approx(
        0.5 * 10 / 20
    )
    # no history at all -> 0
    assert personal_signal({}, {}, None, 1, 4) == 0.0


def test_cf_signal_requires_three_contributors_and_clips():
    target_cells = {(0, 0): (1.0, 5), (0, 1): (2.0, 5), (0, 2): (3.0, 5)}
    source_cells = {
        1: {(0, 0): (0.5, 4), (0, 1): (1.5, 4), (0, 2): (2.5, 4)},
        2: {(0, 0): (0.4, 4), (0, 1): (1.4, 4), (0, 2): (2.4, 4)},
        3: {(0, 0): (0.6, 4), (0, 1): (1.6, 4), (0, 2): (2.6, 4)},
    }
    cf, neighbors = compute_cf_signal(target_cells, source_cells, (0, 0), (-10.0, 10.0))
    assert cf != 0.0
    assert neighbors >= MIN_CONTRIBUTORS

    # fewer than three contributors -> 0
    cf_sparse, _ = compute_cf_signal(
        target_cells, {1: source_cells[1], 2: source_cells[2]}, (0, 0), (-10.0, 10.0)
    )
    assert cf_sparse == 0.0

    # clipping to the source residual percentiles
    clipped, _ = compute_cf_signal(target_cells, source_cells, (0, 0), (-0.1, 0.1))
    assert -0.1 <= clipped <= 0.1


def test_cf_signal_weights_align_with_contributors():
    """Regression (audit BLOCKER): when a top-5 neighbor lacks the requested
    cell, its similarity must not weight another contributor's mean."""
    target_cells = {
        (0, 0): (1.0, 5), (0, 1): (2.0, 5), (0, 2): (3.0, 5),
        (0, 3): (4.0, 5), (0, 4): (5.0, 5),
    }
    # users 1-3 are contributors (have (0,0)) but weakly similar; user 4 is
    # the MOST similar neighbor yet lacks the requested cell (0,0)
    source_cells = {
        1: {(0, 0): (0.1, 4), (0, 1): (5.0, 4), (0, 2): (0.5, 4),
            (0, 3): (0.5, 4), (0, 4): (0.5, 4)},
        2: {(0, 0): (0.2, 4), (0, 1): (5.0, 4), (0, 2): (0.5, 4),
            (0, 3): (0.5, 4), (0, 4): (0.5, 4)},
        3: {(0, 0): (0.3, 4), (0, 1): (5.0, 4), (0, 2): (0.5, 4),
            (0, 3): (0.5, 4), (0, 4): (0.5, 4)},
        4: {(0, 1): (2.0, 4), (0, 2): (3.0, 4), (0, 3): (4.0, 4)},  # no (0,0)
    }
    cf, _ = compute_cf_signal(target_cells, source_cells, (0, 0), (-10.0, 10.0))

    target_vec = {key: value[0] for key, value in target_cells.items()}
    sims = {}
    for uid, cells in source_cells.items():
        source_vec = {key: value[0] for key, value in cells.items() if value[1] > 0}
        cosine, n_common = _cosine_on_common(target_vec, source_vec)
        if n_common >= MIN_CONTRIBUTORS and cosine > 0:
            sims[uid] = cosine * (n_common / (n_common + 10))
    top5 = sorted(sims, key=sims.get, reverse=True)[:5]
    assert top5[0] == 4  # the cell-less neighbor ranks FIRST
    contributors = [uid for uid in top5 if (0, 0) in source_cells[uid]]
    means = [source_cells[uid][(0, 0)][0] for uid in contributors]
    weights = [sims[uid] for uid in contributors]
    expected = float(np.average(means, weights=weights))
    assert cf == pytest.approx(expected, rel=1e-9)
    # the pre-fix misalignment would weight means by a prefix of neighbor sims
    old = float(np.average(means, weights=[sims[uid] for uid in top5][: len(means)]))
    assert not math.isclose(cf, old, rel_tol=1e-9)


def test_policy_tie_order_none_antisedentary_walking():
    assert policy_choice({"none": 5.0, "walking": 5.0, "antisedentary": 5.0}) == "none"
    assert policy_choice({"none": 4.0, "walking": 5.0, "antisedentary": 5.0}) == "antisedentary"
    assert policy_choice({"none": 4.0, "walking": 5.0, "antisedentary": 4.0}) == "walking"


# ---------------------------------------------------------------------------
# SNIPS
# ---------------------------------------------------------------------------

def _prediction(action, y, policy=("walking", "walking")):
    return PredictionResult(
        target_user=1, prediction_utime=1.0, action=action, y=y, y_gf=None,
        raw_nonmissing=True, personal_scores={}, hybrid_scores={},
        policy_personal=policy[0], policy_cf=policy[1], cf_signal_by_action={},
        neighbor_count=0, history_max_utime=None, source_max_rel_time=None,
    )


def test_snips_exact_weights_value_ess():
    predictions = [
        _prediction("none", 0.5, ("none", "none")),
        _prediction("walking", 1.5, ("walking", "walking")),
        _prediction("antisedentary", 2.5, ("antisedentary", "antisedentary")),
    ]
    metrics = snips_metrics(predictions, "policy_cf")
    weights = [1 / 0.4, 1 / 0.3, 1 / 0.3]
    expected_value = sum(w * y for w, y in zip(weights, [0.5, 1.5, 2.5])) / sum(weights)
    expected_ess = sum(weights) ** 2 / sum(w * w for w in weights)
    assert metrics["value"] == pytest.approx(expected_value, rel=1e-9)
    assert metrics["ess"] == pytest.approx(expected_ess, rel=1e-9)
    assert metrics["denominator"] == pytest.approx(sum(weights))


def test_snips_zero_weight_when_policy_mismatch():
    predictions = [_prediction("walking", 1.5, ("none", "none"))]
    metrics = snips_metrics(predictions, "policy_cf")
    assert metrics["denominator"] == 0.0
    assert metrics["ess"] == 0.0
    assert zero_support_reason(metrics) is not None


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def test_bootstrap_seed_determinism_and_replicates():
    deltas = [0.1 * (index % 5) - 0.05 for index in range(37)]
    first = participant_bootstrap_ci(deltas, seed=BOOTSTRAP_SEED, replicates=200)
    second = participant_bootstrap_ci(deltas, seed=BOOTSTRAP_SEED, replicates=200)
    assert first == second
    assert first["mean"] == pytest.approx(np.mean(deltas))
    assert first["replicates"] == 200
    assert first["seed"] == BOOTSTRAP_SEED


# ---------------------------------------------------------------------------
# CR-CF-001 mechanical claim evaluation
# ---------------------------------------------------------------------------

def test_claim_mechanics():
    assert evaluate_claim(0.5, 0.1, [], True) == ("EVALUATED", "SUPPORTED", None)
    status, claim, reason = evaluate_claim(0.5, 0.1, [7], True)
    assert status == "NOT_EVALUABLE" and claim == "CANNOT_BE_SUPPORTED"
    assert "zero_support" in reason
    assert evaluate_claim(-0.1, 0.1, [], True) == ("EVALUATED", "UNSUPPORTED",
                                                   "delta_not_greater_than_zero")
    assert evaluate_claim(0.1, -0.2, [], True) == (
        "EVALUATED", "UNSUPPORTED", "bootstrap_ci_lower_not_greater_than_zero"
    )
    assert evaluate_claim(0.1, 0.05, [], False) == (
        "EVALUATED", "UNSUPPORTED", "integrity_gates_failed"
    )


# ---------------------------------------------------------------------------
# Synthetic cohort + full driver
# ---------------------------------------------------------------------------

ACTIONS_CYCLE = ("none", "walking", "antisedentary")
LOCATIONS = ("home", "work", "other")
WEATHERS = ("sunny", "rain", "cloudy")
ACTIVITIES = ("STILL", "ON_FOOT", "IN_VEHICLE")


def _analysis_row(user, decision, day, slot, action, steps=None):
    if steps is None:
        steps = 40 + (user * 7 + decision * 3) % 60
    rel = (day - 1) * 86400 + (slot - 1) * 3600
    return {
        "user_index": user,
        "decision_index": decision,
        "decision_utime": datetime(2020, 1, 1, tzinfo=UTC).isoformat(),
        "decision_utime_epoch": rel + user * 100000.0,
        "decision_slot": slot,
        "is_randomized": True,
        "action": action,
        "avail": True,
        "study_day": day,
        "study_week": (day - 1) // 7 + 1,
        "rel_time_seconds": float(rel),
        "activity_bucket": ACTIVITIES[(user + slot) % 3],
        "location_bucket": LOCATIONS[(user + day) % 3],
        "weather_bucket": WEATHERS[(slot + day) % 3],
        "prior_step_bucket": "1_199",
        "jbsteps30_raw": float(steps),
        "jbsteps30_zero": float(steps),
        "gfsteps30": float(steps),
        "y": math.log(steps + 0.5),
        "y_gf": math.log(steps + 0.5),
        "raw_outcome_nonmissing": True,
        "gf_outcome_nonmissing": True,
    }


def _synthetic_cohort(users=4, days=12, slots=3, eval_users=None):
    rows = []
    for user in range(1, users + 1):
        decision = 0
        for day in range(1, days + 1):
            for slot in range(1, slots + 1):
                decision += 1
                action = ACTIONS_CYCLE[(user + day + slot) % 3]
                rows.append(_analysis_row(user, decision, day, slot, action))
    return rows


def test_driver_runs_with_zero_leakage_violations():
    cohort = _synthetic_cohort()
    results = evaluate_all_folds(cohort, integrity_gates=None)
    assert results["leakage_violations"] == {
        "held_out_user_in_source": 0,
        "future_target_history": 0,
        "future_source_rows": 0,
        "post_response_features": 0,
    }
    assert len(results["participants"]) == 4
    for participant in results["participants"]:
        assert participant["eval_rows"] > 0


def test_held_out_user_never_in_source():
    cohort = _synthetic_cohort()
    results = evaluate_all_folds(cohort, integrity_gates=None)
    for assignment in results["fold_assignments"]:
        assert assignment["target_user"] not in assignment["source_users"]


def test_record_leakage_violations_detects_future_leaks():
    ok = _prediction("walking", 1.0)
    ok.prediction_utime = 100.0
    ok.history_max_utime = 90.0
    ok.source_max_rel_time = 80.0
    ok.context_keys = sorted(CONTEXT_WHITELIST)
    assert record_leakage_violations(ok, t_rel=100.0) == {
        "held_out_user_in_source": 0, "future_target_history": 0,
        "future_source_rows": 0, "post_response_features": 0,
    }

    leaky = _prediction("walking", 1.0)
    leaky.prediction_utime = 100.0
    leaky.history_max_utime = 100.0  # target history at t is forbidden
    leaky.source_max_rel_time = 150.0  # source row after t is forbidden
    leaky.context_keys = ["response"]  # post-response feature is forbidden
    violations = record_leakage_violations(leaky, t_rel=100.0)
    assert violations["future_target_history"] == 1
    assert violations["future_source_rows"] == 1
    assert violations["post_response_features"] == 1


def test_driver_is_deterministic():
    cohort = _synthetic_cohort()
    first = evaluate_all_folds(cohort, integrity_gates=None)
    second = evaluate_all_folds(cohort, integrity_gates=None)
    assert first["participants"] == second["participants"]
    assert first["fold_assignments"] == second["fold_assignments"]


def test_zero_support_makes_primary_not_evaluable():
    cohort = _synthetic_cohort(users=3, days=12, slots=3)
    # strip one user of all eval rows (days 8-12) -> zero-support participant
    stripped = [
        row for row in cohort
        if not (row["user_index"] == 3 and row["study_day"] >= 8)
    ]
    results = evaluate_all_folds(stripped, integrity_gates=None)
    assert results["zero_support_users"] == [3]
    assert results["evaluable"] is False
    assert results["primary_status"] == "NOT_EVALUABLE"
    assert results["claim"]["CR-CF-001"] == "CANNOT_BE_SUPPORTED"
    assert results["delta_v"] is None
    assert results["bootstrap"] is None


def test_synthetic_evaluator_tests_all_pass():
    for entry in run_synthetic_evaluator_tests():
        assert entry["passed"], entry["test"]


# ---------------------------------------------------------------------------
# PRECHECK never computes the formal result
# ---------------------------------------------------------------------------

def test_precheck_never_computes_formal_result(workdir):
    cohort = _synthetic_cohort(users=4, days=12, slots=3)
    gates = {
        "heartsteps_hashes": "PASS", "duplicates": 0, "users": 37,
        "raw_rows": 8274, "final_rows": 7540,
    }
    report = run_precheck(cohort, gates, workdir)
    assert report["formal_result_computed"] is False
    assert report["delta_v_computed"] is False
    assert report["ci_computed"] is False
    assert report["cr_cf_001_evaluated"] is False
    assert report["model_executed_on_real_data"] is False
    assert report["leakage_checks"]["total_violations"] == 0
    assert all(entry["passed"] for entry in report["synthetic_evaluator_tests"])
    persisted = json.loads(
        (workdir / "stage9_leakage_test_report_v1.json").read_text(encoding="utf-8")
    )
    # no numeric Delta_V / CI is persisted at the report top level (the
    # synthetic evaluator fixtures may exercise bootstrap on fake data)
    assert "delta_v" not in persisted
    assert "bootstrap" not in persisted
    assert "ci_lower" not in persisted
    assert "ci_upper" not in persisted


# ---------------------------------------------------------------------------
# Mode gating and full-pipeline serialization
# ---------------------------------------------------------------------------

def test_default_invocation_is_precheck():
    """Regression: the default runner invocation MUST be PRECHECK, never FORMAL."""
    args = build_parser().parse_args([])
    assert args.formal is False
    formal_args = build_parser().parse_args(["--formal"])
    assert formal_args.formal is True


def test_temporal_structure_verifier_detects_real_violations():
    cohort = _synthetic_cohort(users=4, days=12, slots=3)
    clean = verify_temporal_structure(cohort)
    assert clean["held_out_user_in_source"] == 0
    assert clean["post_response_features"] == 0
    assert clean["time_ordering_violations"] == 0
    assert clean["total_violations"] == 0 if "total_violations" in clean else True

    # a post-response column in the analysis table is a violation
    polluted = [dict(row, response="good") for row in cohort]
    assert verify_temporal_structure(polluted)["post_response_features"] == 1

    # a non-monotonic per-user timeline (duplicate decision timestamp) is a
    # data-quality violation that the strictly-causal masks rely on
    disordered = [dict(row) for row in cohort]
    user1_rows = [row for row in disordered if row["user_index"] == 1]
    user1_rows[1]["decision_utime_epoch"] = user1_rows[0]["decision_utime_epoch"]
    assert verify_temporal_structure(disordered)["time_ordering_violations"] >= 1


def test_base_scores_and_clips_exclude_future_source_rows():
    """Regression (audit B.2): base means and 5th/95th clips must be computed
    from source rows strictly before t; a future source row must not leak."""
    stats = {
        "y": np.array([10.0, 20.0, 1000.0]),
        "action": np.array([0, 0, 0]),
        "slot": np.array([0, 0, 0]),
        "activity": np.array([0, 0, 0]),
        "location": np.array([0, 0, 0]),
        "weather": np.array([0, 0, 0]),
        "prior_steps": np.array([0, 0, 0]),
        "week": np.array([0, 0, 0]),
        "rel_time": np.array([1.0, 2.0, 10.0]),
    }
    context = {"slot": 0, "activity": 0, "location": 0, "weather": 0,
               "prior_steps": 0, "week": 0}
    censored = base_scores_from_stats(stats, stats["rel_time"] < 2.5, context)
    full = base_scores_from_stats(stats, np.ones(3, dtype=bool), context)
    assert censored["none"] == pytest.approx(15.0)   # mean of 10,20 only
    assert full["none"] == pytest.approx(343.33, rel=1e-2)  # includes 1000
    assert censored["none"] != full["none"]
    # the 5th/95th clip percentiles are computed per t from the censored set
    # (numpy linear interpolation: p5 of [-5, 5] = -4.5, p95 = 4.5)
    censored_residuals = stats["y"][stats["rel_time"] < 2.5] - censored["none"]
    assert np.percentile(censored_residuals, 5) == pytest.approx(-4.5)
    assert np.percentile(censored_residuals, 95) == pytest.approx(4.5)


def test_precheck_never_invokes_the_model(monkeypatch, workdir):
    """Behavioral guard (audit gap): PRECHECK must not call the fold driver."""
    import evaluation.stage9.run_stage9_external_cf as runner_module

    cohort = _synthetic_cohort(users=4, days=12, slots=3)
    gates = {"heartsteps_hashes": "PASS", "duplicates": 0, "users": 37,
             "raw_rows": 8274, "final_rows": 7540}

    def _forbidden(*args, **kwargs):
        raise AssertionError("PRECHECK must not execute the fold driver")

    monkeypatch.setattr(runner_module, "evaluate_all_folds", _forbidden)
    report = run_precheck(cohort, gates, workdir)
    assert report["model_executed_on_real_data"] is False


def test_bootstrap_replicate_constant_is_frozen():
    assert BOOTSTRAP_REPLICATES == 10000


def test_randtrue_secondary_sensitivity_present():
    cohort = _synthetic_cohort(users=4, days=12, slots=3)
    results = evaluate_all_folds(cohort, integrity_gates=None)
    for participant in results["participants"]:
        assert "randtrue_v_cf" in participant
        assert "randtrue_eval_rows" in participant
        assert participant["randtrue_eval_rows"] >= 0



def test_full_pipeline_preprocessor_to_evaluator(workdir):
    """End-to-end: synthetic cache -> preprocessing -> analysis CSV ->
    typed round-trip -> 37-fold driver runs with zero leakage violations."""
    import csv as csv_module

    from evaluation.stage9.preprocess_heartsteps_v1 import (
        run_preprocessing,
    )

    cache = workdir / "cache"
    out = workdir / "preformal"
    # build a small synthetic cache with the real column names
    cache.mkdir(exist_ok=True)
    with open(cache / "users.csv", "w", encoding="utf-8", newline="") as handle:
        writer = csv_module.DictWriter(
            handle, fieldnames=["user.index", "age", "gender", "totaldays"]
        )
        writer.writeheader()
        for uid in range(1, 5):
            writer.writerow({"user.index": str(uid), "age": "30", "gender": "female",
                             "totaldays": "42"})
    header = [
        "user.index", "decision.index", "decision.index.nogap",
        "sugg.decision.utime", "sugg.decision.slot", "is.randomized", "avail",
        "send", "send.active", "send.sedentary", "recognized.activity",
        "dec.location.category", "dec.weather.condition", "jbsteps30pre",
        "jbsteps30", "jbsteps30.zero", "gfsteps30",
    ]
    rows = []
    for uid in range(1, 5):
        for day in range(1, 13):
            for slot in range(1, 4):
                action = ("none", "walking", "antisedentary")[(uid + day + slot) % 3]
                send, active, sedentary = {
                    "none": ("False", "False", "False"),
                    "walking": ("True", "True", "False"),
                    "antisedentary": ("True", "False", "True"),
                }[action]
                rows.append({
                    "user.index": str(uid),
                    "decision.index": str(day * 3 + slot),
                    "decision.index.nogap": str(day * 3 + slot),
                    "sugg.decision.utime": f"2020-01-{day:02d} {8 + slot:02d}:00:00",
                    "sugg.decision.slot": str(slot),
                    "is.randomized": "True",
                    "avail": "True",
                    "send": send,
                    "send.active": active,
                    "send.sedentary": sedentary,
                    "recognized.activity": "STILL",
                    "dec.location.category": "home",
                    "dec.weather.condition": "sunny",
                    "jbsteps30pre": "120",
                    "jbsteps30": str(50 + day * 3 + slot),
                    "jbsteps30.zero": str(50 + day * 3 + slot),
                    "gfsteps30": str(40 + day * 3 + slot),
                })
    with open(cache / "suggestions.csv", "w", encoding="utf-8", newline="") as handle:
        writer = csv_module.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)
    for name in ("gfsteps.csv", "jbsteps.csv"):
        with open(cache / name, "w", encoding="utf-8", newline="") as handle:
            handle.write("user.index,steps.utime,steps\n")

    summary = run_preprocessing(cache, out, verify_hashes=False)
    assert summary["raw_rows"] == 144
    assert summary["final_primary_rows"] == 144

    # typed round-trip via the serialized analysis table
    from evaluation.stage9.preprocess_heartsteps_v1 import read_csv_rows
    typed = read_csv_rows(cache / "analysis_table_v1.csv")
    assert len(typed) == 144
    assert all(row["action"] in ("none", "walking", "antisedentary") for row in typed)

    # the evaluator consumes the typed rows with zero leakage violations
    results = evaluate_all_folds(typed, integrity_gates=None)
    assert results["leakage_violations"] == {
        "held_out_user_in_source": 0,
        "future_target_history": 0,
        "future_source_rows": 0,
        "post_response_features": 0,
    }
    assert len(results["participants"]) == 4


# ---------------------------------------------------------------------------
# Stage 9C.1 formal integrity-gate wiring repair (regression)
#
# Attempt #1 failed pre-computation because check_integrity_gates() returned
# no schema_ok key while run_formal() requires integrity_gates["schema_ok"]
# is True.  These tests prove the repaired _cli() computes check_schema()
# over the real analysis table and passes schema_ok into run_formal, that a
# valid schema reaches the gate as True, that an invalid schema blocks
# FORMAL fail-closed, and that none of the tests executes real model
# computation (run_formal / evaluate_all_folds are stubbed or guarded).
# ---------------------------------------------------------------------------

def _write_analysis_table(rows, path):
    import csv as csv_module
    fieldnames = list(rows[0].keys())
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv_module.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _formal_cli_run(monkeypatch, workdir, cohort, gates, stub_run_formal=True):
    """Drive the real _cli() FORMAL path with a synthetic analysis table.

    check_integrity_gates is stubbed (no real HeartSteps files needed);
    run_formal is stubbed when requested (no real CF computation).
    evaluate_all_folds is ALWAYS replaced with a forbidden stub so any real
    model execution fails the test loudly.  Returns the run_formal
    arguments captured when run_formal was stubbed.
    """
    import sys

    import evaluation.stage9.run_stage9_external_cf as runner_module

    table = workdir / "analysis_table_v1.csv"
    _write_analysis_table(cohort, table)
    captured = {}
    if stub_run_formal:
        def fake_run_formal(analysis_rows, integrity_gates, out_dir):
            captured["analysis_rows"] = list(analysis_rows)
            captured["integrity_gates"] = dict(integrity_gates)
            captured["out_dir"] = str(out_dir)
            return {"primary_status": "EVALUATED",
                    "claim": {"CR-CF-001": "UNSUPPORTED", "reason": "test-stub"}}
        monkeypatch.setattr(runner_module, "run_formal", fake_run_formal)
    monkeypatch.setattr(runner_module, "check_integrity_gates",
                        lambda *args, **kwargs: dict(gates))

    def _forbidden(*args, **kwargs):
        raise AssertionError("real formal computation is forbidden in this test")

    monkeypatch.setattr(runner_module, "evaluate_all_folds", _forbidden)
    monkeypatch.setattr(sys, "argv",
                        ["runner", "--formal", "--no-download",
                         "--analysis-table", str(table)])
    return captured


def test_formal_cli_passes_real_check_schema_result_to_run_formal(monkeypatch, workdir):
    import evaluation.stage9.run_stage9_external_cf as runner_module
    cohort = _synthetic_cohort(users=2, days=12, slots=3)
    gates = {"heartsteps_hashes": "PASS", "duplicates": 0, "users": 2,
             "raw_rows": 72, "final_rows": 72}
    captured = _formal_cli_run(monkeypatch, workdir, cohort, gates)
    assert runner_module._cli() == 0
    gates_seen = captured["integrity_gates"]
    assert "schema_ok" in gates_seen
    # the gate value is the REAL check_schema() result over the analysis
    # rows the CLI constructed, never a hardcoded constant
    expected = runner_module.check_schema(captured["analysis_rows"])["schema_ok"]
    assert gates_seen["schema_ok"] == expected


def test_valid_schema_schema_ok_true_reaches_formal_gate(monkeypatch, workdir):
    import evaluation.stage9.run_stage9_external_cf as runner_module
    cohort = _synthetic_cohort(users=2, days=12, slots=3)
    gates = {"heartsteps_hashes": "PASS", "duplicates": 0, "users": 2,
             "raw_rows": 72, "final_rows": 72}
    captured = _formal_cli_run(monkeypatch, workdir, cohort, gates)
    assert runner_module._cli() == 0
    assert captured["integrity_gates"]["schema_ok"] is True


def test_invalid_schema_schema_ok_false_blocks_formal(monkeypatch, workdir):
    import evaluation.stage9.run_stage9_external_cf as runner_module
    cohort = _synthetic_cohort(users=2, days=12, slots=3)
    # break the schema: study day outside the frozen 1..42 range
    cohort[0]["study_day"] = 99
    assert runner_module.check_schema(cohort)["schema_ok"] is False
    gates = {"heartsteps_hashes": "PASS", "duplicates": 0, "users": 2,
             "raw_rows": 72, "final_rows": 72}
    # the REAL run_formal is used: it must fail closed on schema_ok=False
    # before writing any run directory or executing the model
    _formal_cli_run(monkeypatch, workdir, cohort, gates, stub_run_formal=False)
    with pytest.raises(RuntimeError) as excinfo:
        runner_module._cli()
    assert "blocked by integrity gates" in str(excinfo.value)
    assert not list(Path("evaluation/runs").glob("*_stage9_formal"))


def test_formal_gate_wiring_tests_never_run_real_computation(monkeypatch, workdir):
    import evaluation.stage9.run_stage9_external_cf as runner_module
    cohort = _synthetic_cohort(users=2, days=12, slots=3)
    gates = {"heartsteps_hashes": "PASS", "duplicates": 0, "users": 2,
             "raw_rows": 72, "final_rows": 72}
    captured = _formal_cli_run(monkeypatch, workdir, cohort, gates)
    assert runner_module._cli() == 0
    # stubs did the work: no immutable formal run directory may exist
    assert not list(Path("evaluation/runs").glob("*_stage9_formal"))
    assert captured["integrity_gates"]["schema_ok"] is True


def test_precheck_cli_gates_unchanged_by_wiring_repair(monkeypatch, workdir):
    import sys

    import evaluation.stage9.run_stage9_external_cf as runner_module
    cohort = _synthetic_cohort(users=2, days=12, slots=3)
    table = workdir / "analysis_table_v1.csv"
    _write_analysis_table(cohort, table)
    captured = {}

    def fake_run_precheck(analysis_rows, integrity_gates, out_dir):
        captured["integrity_gates"] = dict(integrity_gates)
        return {"formal_result_computed": False}

    monkeypatch.setattr(runner_module, "check_integrity_gates",
                        lambda *args, **kwargs: {"heartsteps_hashes": "PASS",
                                                 "duplicates": 0, "users": 2,
                                                 "raw_rows": 72,
                                                 "final_rows": 72})
    monkeypatch.setattr(runner_module, "run_precheck", fake_run_precheck)
    monkeypatch.setattr(sys, "argv", ["runner", "--no-download",
                                     "--analysis-table", str(table)])
    assert runner_module._cli() == 0
    # PRECHECK must receive the gates exactly as before the repair
    assert "schema_ok" not in captured["integrity_gates"]
