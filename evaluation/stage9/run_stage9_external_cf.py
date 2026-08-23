"""Stage 9B external CF evaluator: LOPO temporal evaluation (frozen v1.1).

Implements the frozen Stage 9A v1.1 DESIGN C external mechanism validation:

- 37-fold leave-one-participant-out; the held-out participant is NEVER in
  source fitting or neighbor construction.
- Days 1-7 of the target participant = adaptation history only; days 8-42 are
  evaluation decisions.
- Strict pre-prediction temporal censoring: at prediction time t the target
  history contains only events strictly before t and source histories are
  censored to source relative study time strictly earlier than t.  This applies
  to ALL source-derived objects: base context means, action means, residual
  means, neighbor vectors, similarity, fallback means, residual-clipping
  percentiles and neighbor contributions (online warm-start rule).
- Frozen model: additive smoothed context means (shrinkage n/(n+10)); target
  strictly-prior residual personal signal (action x slot -> action -> overall
  fallback); user-neighborhood residual on action x decision-slot cells with
  cosine similarity on co-observed cells, shrunk n_common/(n_common+10),
  >=3 common cells, positive only, max 5 neighbors, >=3 contributors per cell,
  source-history-only 5th/95th residual clipping; hybrid = base + personal +
  cf, comparator = base + personal.  No alpha, no test-result tuning.
- SNIPS: w_t = I(A_t == pi(X_t)) / p(A_t | X_t) with p(none)=0.4,
  p(walking)=0.3, p(antisedentary)=0.3; V_u = sum(w*y)/sum(w);
  ESS_u = (sum w)^2 / sum(w^2); Delta_V = mean_u(V(plus_cf) - V(personal));
  participant-level paired bootstrap, 10,000 replicates, seed 20260818,
  percentile 95% CI.
- Zero support (sum w == 0 or ESS == 0 for either primary policy) retains the
  participant, never imputes, and makes the aggregate primary comparison
  NOT_EVALUABLE with CR-CF-001 CANNOT_BE_SUPPORTED.
- CR-CF-001 is evaluated mechanically, never hardcoded.
- Two modes: PRECHECK (default) verifies data, runs preprocessing, schema,
  leakage and synthetic evaluator tests but NEVER computes the real CF result;
  FORMAL (--formal) may compute the real Delta_V / CI / CR-CF-001.
"""

from __future__ import annotations

import argparse
import csv as csv_module
import hashlib
import itertools
import json
import math
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from evaluation.stage9.preprocess_heartsteps_v1 import (
    ACTIONS,
    ASSIGNMENT_PROBABILITIES,
    PINNED_COMMIT,
    PINNED_FILES,
    _read_csv,
    apply_eligibility,
    build_analysis_rows,
    download_pinned_files,
    emit_flow_manifests,
    verify_pinned_files,
)

# ---------------------------------------------------------------------------
# Frozen constants (Stage 9A v1.1)
# ---------------------------------------------------------------------------

BOOTSTRAP_REPLICATES = 10000
BOOTSTRAP_SEED = 20260818
SHRINKAGE_DENOM = 10.0
MIN_COMMON_CELLS = 3
MAX_NEIGHBORS = 5
MIN_CONTRIBUTORS = 3
SCORE_TIE_ORDER = ("none", "antisedentary", "walking")
TARGET_ADAPTATION_DAYS = (1, 7)
TARGET_TEST_DAYS = (8, 42)

ACTIVITY_CODES = ("STILL", "ON_FOOT", "IN_VEHICLE", "other", "unknown")
LOCATION_CODES = ("home", "work", "other", "unknown")
WEATHER_CODES = ("precipitation_or_snow", "other", "unknown")
PRIOR_CODES = ("missing", "0", "1_199", "ge_200")

CONTEXT_FEATURES = ("slot", "activity", "location", "weather", "prior_steps", "week")
CONTEXT_WHITELIST = set(CONTEXT_FEATURES)

CELL_COUNT = len(ACTIONS) * 5  # action x decision-slot cells

POLICY_PERSONAL = "EXTERNAL_PERSONAL_HISTORY"
POLICY_PLUS_CF = "EXTERNAL_PERSONAL_PLUS_CF"

METHOD_INTERPRETATION = (
    "ONE-STEP CONTEXTUAL OFF-POLICY VALUE UNDER THE RANDOMIZED "
    "LOGGED-HISTORY DISTRIBUTION"
)

FEATURE_CARDINALITY: dict[str, int] = {
    "slot": 5,
    "activity": len(ACTIVITY_CODES),
    "location": len(LOCATION_CODES),
    "weather": len(WEATHER_CODES),
    "prior_steps": len(PRIOR_CODES),
    "week": 6,
}

# ---------------------------------------------------------------------------
# Pre-registration amendments (v1.1 operational decisions, frozen pre-formal)
# ---------------------------------------------------------------------------

PREREGISTRATION_AMENDMENTS = [
    {
        "amendment": "AM-001",
        "title": "is.randomized SNIPS scope",
        "decision": (
            "The released field is.randomized is a required nonblank "
            "OPERATIONAL/data-quality field per the frozen v1.1 ticket; it is "
            "never used as an inclusion filter (the randomized action space at "
            "an eligible available decision point is none/walking/antisedentary "
            "with p=0.4/0.3/0.3).  The primary SNIPS estimand therefore covers "
            "all primary-cohort rows.  As a sensitivity, SNIPS restricted to "
            "rows with is.randomized == True is reported as a SECONDARY metric "
            "and never affects the primary claim."
        ),
    },
]


# ---------------------------------------------------------------------------
# Context coding
# ---------------------------------------------------------------------------

def _feature_code(feature: str, value: Any) -> int:
    if feature == "slot":
        if value is None:
            return 4
        return max(0, min(4, int(value) - 1))
    if feature == "activity":
        return ACTIVITY_CODES.index(value) if value in ACTIVITY_CODES else 4
    if feature == "location":
        return LOCATION_CODES.index(value) if value in LOCATION_CODES else 3
    if feature == "weather":
        return WEATHER_CODES.index(value) if value in WEATHER_CODES else 2
    if feature == "prior_steps":
        return PRIOR_CODES.index(value) if value in PRIOR_CODES else 0
    if feature == "week":
        if value is None:
            return 0
        return max(0, min(5, int(value) - 1))
    raise KeyError(feature)


