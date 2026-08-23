"""Stage 9B product CF tie-break adapter (neutral by default).

Implements the frozen Stage 9A v1.1 product contract:

- CF executes only after the existing safe Personal/Agentic ranking and may
  reorder ONLY exact ``adjusted_rank`` ties.
- Primary key: existing ``personalization.adjusted_rank`` (unchanged).
- Secondary key within an exact tie: descending bounded ``cf_signal``.
- Tertiary keys: existing ``base_task_rank``, then ``task_id``.
- No exact ``adjusted_rank`` tie -> no order change.
- Candidate multiset and cardinality must remain identical.
- Unknown/duplicate task signals, missing/corrupt artifacts, NaN / infinity /
  out-of-range scores fail closed -> original order plus a reason.
- HeartSteps-derived scores never enter this adapter.  Until a separately
  approved real 微律 pilot, the provider is neutral (cf_signal = 0.0).

This module is pure and side-effect free; it copies nothing from the tasks and
mutates nothing.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

CF_SIGNAL_MIN = -1.0
CF_SIGNAL_MAX = 1.0
NEUTRAL_CF_SIGNAL = 0.0
NEUTRAL_MODEL_VERSION = "neutral-v0.1"
NEUTRAL_DATA_VERSION = "none"

# Minimum product-side data conditions before a nonzero signal may be applied.
# These mirror the preregistration product contract.
MIN_TARGET_INTERACTIONS = 10
MIN_NEIGHBORS = 3


def neutral_cf_provider(task_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Neutral provider: bounded zero signal for every candidate ID.

    Until a future real 微律 pilot, this is the only production provider.
    HeartSteps parameters must never populate this interface.
    """
    return {
        task_id: {
            "cf_signal": NEUTRAL_CF_SIGNAL,
            "neighbor_count": 0,
            "model_version": NEUTRAL_MODEL_VERSION,
            "data_version": NEUTRAL_DATA_VERSION,
        }
        for task_id in task_ids
    }