def _context_codes(row: dict[str, Any]) -> dict[str, int]:
    return {
        "slot": _feature_code("slot", row.get("decision_slot")),
        "activity": _feature_code("activity", row.get("activity_bucket")),
        "location": _feature_code("location", row.get("location_bucket")),
        "weather": _feature_code("weather", row.get("weather_bucket")),
        "prior_steps": _feature_code("prior_steps", row.get("prior_step_bucket")),
        "week": _feature_code("week", row.get("study_week")),
    }


# ---------------------------------------------------------------------------
# Base score (additive smoothed action/context means)
# ---------------------------------------------------------------------------

def _base_components(
    stats: dict[str, np.ndarray], mask: np.ndarray
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """(action_means, adj_tables) from the censored source rows.

    action_means[a] falls back to the global source mean, then 0 when the mask
    is empty.  adj_tables[f][a*card + v] is the shrunk adjustment for feature f,
    action a, value v: (cell_mean - action_mean) * n/(n+10).
    """
    y = stats["y"][mask]
    action = stats["action"][mask]
    if y.size == 0:
        action_means = np.zeros(3, dtype=float)
    else:
        global_mean = float(y.mean())
        sums = np.bincount(action, weights=y, minlength=3)
        counts = np.bincount(action, minlength=3)
        action_means = np.where(counts > 0, sums / np.maximum(counts, 1), global_mean)
    adj_tables: dict[str, np.ndarray] = {}
    for feature in CONTEXT_FEATURES:
        card = FEATURE_CARDINALITY[feature]
        if y.size == 0:
            adj_tables[feature] = np.zeros(3 * card, dtype=float)
            continue
        values = stats[feature][mask]
        combined = action * card + values
        cell_sums = np.bincount(combined, weights=y, minlength=3 * card)
        cell_counts = np.bincount(combined, minlength=3 * card)
        cell_means = np.where(
            cell_counts > 0, cell_sums / np.maximum(cell_counts, 1), 0.0
        )
        action_of_cell = np.arange(3 * card) // card
        adjustment = np.where(
            cell_counts > 0,
            (cell_means - action_means[action_of_cell])
            * (cell_counts / (cell_counts + SHRINKAGE_DENOM)),
            0.0,
        )
        adj_tables[feature] = adjustment
    return action_means, adj_tables


def base_for_context(
    action_means: np.ndarray,
    adj_tables: dict[str, np.ndarray],
    action_index: int,
    context: dict[str, int],
) -> float:
    score = float(action_means[action_index])
    for feature in CONTEXT_FEATURES:
        card = FEATURE_CARDINALITY[feature]
        score += float(adj_tables[feature][action_index * card + context[feature]])
    return score


def base_array_for_rows(
    action_means: np.ndarray,
    adj_tables: dict[str, np.ndarray],
    action_codes: np.ndarray,
    feature_values: dict[str, np.ndarray],
) -> np.ndarray:
    base = action_means[action_codes].copy()
    for feature in CONTEXT_FEATURES:
        card = FEATURE_CARDINALITY[feature]
        base = base + adj_tables[feature][action_codes * card + feature_values[feature]]
    return base


def base_scores_from_stats(
    stats: dict[str, np.ndarray], mask: np.ndarray, context: dict[str, int]
) -> dict[str, float]:
    """Scalar base scores for one context (used by tests and history rows)."""
    action_means, adj_tables = _base_components(stats, mask)
    return {
        action: base_for_context(action_means, adj_tables, index, context)
        for index, action in enumerate(ACTIONS)
    }


# ---------------------------------------------------------------------------
# Personal / collaborative signal
# ---------------------------------------------------------------------------

def _shrunk_mean(raw_mean: float, n: int) -> float:
    return raw_mean * (n / (n + SHRINKAGE_DENOM))


def personal_signal(
    target_cell_means: dict[tuple[int, int], tuple[float, int]],
    target_action_means: dict[int, tuple[float, int]],
    overall: tuple[float, int] | None,
    action_index: int,
    slot: int,
) -> float:
    """Strictly-prior target residual; falls back action x slot -> action -> overall."""
    cell = target_cell_means.get((action_index, slot))
    if cell and cell[1] > 0:
        return _shrunk_mean(cell[0], cell[1])
    action = target_action_means.get(action_index)
    if action and action[1] > 0:
        return _shrunk_mean(action[0], action[1])
    if overall and overall[1] > 0:
        return _shrunk_mean(overall[0], overall[1])
    return 0.0


def _cosine_on_common(
    target: dict[tuple[int, int], float],
    source: dict[tuple[int, int], float],
) -> tuple[float, int]:
    common = [cell for cell in target if cell in source]
    n_common = len(common)
    if n_common == 0:
        return 0.0, 0
    t_vec = np.array([target[cell] for cell in common], dtype=float)
    s_vec = np.array([source[cell] for cell in common], dtype=float)
    denom = float(np.linalg.norm(t_vec) * np.linalg.norm(s_vec))
    if denom == 0.0:
        return 0.0, n_common
    return float(np.dot(t_vec, s_vec) / denom), n_common


def compute_cf_signal(
    target_cell_means: dict[tuple[int, int], tuple[float, int]],
    source_user_cell_means: dict[int, dict[tuple[int, int], tuple[float, int]]],
    cell: tuple[int, int],
    residual_clip: tuple[float, float],
) -> tuple[float, int]:
    """Shrinkage-weighted neighbor residual for one action x slot cell.

    Similarity = cosine on co-observed cells, shrunk by n_common/(n_common+10),
    positive only, >= 3 common cells, max 5 neighbors, and >= 3 contributors
    for the requested cell; otherwise cf_signal = 0.  Result is clipped to the
    source-history 5th/95th residual percentiles at prediction time t.
    """
    target_vec = {key: value[0] for key, value in target_cell_means.items() if value[1] > 0}
    similarities: list[tuple[float, int]] = []
    for source_user, cells in source_user_cell_means.items():
        source_vec = {key: value[0] for key, value in cells.items() if value[1] > 0}
        cosine, n_common = _cosine_on_common(target_vec, source_vec)
        if n_common < MIN_COMMON_CELLS:
            continue
        shrunk = cosine * (n_common / (n_common + SHRINKAGE_DENOM))
        if shrunk <= 0:
            continue
        similarities.append((shrunk, source_user))
    similarities.sort(key=lambda item: item[0], reverse=True)
    neighbors = similarities[:MAX_NEIGHBORS]
    contributors = [
        source_user
        for _, source_user in neighbors
        if source_user_cell_means[source_user].get(cell, (0.0, 0))[1] > 0
    ]
    if len(contributors) < MIN_CONTRIBUTORS:
        return 0.0, len(neighbors)
    # Shrinkage-weighted mean of the CONTRIBUTORS' cell means: each
    # contributor is weighted by its own (positive, shrunk) similarity.  We
    # must align means with their own weights; a top-5 neighbor without the
    # requested cell contributes no mean and no weight.
    contributor_set = set(contributors)
    means = [source_user_cell_means[user][cell][0] for user in contributors]
    weights = [sim for sim, user in neighbors if user in contributor_set]
    assert len(means) == len(weights)
    weighted = float(np.average(means, weights=weights))
    lo, hi = residual_clip
    clipped = min(max(weighted, lo), hi)
    return clipped, len(neighbors)


def policy_choice(scores: dict[str, float]) -> str:
    """Deterministic top-scored action; ties resolve none -> antisedentary -> walking."""
    best = max(scores.values())
    for action in SCORE_TIE_ORDER:
        if scores[action] == best:
            return action
    raise AssertionError("unreachable")


# ---------------------------------------------------------------------------
# Per-fold arrays
# ---------------------------------------------------------------------------

@dataclass
class FoldArrays:
    user: np.ndarray
    action: np.ndarray
    y: np.ndarray
    slot: np.ndarray
    activity: np.ndarray
    location: np.ndarray
    weather: np.ndarray
    prior_steps: np.ndarray
    week: np.ndarray
    rel_time: np.ndarray
    utime: np.ndarray
    contexts: list[dict[str, int]]

    def stats_dict(self) -> dict[str, np.ndarray]:
        return {
            "user": self.user,
            "action": self.action,
            "y": self.y,
            "slot": self.slot,
            "activity": self.activity,
            "location": self.location,
            "weather": self.weather,
            "prior_steps": self.prior_steps,
            "week": self.week,
            "rel_time": self.rel_time,
            "utime": self.utime,
        }


def build_fold_arrays(rows: list[dict[str, Any]]) -> FoldArrays:
    n = len(rows)
    action = np.empty(n, dtype=int)
    slot = np.empty(n, dtype=int)
    activity = np.empty(n, dtype=int)
    location = np.empty(n, dtype=int)
    weather = np.empty(n, dtype=int)
    prior_steps = np.empty(n, dtype=int)
    week = np.empty(n, dtype=int)
    rel_time = np.empty(n, dtype=float)
    utime = np.empty(n, dtype=float)
    user = np.empty(n, dtype=int)
    y = np.empty(n, dtype=float)
    contexts: list[dict[str, int]] = []
    for index, row in enumerate(rows):
        user[index] = int(row["user_index"])
        action[index] = ACTIONS.index(row["action"])
        y[index] = float(row["y"])
        context = _context_codes(row)
        slot[index] = context["slot"]
        activity[index] = context["activity"]
        location[index] = context["location"]
        weather[index] = context["weather"]
        prior_steps[index] = context["prior_steps"]
        week[index] = context["week"]
        rel_time[index] = float(row["rel_time_seconds"])
        utime[index] = float(row["decision_utime_epoch"])
        contexts.append(context)
    return FoldArrays(
        user=user, action=action, y=y, slot=slot, activity=activity,
        location=location, weather=weather, prior_steps=prior_steps,
        week=week, rel_time=rel_time, utime=utime, contexts=contexts,
    )


# ---------------------------------------------------------------------------
# One prediction time (strictly causal)
# ---------------------------------------------------------------------------

@dataclass
class PredictionResult:
    target_user: int
    prediction_utime: float
    action: str
    y: float
    y_gf: float | None
    raw_nonmissing: bool
    personal_scores: dict[str, float]
    hybrid_scores: dict[str, float]
    policy_personal: str
    policy_cf: str
    cf_signal_by_action: dict[str, float]
    neighbor_count: int
    history_max_utime: float | None
    source_max_rel_time: float | None
    context_keys: list[str] = field(default_factory=list)
    is_randomized: bool | None = None


def predict_at_time(
    target_user: int,
    prediction_row: dict[str, Any],
    source_stats: dict[str, np.ndarray],
    source_contexts: list[dict[str, int]],
    target_rows: list[dict[str, Any]],
    residual_clip_cache: dict[float, tuple[float, float]],
) -> PredictionResult:
    """Score the three actions at one target prediction time (strictly causal)."""
    t_rel = float(prediction_row["rel_time_seconds"])
    t_utime = float(prediction_row["decision_utime_epoch"])
    context = _context_codes(prediction_row)

    source_mask = source_stats["rel_time"] < t_rel
    action_means, adj_tables = _base_components(source_stats, source_mask)
    source_action = source_stats["action"][source_mask]
    feature_values = {
        feature: source_stats[feature][source_mask] for feature in CONTEXT_FEATURES
    }
    source_base = base_array_for_rows(
        action_means, adj_tables, source_action, feature_values
    )
    source_residuals = source_stats["y"][source_mask] - source_base

    if source_residuals.size == 0:
        clip_lo, clip_hi = 0.0, 0.0
    else:
        clip_lo, clip_hi = (
            float(np.percentile(source_residuals, 5)),
            float(np.percentile(source_residuals, 95)),
        )
    residual_clip_cache[t_rel] = (clip_lo, clip_hi)

    # source user x (action, slot) cell mean residuals
    source_users = source_stats["user"][source_mask]
    source_slots = source_stats["slot"][source_mask]
    code = source_users * CELL_COUNT + source_action * 5 + source_slots
    sums = np.bincount(code, weights=source_residuals)
    counts = np.bincount(code)
    source_user_cell_means: dict[int, dict[tuple[int, int], tuple[float, int]]] = {}
    for flat, count in enumerate(counts):
        if count == 0:
            continue
        user = flat // CELL_COUNT
        action = (flat % CELL_COUNT) // 5
        slot = flat % 5
        source_user_cell_means.setdefault(user, {})[(action, slot)] = (
            float(sums[flat] / count),
            int(count),
        )

    # target strictly-prior residuals (utime strictly < t)
    history = [
        row
        for row in target_rows
        if row["decision_utime_epoch"] is not None
        and float(row["decision_utime_epoch"]) < t_utime
    ]
    history_max_utime = (
        max(float(row["decision_utime_epoch"]) for row in history) if history else None
    )
    target_cell_means: dict[tuple[int, int], tuple[float, int]] = {}
    target_action_means: dict[int, tuple[float, int]] = {}
    overall_sum = 0.0
    overall_n = 0
    for row in history:
        row_action = ACTIONS.index(row["action"])
        row_context = _context_codes(row)
        base = base_for_context(action_means, adj_tables, row_action, row_context)
        residual = float(row["y"]) - base
        overall_sum += residual
        overall_n += 1
        key = (row_action, int(row["decision_slot"]) - 1)
        mean, count = target_cell_means.get(key, (0.0, 0))
        target_cell_means[key] = (mean + residual, count + 1)
        action_mean, action_count = target_action_means.get(row_action, (0.0, 0))
        target_action_means[row_action] = (action_mean + residual, action_count + 1)
    target_cell_means = {
        key: (value[0] / value[1], value[1]) for key, value in target_cell_means.items()
    }
    target_action_means = {
        key: (value[0] / value[1], value[1]) for key, value in target_action_means.items()
    }
    overall = (overall_sum / overall_n, overall_n) if overall_n > 0 else None

    personal_scores: dict[str, float] = {}
    hybrid_scores: dict[str, float] = {}
    cf_signal_by_action: dict[str, float] = {}
    neighbor_counts: list[int] = []
    slot_index = int(prediction_row["decision_slot"]) - 1
    for action_index, action_name in enumerate(ACTIONS):
        base = base_for_context(action_means, adj_tables, action_index, context)
        personal = personal_signal(
            target_cell_means, target_action_means, overall, action_index, slot_index
        )
        cf, neighbor_count = compute_cf_signal(
            target_cell_means,
            source_user_cell_means,
            (action_index, slot_index),
            (clip_lo, clip_hi),
        )
        personal_scores[action_name] = base + personal
        cf_signal_by_action[action_name] = cf
        neighbor_counts.append(neighbor_count)
        hybrid_scores[action_name] = base + personal + cf

    gf = prediction_row.get("gfsteps30")
    y_gf = math.log(float(gf) + 0.5) if gf is not None else None
    return PredictionResult(
        target_user=target_user,
        prediction_utime=t_utime,
        action=prediction_row["action"],
        y=float(prediction_row["y"]),
        y_gf=y_gf,
        raw_nonmissing=bool(prediction_row.get("raw_outcome_nonmissing")),
        personal_scores=personal_scores,
        hybrid_scores=hybrid_scores,
        policy_personal=policy_choice(personal_scores),
        policy_cf=policy_choice(hybrid_scores),
        cf_signal_by_action=cf_signal_by_action,
        neighbor_count=max(neighbor_counts) if neighbor_counts else 0,
        history_max_utime=history_max_utime,
        source_max_rel_time=(
            float(source_stats["rel_time"][source_mask].max()) if source_mask.any() else None
        ),
        context_keys=sorted(CONTEXT_WHITELIST),
        is_randomized=prediction_row.get("is_randomized"),
    )


def record_leakage_violations(
    result: PredictionResult, t_rel: float
) -> dict[str, int]:
    """Per-record leakage re-verification (used by the driver and by tests)."""
    violations = {
        "held_out_user_in_source": 0,
        "future_target_history": 0,
        "future_source_rows": 0,
        "post_response_features": 0,
    }
    if (
        result.history_max_utime is not None
        and result.history_max_utime >= result.prediction_utime
    ):
        violations["future_target_history"] = 1
    if result.source_max_rel_time is not None and result.source_max_rel_time >= t_rel:
        violations["future_source_rows"] = 1
    if not set(result.context_keys) <= CONTEXT_WHITELIST:
        violations["post_response_features"] = 1
    return violations


# ---------------------------------------------------------------------------
# SNIPS metrics
# ---------------------------------------------------------------------------

def snips_metrics(
    predictions: list[PredictionResult],
    policy_key: str,
    y_key: str = "y",
    include_fn: Callable[[PredictionResult], bool] | None = None,
) -> dict[str, float]:
    """w_t = I(A_t == pi(X_t)) / p(A_t); V = sum(w*y)/sum(w); ESS = (sum w)^2/sum(w^2)."""
    weight_sum = 0.0
    weight_sq_sum = 0.0
    weighted_y_sum = 0.0
    for prediction in predictions:
        if include_fn is not None and not include_fn(prediction):
            continue
        chosen = prediction.policy_cf if policy_key == "policy_cf" else prediction.policy_personal
        if prediction.action != chosen:
            continue
        weight = 1.0 / ASSIGNMENT_PROBABILITIES[prediction.action]
        y_value = prediction.y if y_key == "y" else getattr(prediction, y_key)
        weight_sum += weight
        weight_sq_sum += weight * weight
        weighted_y_sum += weight * y_value
    if weight_sum == 0.0:
        return {"denominator": 0.0, "ess": 0.0, "value": float("nan")}
    ess = (weight_sum * weight_sum) / weight_sq_sum if weight_sq_sum > 0 else 0.0
    return {"denominator": weight_sum, "ess": ess, "value": weighted_y_sum / weight_sum}


def zero_support_reason(metrics: dict[str, float]) -> str | None:
    if metrics["denominator"] == 0.0 or metrics["ess"] == 0.0:
        return "zero_denominator_or_ess"
    return None


# ---------------------------------------------------------------------------
# Bootstrap (participant-level paired, frozen seed)
# ---------------------------------------------------------------------------

def participant_bootstrap_ci(
    deltas: list[float],
    seed: int = BOOTSTRAP_SEED,
    replicates: int = BOOTSTRAP_REPLICATES,
) -> dict[str, float]:
    rng = np.random.default_rng(seed)
    array = np.asarray(deltas, dtype=float)
    means = np.empty(replicates, dtype=float)
    for index in range(replicates):
        sample = array[rng.integers(0, array.size, size=array.size)]
        means[index] = float(sample.mean())
    lo, hi = np.percentile(means, [2.5, 97.5])
    return {
        "mean": float(array.mean()),
        "ci_lower": float(lo),
        "ci_upper": float(hi),
        "replicates": replicates,
        "seed": seed,
    }


# ---------------------------------------------------------------------------
# 37-fold LOPO temporal evaluation
# ---------------------------------------------------------------------------

def evaluate_claim(
    delta_v: float | None,
    ci_lower: float | None,
    zero_support_users: list[int],
    all_gates_pass: bool,
) -> tuple[str, str, str | None]:
    """Mechanical CR-CF-001 evaluation; never hardcoded.

    SUPPORTED only iff Delta_V > 0 AND participant-bootstrap 95% CI lower
    bound > 0 AND both policies have positive denominator/ESS for every
    participant AND all integrity gates pass.
    """
    if zero_support_users:
        return (
            "NOT_EVALUABLE",
            "CANNOT_BE_SUPPORTED",
            "zero_support_participants: " + ",".join(map(str, zero_support_users)),
        )
    if delta_v is None or not delta_v > 0:
        return "EVALUATED", "UNSUPPORTED", "delta_not_greater_than_zero"
    if ci_lower is None or ci_lower <= 0:
        return "EVALUATED", "UNSUPPORTED", "bootstrap_ci_lower_not_greater_than_zero"
    if not all_gates_pass:
        return "EVALUATED", "UNSUPPORTED", "integrity_gates_failed"
    return "EVALUATED", "SUPPORTED", None


def evaluate_all_folds(
    analysis_rows: list[dict[str, Any]],
    integrity_gates: dict[str, Any] | None = None,
    compute_aggregates: bool = True,
) -> dict[str, Any]:
    users = sorted({int(row["user_index"]) for row in analysis_rows})
    rows_by_user: dict[int, list[dict[str, Any]]] = {}
    for row in analysis_rows:
        rows_by_user.setdefault(int(row["user_index"]), []).append(row)
    for user_rows in rows_by_user.values():
        user_rows.sort(key=lambda row: float(row["decision_utime_epoch"]))

    participants: list[dict[str, Any]] = []
    fold_assignments: list[dict[str, Any]] = []
    leakage_violations: dict[str, int] = {
        "held_out_user_in_source": 0,
        "future_target_history": 0,
        "future_source_rows": 0,
        "post_response_features": 0,
    }

    for fold_index, target_user in enumerate(users):
        source_users = [uid for uid in users if uid != target_user]
        if target_user in source_users:
            leakage_violations["held_out_user_in_source"] += 1
        source_rows = [row for uid in source_users for row in rows_by_user[uid]]
        fold_arrays = build_fold_arrays(source_rows)
        source_stats = fold_arrays.stats_dict()
        target_rows = rows_by_user[target_user]
        eval_rows = [
            row
            for row in target_rows
            if row["study_day"] is not None
            and TARGET_TEST_DAYS[0] <= row["study_day"] <= TARGET_TEST_DAYS[1]
        ]
        residual_clip_cache: dict[float, tuple[float, float]] = {}
        fold_predictions: list[PredictionResult] = []
        for prediction_row in eval_rows:
            result = predict_at_time(
                target_user,
                prediction_row,
                source_stats,
                fold_arrays.contexts,
                target_rows,
                residual_clip_cache,
            )
            t_rel = float(prediction_row["rel_time_seconds"])
            for key, count in record_leakage_violations(result, t_rel).items():
                leakage_violations[key] += count
            fold_predictions.append(result)

        personal_metrics = snips_metrics(fold_predictions, "policy_personal")
        cf_metrics = snips_metrics(fold_predictions, "policy_cf")
        delta = cf_metrics["value"] - personal_metrics["value"]
        zero_support = (
            zero_support_reason(personal_metrics) or zero_support_reason(cf_metrics)
        )
        mae_rows = [
            abs(float(prediction.y) - prediction.hybrid_scores[prediction.action])
            for prediction in fold_predictions
        ]
        cf_applied_rows = sum(
            1
            for prediction in fold_predictions
            if prediction.cf_signal_by_action.get(prediction.policy_cf, 0.0) != 0.0
        )
        # secondary sensitivities
        cc_personal = snips_metrics(
            fold_predictions, "policy_personal", include_fn=lambda p: p.raw_nonmissing
        )
        cc_cf = snips_metrics(
            fold_predictions, "policy_cf", include_fn=lambda p: p.raw_nonmissing
        )
        gf_personal = snips_metrics(
            fold_predictions, "policy_personal", y_key="y_gf",
            include_fn=lambda p: p.y_gf is not None,
        )
        gf_cf = snips_metrics(
            fold_predictions, "policy_cf", y_key="y_gf",
            include_fn=lambda p: p.y_gf is not None,
        )
        # Secondary sensitivity (AM-001): SNIPS restricted to rows whose
        # released is.randomized field is True.  Never affects the primary.
        rand_personal = snips_metrics(
            fold_predictions, "policy_personal",
            include_fn=lambda p: p.is_randomized is True,
        )
        rand_cf = snips_metrics(
            fold_predictions, "policy_cf",
            include_fn=lambda p: p.is_randomized is True,
        )
        participants.append(
            {
                "user_index": target_user,
                "eval_rows": len(fold_predictions),
                "denominator_personal": personal_metrics["denominator"],
                "ess_personal": personal_metrics["ess"],
                "v_personal": personal_metrics["value"],
                "denominator_cf": cf_metrics["denominator"],
                "ess_cf": cf_metrics["ess"],
                "v_cf": cf_metrics["value"],
                "delta": delta,
                "zero_support": zero_support,
                "mae_hybrid": float(np.mean(mae_rows)) if mae_rows else float("nan"),
                "neighbor_coverage": (
                    cf_applied_rows / len(fold_predictions) if fold_predictions else 0.0
                ),
                "cc_v_personal": cc_personal["value"],
                "cc_v_cf": cc_cf["value"],
                "gf_v_personal": gf_personal["value"],
                "gf_v_cf": gf_cf["value"],
                "randtrue_v_personal": rand_personal["value"],
                "randtrue_v_cf": rand_cf["value"],
                "randtrue_eval_rows": sum(
                    1 for p in fold_predictions if p.is_randomized is True
                ),
            }
        )
        fold_assignments.append(
            {
                "fold": fold_index + 1,
                "target_user": target_user,
                "source_users": source_users,
                "source_rows": len(source_rows),
                "eval_rows": len(fold_predictions),
            }
        )

    zero_support_users = [p["user_index"] for p in participants if p["zero_support"]]
    evaluable = not zero_support_users
    deltas = [p["delta"] for p in participants]

    if compute_aggregates and evaluable and deltas:
        bootstrap = participant_bootstrap_ci(deltas)
        delta_v = bootstrap["mean"]
    else:
        bootstrap = None
        delta_v = None

    all_gates_pass = bool(
        integrity_gates is not None
        and integrity_gates.get("heartsteps_hashes") == "PASS"
        and integrity_gates.get("duplicates") == 0
        and integrity_gates.get("schema_ok") is True
        and sum(leakage_violations.values()) == 0
    )

    if not evaluable:
        primary_status, claim_status, claim_reason = evaluate_claim(
            delta_v=None, ci_lower=None, zero_support_users=zero_support_users,
            all_gates_pass=all_gates_pass,
        )
    else:
        primary_status, claim_status, claim_reason = evaluate_claim(
            delta_v=delta_v,
            ci_lower=bootstrap["ci_lower"] if bootstrap else None,
            zero_support_users=[],
            all_gates_pass=all_gates_pass,
        )

    return {
        "participants": participants,
        "fold_assignments": fold_assignments,
        "leakage_violations": leakage_violations,
        "zero_support_users": zero_support_users,
        "evaluable": evaluable,
        "delta_v": delta_v,
        "bootstrap": bootstrap,
        "primary_status": primary_status,
        "claim": {"CR-CF-001": claim_status, "reason": claim_reason},
    }


# ---------------------------------------------------------------------------
# Integrity gates
# ---------------------------------------------------------------------------

def check_schema(analysis_rows: list[dict[str, Any]]) -> dict[str, Any]:
    required = {
        "user_index", "decision_index", "decision_utime_epoch", "decision_slot",
        "action", "study_day", "study_week", "rel_time_seconds", "y",
        "activity_bucket", "location_bucket", "weather_bucket", "prior_step_bucket",
    }
    problems = []
    for row in analysis_rows:
        missing = required - set(row.keys())
        if missing:
            problems.append(f"missing columns {sorted(missing)}")
            break
        if row["action"] not in ACTIONS:
            problems.append(f"invalid action {row['action']!r}")
            break
        if row["y"] is None or not math.isfinite(float(row["y"])):
            problems.append(f"non-finite y for user {row['user_index']}")
            break
        if row["study_day"] is None or not (1 <= row["study_day"] <= 42):
            problems.append(f"study day out of range for user {row['user_index']}")
            break
        if row["decision_slot"] not in (1, 2, 3, 4, 5):
            problems.append(f"slot out of range for user {row['user_index']}")
            break
    return {"schema_ok": not problems, "problems": problems, "rows": len(analysis_rows)}


def check_integrity_gates(
    cache_dir: str | Path, duplicate_policy: str = "fail"
) -> dict[str, Any]:
    verification = verify_pinned_files(cache_dir)
    suggestions = _read_csv(Path(cache_dir) / "suggestions.csv")
    users = _read_csv(Path(cache_dir) / "users.csv")
    flow = apply_eligibility(suggestions, users, duplicate_policy=duplicate_policy)
    return {
        "heartsteps_hashes": verification["status"],
        "duplicates": flow["duplicates"],
        "users": len(users),
        "raw_rows": flow["raw_total"],
        "final_rows": len(flow["final_rows"]),
    }


# ---------------------------------------------------------------------------
# PRECHECK (never computes the real CF result)
# ---------------------------------------------------------------------------

def verify_temporal_structure(analysis_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Pure data-driven leakage-structure verification; executes NO model.

    Returns violation counters that are meaningful without executing the
    frozen model:

    - ``held_out_user_in_source``: every fold's source-user set must exclude
      the held-out target (fold assignment structure);
    - ``post_response_features``: the analysis table must carry no column
      outside the frozen prediction-time whitelist;
    - ``time_ordering_violations``: per user, decision timestamps must be
      strictly increasing (strictly-causal masks rely on well-ordered rows).

    ``future_target_history`` / ``future_source_rows`` are guaranteed to be 0
    by construction: the driver only ever consults target rows with
    utime < t and source rows with relative study time < t.  Those strictly
    causal masks are exercised by the synthetic driver tests; the record-level
    re-verification additionally runs inside FORMAL mode after audit.
    """
    violations = {
        "held_out_user_in_source": 0,
        "future_target_history": 0,
        "future_source_rows": 0,
        "post_response_features": 0,
        "time_ordering_violations": 0,
    }
    users = sorted({int(row["user_index"]) for row in analysis_rows})
    rows_by_user: dict[int, list[dict[str, Any]]] = {}
    for row in analysis_rows:
        rows_by_user.setdefault(int(row["user_index"]), []).append(row)

    allowed_keys = {
        "user_index", "decision_index", "decision_utime", "decision_utime_epoch",
        "decision_slot", "is_randomized", "action", "avail", "study_day",
        "study_week", "rel_time_seconds", "activity_bucket", "location_bucket",
        "weather_bucket", "prior_step_bucket", "jbsteps30_raw", "jbsteps30_zero",
        "gfsteps30", "y", "y_gf", "raw_outcome_nonmissing", "gf_outcome_nonmissing",
    }
    if analysis_rows:
        extra = set(analysis_rows[0].keys()) - allowed_keys
        violations["post_response_features"] = len(extra)

    for target_user in users:
        source_users = [uid for uid in users if uid != target_user]
        if target_user in source_users:
            violations["held_out_user_in_source"] += 1
        ordered = sorted(rows_by_user[target_user],
                         key=lambda row: float(row["decision_utime_epoch"]))
        for earlier, later in itertools.pairwise(ordered):
            if float(later["decision_utime_epoch"]) <= float(earlier["decision_utime_epoch"]):
                violations["time_ordering_violations"] += 1
    return violations


def run_precheck(
    analysis_rows: list[dict[str, Any]],
    integrity_gates: dict[str, Any],
    out_dir: str | Path,
) -> dict[str, Any]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    schema = check_schema(analysis_rows)
    # Pure data-driven leakage-structure verification over the FULL cohort; the
    # frozen model is never executed here (the driver is exercised only on
    # synthetic fixtures below).
    leakage = verify_temporal_structure(analysis_rows)
    synthetic = run_synthetic_evaluator_tests()
    report = {
        "manifest_id": "stage9_leakage_test_report_v1",
        "schema_version": "1.1",
        "generated_at": datetime.now(UTC).isoformat(),
        "integrity_gates": {
            "heartsteps_hashes": integrity_gates.get("heartsteps_hashes"),
            "duplicates": integrity_gates.get("duplicates"),
            "users": integrity_gates.get("users"),
            "raw_rows": integrity_gates.get("raw_rows"),
            "final_rows": integrity_gates.get("final_rows"),
            "schema_ok": schema["schema_ok"],
        },
        "leakage_checks": {
            "held_out_user_in_source": leakage["held_out_user_in_source"],
            "future_target_history": leakage["future_target_history"],
            "future_source_rows": leakage["future_source_rows"],
            "post_response_features": leakage["post_response_features"],
            "time_ordering_violations": leakage["time_ordering_violations"],
            "total_violations": (
                leakage["held_out_user_in_source"]
                + leakage["future_target_history"]
                + leakage["future_source_rows"]
                + leakage["post_response_features"]
            ),
        },
        "synthetic_evaluator_tests": synthetic,
        "formal_result_computed": False,
        "delta_v_computed": False,
        "ci_computed": False,
        "cr_cf_001_evaluated": False,
        "model_executed_on_real_data": False,
        "note": "PRECHECK verifies data integrity, schema and leakage structure "
                "over the full cohort WITHOUT executing the frozen model; the "
                "model math is exercised only on synthetic fixtures. "
                "future_target/future_source = 0 by construction of the "
                "strictly-causal masks (utime < t / relative time < t), which "
                "are exercised by the synthetic driver tests; record-level "
                "re-verification runs in FORMAL mode after audit. No real "
                "Delta_V / CI / CR-CF-001 is computed or persisted.",
    }
    with open(out_dir / "stage9_leakage_test_report_v1.json", "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return report


def run_synthetic_evaluator_tests() -> list[dict[str, Any]]:
    """Small hand-built fixtures proving the frozen model math (no real data)."""
    results: list[dict[str, Any]] = []

    # 1) base score: action means + shrunk context adjustments
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
    results.append({
        "test": "base_score_shrinkage_and_action_means",
        "passed": math.isclose(base["none"], 10.0, abs_tol=1e-9)
                  and math.isclose(base["walking"], 100.0, abs_tol=1e-9),
        "detail": {"base": base},
    })

    # 2) deterministic tie order none -> antisedentary -> walking
    results.append({
        "test": "score_tie_order_none_antisedentary_walking",
        "passed": policy_choice({"none": 5.0, "walking": 5.0, "antisedentary": 5.0}) == "none"
                  and policy_choice({"none": 4.0, "walking": 5.0, "antisedentary": 5.0}) == "antisedentary",
        "detail": {},
    })

    # 3) SNIPS exact weights / value / ESS
    predictions = []
    for action, y_value in (("none", 0.5), ("walking", 1.5), ("antisedentary", 2.5)):
        prediction = PredictionResult(
            target_user=1, prediction_utime=1.0, action=action, y=y_value, y_gf=None,
            raw_nonmissing=True, personal_scores={}, hybrid_scores={},
            policy_personal=action, policy_cf=action, cf_signal_by_action={},
            neighbor_count=0, history_max_utime=None, source_max_rel_time=None,
        )
        predictions.append(prediction)
    metrics = snips_metrics(predictions, "policy_cf")
    expected_value = (0.5 / 0.4 + 1.5 / 0.3 + 2.5 / 0.3) / (1 / 0.4 + 1 / 0.3 + 1 / 0.3)
    expected_ess = (1 / 0.4 + 1 / 0.3 + 1 / 0.3) ** 2 / (
        (1 / 0.4) ** 2 + (1 / 0.3) ** 2 + (1 / 0.3) ** 2
    )
    results.append({
        "test": "snips_weight_value_ess_exact",
        "passed": math.isclose(metrics["value"], expected_value, rel_tol=1e-9)
                  and math.isclose(metrics["ess"], expected_ess, rel_tol=1e-9),
        "detail": {"value": metrics["value"], "ess": metrics["ess"]},
    })

    # 4) cf_signal requires >= 3 contributors for the requested cell
    target_cells = {(0, 0): (1.0, 5), (0, 1): (2.0, 5), (0, 2): (3.0, 5)}
    source_cells = {
        1: {(0, 0): (0.5, 4), (0, 1): (1.5, 4), (0, 2): (2.5, 4)},
        2: {(0, 0): (0.4, 4), (0, 1): (1.4, 4), (0, 2): (2.4, 4)},
        3: {(0, 0): (0.6, 4), (0, 1): (1.6, 4), (0, 2): (2.6, 4)},
    }
    cf, neighbors = compute_cf_signal(target_cells, source_cells, (0, 0), (-10.0, 10.0))
    results.append({
        "test": "cf_signal_min_three_contributors",
        "passed": cf != 0.0 and neighbors >= MIN_CONTRIBUTORS,
        "detail": {"cf": cf, "neighbors": neighbors},
    })
    cf_sparse, neighbors_sparse = compute_cf_signal(
        target_cells, {1: source_cells[1], 2: source_cells[2]}, (0, 0), (-10.0, 10.0)
    )
    results.append({
        "test": "cf_signal_zero_when_fewer_than_three_contributors",
        "passed": cf_sparse == 0.0,
        "detail": {"cf": cf_sparse, "neighbors": neighbors_sparse},
    })

    # 5) bootstrap determinism with the frozen seed
    deltas = [0.1 * (index % 5) - 0.05 for index in range(37)]
    first = participant_bootstrap_ci(deltas, seed=BOOTSTRAP_SEED, replicates=200)
    second = participant_bootstrap_ci(deltas, seed=BOOTSTRAP_SEED, replicates=200)
    results.append({
        "test": "bootstrap_seed_determinism",
        "passed": first["ci_lower"] == second["ci_lower"]
                  and first["ci_upper"] == second["ci_upper"],
        "detail": {"ci_lower": first["ci_lower"], "ci_upper": first["ci_upper"]},
    })

    # 6) zero support detected
    zero = {"denominator": 0.0, "ess": 0.0, "value": float("nan")}
    results.append({
        "test": "zero_support_detected",
        "passed": zero_support_reason(zero) is not None,
        "detail": {"reason": zero_support_reason(zero)},
    })
    return results


# ---------------------------------------------------------------------------
# FORMAL (immutable run artifacts)
# ---------------------------------------------------------------------------

def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_sha256_manifest(run_dir: Path) -> None:
    entries = {}
    for path in sorted(run_dir.iterdir()):
        if path.is_file():
            entries[path.name] = _sha256_file(path)
    with open(run_dir / "sha256_manifest.json", "w", encoding="utf-8") as handle:
        json.dump(entries, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def run_formal(
    analysis_rows: list[dict[str, Any]],
    integrity_gates: dict[str, Any],
    out_dir: str | Path,
) -> dict[str, Any]:
    """FORMAL: computes the real Delta_V / CI / CR-CF-001 into an immutable run dir.

    Exit gate (implementation contract): FORMAL refuses to write any run unless
    all integrity gates pass (hashes PASS, zero duplicates, schema OK) and the
    fold-driver leakage re-verification is violation-free.
    """
    out_dir = Path(out_dir)
    gates_failed = (
        integrity_gates is None
        or integrity_gates.get("heartsteps_hashes") != "PASS"
        or integrity_gates.get("duplicates") != 0
        or integrity_gates.get("schema_ok") is not True
    )
    if gates_failed:
        raise RuntimeError(
            "FORMAL run blocked by integrity gates: " + json.dumps(integrity_gates)
        )
    out_dir.mkdir(parents=True, exist_ok=False)
    results = evaluate_all_folds(analysis_rows, integrity_gates=integrity_gates)
    if sum(results["leakage_violations"].values()) > 0:
        raise RuntimeError(
            "FORMAL run blocked by leakage violations: "
            + json.dumps(results["leakage_violations"])
        )

    run_manifest = {
        "manifest_id": "stage9_formal_run",
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "FORMAL",
        "source": {"name": "HeartSteps V1", "commit": PINNED_COMMIT},
        "hashes": {name: pin["sha256"] for name, pin in PINNED_FILES.items()},
        "policies": {
            "comparator": POLICY_PERSONAL,
            "method": POLICY_PLUS_CF,
            "note": (
                "EXTERNAL personal means HeartSteps target-user history, NOT "
                "微律 Personal RAG."
            ),
        },
        "interpretation": METHOD_INTERPRETATION,
        "constants": {
            "bootstrap_replicates": BOOTSTRAP_REPLICATES,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "shrinkage_denom": SHRINKAGE_DENOM,
            "min_common_cells": MIN_COMMON_CELLS,
            "max_neighbors": MAX_NEIGHBORS,
            "min_contributors": MIN_CONTRIBUTORS,
            "assignment_probabilities": ASSIGNMENT_PROBABILITIES,
            "score_tie_order": list(SCORE_TIE_ORDER),
            "target_adaptation_days": list(TARGET_ADAPTATION_DAYS),
            "target_test_days": list(TARGET_TEST_DAYS),
        },
        "integrity_gates": integrity_gates,
        "leakage_violations": results["leakage_violations"],
        "preregistration_amendments": PREREGISTRATION_AMENDMENTS,
        "primary_status": results["primary_status"],
        "claim": results["claim"],
    }
    with open(out_dir / "run_manifest.json", "w", encoding="utf-8") as handle:
        json.dump(run_manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    with open(out_dir / "per_participant_metrics.csv", "w", encoding="utf-8",
              newline="") as handle:
        writer = csv_module.DictWriter(
            handle, fieldnames=list(results["participants"][0].keys())
        )
        writer.writeheader()
        writer.writerows(results["participants"])

    with open(out_dir / "fold_assignments.csv", "w", encoding="utf-8",
              newline="") as handle:
        writer = csv_module.DictWriter(
            handle, fieldnames=list(results["fold_assignments"][0].keys())
        )
        writer.writeheader()
        writer.writerows(results["fold_assignments"])

    with open(out_dir / "claim_evaluation.json", "w", encoding="utf-8") as handle:
        json.dump({
            "claim_id": "CR-CF-001",
            "status": results["claim"]["CR-CF-001"],
            "reason": results["claim"]["reason"],
            "policies": {
                "comparator": POLICY_PERSONAL,
                "method": POLICY_PLUS_CF,
                "note": (
                    "EXTERNAL personal means HeartSteps target-user history, "
                    "NOT 微律 Personal RAG."
                ),
            },
            "delta_v": results["delta_v"],
            "bootstrap": results["bootstrap"],
            "zero_support_users": results["zero_support_users"],
            "evaluable": results["evaluable"],
            "interpretation": METHOD_INTERPRETATION,
            "not_proof_of": [
                "35-day deployment value",
                "long-term intervention efficacy",
                "causal value of deploying weilv CF",
                "youth effectiveness",
            ],
        }, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    _write_sha256_manifest(out_dir)
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-table", default=None,
                        help="path to the preprocessor analysis table CSV")
    parser.add_argument("--cache-dir", default=str(Path(".runtime") / "stage9_heartsteps"))
    parser.add_argument("--out-dir", default=str(Path("evaluation/stage9/preformal")))
    parser.add_argument("--formal", action="store_true",
                        help="compute the real formal CF result (frozen code audit required first)")
    parser.add_argument("--no-download", action="store_true")
    parser.add_argument("--duplicate-policy", choices=("fail", "report"),
                        default="fail",
                        help="preflight may use 'report' to audit duplicate keys")
    return parser


def _cli() -> int:
    parser = build_parser()
    args = parser.parse_args()

    cache_dir = Path(args.cache_dir)
    if not args.no_download:
        try:
            download_pinned_files(cache_dir)
        except Exception as error:  # noqa: BLE001
            print(f"[runner] download failed: {error}", file=sys.stderr)
            return 2

    integrity_gates = check_integrity_gates(cache_dir, duplicate_policy=args.duplicate_policy)
    print("[runner] integrity gates:", json.dumps(integrity_gates, indent=2))

    if args.analysis_table:
        from evaluation.stage9.preprocess_heartsteps_v1 import read_csv_rows
        analysis_rows = read_csv_rows(Path(args.analysis_table))
    else:
        users = _read_csv(cache_dir / "users.csv")
        suggestions = _read_csv(cache_dir / "suggestions.csv")
        flow = apply_eligibility(suggestions, users,
                                 duplicate_policy=args.duplicate_policy)
        analysis_rows = build_analysis_rows(flow["final_rows"], flow)
        emit_flow_manifests(flow, analysis_rows, users, Path(args.out_dir))

    if not args.formal:
        report = run_precheck(analysis_rows, integrity_gates, Path(args.out_dir))
        print("[runner] PRECHECK complete (no formal CF result computed).")
        print(json.dumps(report, ensure_ascii=False, indent=2)[:4000])
        return 0

    # Stage 9C.1 wiring repair: the real schema result (computed over the
    # constructed analysis table) must reach the FORMAL integrity gate.
    # PRECHECK recomputes schema internally, so its behavior is unchanged.
    # Fail-closed semantics are unchanged: run_formal blocks whenever
    # schema_ok is not True (including a failing schema check).
    schema = check_schema(analysis_rows)
    integrity_gates["schema_ok"] = schema["schema_ok"]

    run_dir = Path("evaluation/runs") / (
        datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "_stage9_formal"
    )
    results = run_formal(analysis_rows, integrity_gates, run_dir)
    print(json.dumps({
        "run_dir": str(run_dir),
        "primary_status": results["primary_status"],
        "claim": results["claim"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