def _is_finite_in_range(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(value) and CF_SIGNAL_MIN <= value <= CF_SIGNAL_MAX


def _coerce_float(value: Any, default: float) -> float:
    """Exception-safe finite-float coercion for diagnostics metadata.

    Non-numeric, boolean, or non-finite values degrade to ``default``.  Never
    raises.  Diagnostics fallbacks never influence task ranking (ranking reads
    only values already validated by :func:`validate_signals`).
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    result = float(value)
    return result if math.isfinite(result) else default


def _coerce_int(value: Any, default: int) -> int:
    """Exception-safe finite-int coercion for diagnostics metadata."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    try:
        result = int(value)
    except (ValueError, OverflowError):  # e.g. int(float("nan")) / int(float("inf"))
        return default
    return result if math.isfinite(result) else default


def _coerce_str(value: Any, default: str) -> str:
    """Exception-safe non-empty-string coercion for diagnostics metadata."""
    return value if isinstance(value, str) and value else default


def validate_signals(
    tasks: list[dict[str, Any]], signals: dict[str, dict[str, Any]] | None
) -> tuple[bool, str]:
    """Validate the CF artifact against the candidate set; fail closed otherwise.

    Returns (ok, reason).  Any failure means the caller must keep the original
    order.
    """
    if not tasks:
        return True, "no_candidates"
    if signals is None:
        return False, "missing_cf_artifact"
    task_ids = [task.get("task_id") for task in tasks]
    if not all(isinstance(task_id, str) and task_id for task_id in task_ids):
        return False, "candidate_without_task_id"
    if len(set(task_ids)) != len(task_ids):
        return False, "duplicate_candidate_task"
    if not isinstance(signals, dict):
        return False, "corrupt_cf_artifact"
    signal_ids = list(signals.keys())
    if len(set(signal_ids)) != len(signal_ids):
        return False, "duplicate_signal_task"
    unknown = [task_id for task_id in signal_ids if task_id not in set(task_ids)]
    if unknown:
        return False, "unknown_task_signal"
    missing = [task_id for task_id in task_ids if task_id not in signals]
    if missing:
        return False, "missing_signal_for_candidate"
    # rank fields must be present and numeric so the sort can never crash:
    # missing/None rank fields fail closed to the original order
    for task in tasks:
        personalization = task.get("personalization")
        if not isinstance(personalization, dict):
            return False, "missing_rank_fields"
        adjusted = personalization.get("adjusted_rank")
        base_rank = personalization.get("base_task_rank")
        if not isinstance(adjusted, (int, float)) or isinstance(adjusted, bool):
            return False, "missing_rank_fields"
        if not isinstance(base_rank, (int, float)) or isinstance(base_rank, bool):
            return False, "missing_rank_fields"
    for task_id in task_ids:
        entry = signals[task_id]
        if not isinstance(entry, dict):
            return False, "corrupt_signal_entry"
        signal = entry.get("cf_signal")
        if not _is_finite_in_range(signal):
            return False, "nonfinite_or_out_of_range_signal"
    return True, "ok"


def apply_cf_tiebreak(
    tasks: list[dict[str, Any]],
    signals: dict[str, dict[str, Any]] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Reorder only exact ``adjusted_rank`` ties; fail closed otherwise.

    Returns (ordered_tasks, diagnostics).  ``ordered_tasks`` is a NEW list of
    the same task objects (never mutated, never copied in content); on any
    failure it is the original order with ``cf_applied=False``.
    """
    try:
        ok, reason = validate_signals(tasks, signals)
    except Exception:  # noqa: BLE001 - validation must never crash the caller
        ok, reason = False, "validation_failed_fail_closed"
    before_ids = [task.get("task_id") for task in tasks]
    safe_signals = signals if isinstance(signals, dict) else {}

    def _entry(task_id: Any) -> dict[str, Any]:
        if not isinstance(task_id, str):
            return {}
        entry = safe_signals.get(task_id)
        return entry if isinstance(entry, dict) else {}

    def _diagnostics(applied: bool, fallback_reason: str | None) -> dict[str, Any]:
        # Stage 9B.1 repair (audit F-001/F-002): diagnostics must never raise.
        # Every provider value passes through exception-safe coercion helpers;
        # malformed values degrade to neutral fallbacks that cannot influence
        # ranking (ranking reads only values validated by validate_signals).
        return {
            "cf_applied": applied,
            "cf_fallback_reason": fallback_reason,
            "cf_signal_by_task": {
                str(task_id): _coerce_float(
                    _entry(task_id).get("cf_signal"), NEUTRAL_CF_SIGNAL
                )
                for task_id in before_ids
            },
            "cf_neighbor_count_by_task": {
                str(task_id): _coerce_int(_entry(task_id).get("neighbor_count"), 0)
                for task_id in before_ids
            },
            "candidate_task_ids_before_cf": list(before_ids),
            "candidate_task_ids_after_cf": list(before_ids),
            "cf_model_version": sorted({
                _coerce_str(_entry(task_id).get("model_version"), NEUTRAL_MODEL_VERSION)
                for task_id in before_ids
            }),
            "cf_data_version": sorted({
                _coerce_str(_entry(task_id).get("data_version"), NEUTRAL_DATA_VERSION)
                for task_id in before_ids
            }),
            "invariant_candidate_set": True,
            "invariant_cardinality": True,
            "invariant_no_mutation": True,
        }

    if not ok:
        return list(tasks), _diagnostics(False, reason)

    def sort_key(task: dict[str, Any]) -> tuple[Any, ...]:
        personalization = task.get("personalization") or {}
        signal = float(signals[task["task_id"]]["cf_signal"])
        return (
            personalization.get("adjusted_rank"),
            -signal,
            personalization.get("base_task_rank"),
            task["task_id"],
        )

    try:
        ordered = sorted(tasks, key=sort_key)
    except (TypeError, ValueError, KeyError):
        # defensive fail-closed: never crash the caller
        return list(tasks), _diagnostics(False, "sort_failed_fail_closed")
    after_ids = [task.get("task_id") for task in ordered]

    diagnostics = _diagnostics(True, None)
    diagnostics["candidate_task_ids_after_cf"] = list(after_ids)
    if sorted(before_ids) != sorted(after_ids):
        diagnostics.update(
            cf_applied=False,
            cf_fallback_reason="candidate_set_changed",
            invariant_candidate_set=False,
        )
        return list(tasks), diagnostics
    if len(before_ids) != len(after_ids):
        diagnostics.update(
            cf_applied=False,
            cf_fallback_reason="candidate_cardinality_changed",
            invariant_cardinality=False,
        )
        return list(tasks), diagnostics
    return ordered, diagnostics


def apply_cf_to_ranking(
    ranking: list[dict[str, Any]],
    provider: Callable[[list[str]], dict[str, dict[str, Any]]] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Convenience wrapper used at the Personal/Agentic integration points.

    A ``None`` provider (production default) is a strict no-op: the original
    order is returned with ``cf_applied=False`` and no diagnostics.
    """
    if provider is None:
        return ranking, None
    task_ids = [task.get("task_id") for task in ranking]
    try:
        signals = provider(task_ids)
    except Exception:  # noqa: BLE001 - any provider failure fails closed
        return ranking, {
            "cf_applied": False,
            "cf_fallback_reason": "provider_exception",
            "candidate_task_ids_before_cf": list(task_ids),
            "candidate_task_ids_after_cf": list(task_ids),
        }
    return apply_cf_tiebreak(ranking, signals)
