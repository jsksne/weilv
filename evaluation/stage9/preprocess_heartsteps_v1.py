"""Stage 9B preprocessor: HeartSteps V1 pinned source -> deterministic Stage 9 cohort.

Implements the frozen Stage 9A v1.1 eligibility, action reconstruction and
row-flow audit for DESIGN C (external mechanism validation).

Responsibilities
----------------
1. Download the pinned HeartSteps V1 release to a temporary/cache directory
   (never vendored into the repository) and verify every frozen hash.
2. Reconstruct the three frozen action archetypes exactly:
       none          send=False, send.active=False, send.sedentary=False
       walking       send=True,  send.active=True,  send.sedentary=False
       antisedentary send=True,  send.active=False, send.sedentary=True
   Any contradictory/incomplete encoding is excluded and counted; it is never
   repaired heuristically and never inferred from ``returned.message``.
3. Apply the frozen primary eligibility rules in a fixed, documented order and
   emit the row-flow manifests:
       - evaluation/stage9/preformal/preprocessing_flow_v1.json
       - evaluation/stage9/preformal/preprocessing_flow_by_user_v1.csv
       - evaluation/stage9/preformal/stage9_public_release_exclusion_rules_v1.json
4. Write a deterministic analysis table (no raw external files) into the cache
   directory for the external evaluator runner.

Important semantic notes
------------------------
- ``is.randomized`` is a *required nonblank operational field*, NOT an inclusion
  filter.  The randomized action space at an eligible available decision point
  is {none, walking, antisedentary} with probabilities {0.4, 0.3, 0.3}.  Rows
  with ``is.randomized == False`` (or blank) are handled by the operational
  missingness rule, never by a ``keep only is.randomized == True`` filter.
- Raw ``jbsteps30`` nonmissingness is NOT a primary eligibility condition; the
  primary outcome is y = ln(jbsteps30.zero + 0.5).  Raw jbsteps30 is reserved
  for complete-case sensitivity; Google Fit for sensor sensitivity.
- The final cohort is the reproducible public-release cohort.  Paper
  denominators (7,540 included / 6,061 available) are comparison targets only.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Frozen pinning (Stage 9A v1.1)
# ---------------------------------------------------------------------------

PINNED_COMMIT = "3016391de426116bdef41880d72bc8cd4b9b2477"
RAW_BASE_URL = f"https://raw.githubusercontent.com/klasnja/HeartStepsV1/{PINNED_COMMIT}"

# (data_files path, sha256, byte length, row count) - lengths/counts from
# stage9_data_source_audit_v1_1.md; hashes are the frozen v1.1 pins.
PINNED_FILES: dict[str, dict[str, Any]] = {
    "users.csv": {
        "url": f"{RAW_BASE_URL}/data_files/users.csv",
        "sha256": "b07d93573b014e0ae1da822c616e9e811551ad77dc8390fb52a03202f7df0ed1",
        "bytes": 21610,
        "rows": 37,
    },
    "suggestions.csv": {
        "url": f"{RAW_BASE_URL}/data_files/suggestions.csv",
        "sha256": "60ee7896183d7084a084f9a6e8ef2d0afea2e7fecdb41d6b15382ce1745c5ddb",
        "bytes": 4371854,
        "rows": 8274,
    },
    "gfsteps.csv": {
        "url": f"{RAW_BASE_URL}/data_files/gfsteps.csv",
        "sha256": "1c65688ef3ee6cb973ffa089b375947edb832166b00ccb3112fafe2ef72f956c",
        "bytes": 10021829,
        "rows": 197524,
    },
    "jbsteps.csv": {
        "url": f"{RAW_BASE_URL}/data_files/jbsteps.csv",
        "sha256": "bd4a2104037514d8a818465ad483218b56f6c2cd78d57a6643818715aebd77e3",
        "bytes": 17652097,
        "rows": 237865,
    },
}

# ---------------------------------------------------------------------------
# Frozen cohort constants (Stage 9A v1.1)
# ---------------------------------------------------------------------------

ACTIONS = ("none", "walking", "antisedentary")

ACTION_ENCODING: dict[str, tuple[bool, bool, bool]] = {
    # action -> (send, send.active, send.sedentary)
    "none": (False, False, False),
    "walking": (True, True, False),
    "antisedentary": (True, False, True),
}

ASSIGNMENT_PROBABILITIES: dict[str, float] = {
    "none": 0.4,
    "walking": 0.3,
    "antisedentary": 0.3,
}

REQUIRED_OPERATIONAL_FIELDS = (
    "user.index",
    "decision.index",
    "sugg.decision.utime",
    "sugg.decision.slot",
    "is.randomized",
    "send",
    "send.active",
    "send.sedentary",
)

DECISION_SLOTS = (1, 2, 3, 4, 5)
STUDY_DAY_MIN, STUDY_DAY_MAX = 1, 42

ACTIVITY_BUCKET_MAP = {
    "STILL": "STILL",
    "WALKING": "ON_FOOT",
    "RUNNING": "ON_FOOT",
    "ON_FOOT": "ON_FOOT",
    "ON_BICYCLE": "ON_FOOT",
    "IN_VEHICLE": "IN_VEHICLE",
    "IN_ROAD_VEHICLE": "IN_VEHICLE",
    "IN_RAIL_VEHICLE": "IN_VEHICLE",
    "IN_2WHEELER_VEHICLE": "IN_VEHICLE",
}

WEATHER_PRECIPITATION_TOKENS = (
    "rain",
    "snow",
    "sleet",
    "hail",
    "shower",
    "storm",
    "drizzle",
    "thunder",
    "precip",
)

# Study-day column candidates that, when present and nonblank, are used
# directly; otherwise the day is derived from sugg.decision.utime relative to
# the participant's first decision timestamp.  The chosen source is recorded in
# the exclusion-rules manifest.
STUDY_DAY_COLUMN_CANDIDATES = ("study.day.nogap", "study.day", "study.day.no.gap")

TRUTHY = {"true", "1", "yes"}


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def _as_bool(value: Any) -> bool | None:
    """Parse a released logical field; returns None when blank/unparseable."""
    if _is_blank(value):
        return None
    text = str(value).strip().lower()
    if text in TRUTHY:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def _as_int(value: Any) -> int | None:
    if _is_blank(value):
        return None
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    if _is_blank(value):
        return None
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _parse_utime(value: Any) -> datetime | None:
    """Parse HeartSteps utime fields robustly (ISO text or epoch seconds/ms)."""
    if _is_blank(value):
        return None
    text = str(value).strip()
    # epoch seconds / milliseconds
    try:
        number = float(text)
        if abs(number) > 1e12:  # epoch milliseconds
            number /= 1000.0
        return datetime.fromtimestamp(number, tz=UTC)
    except (TypeError, ValueError):
        pass
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S.%f",
    ):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def verify_pinned_files(cache_dir: str | Path) -> dict[str, Any]:
    """Verify all frozen hashes; raise on any mismatch. Returns a report."""
    cache_dir = Path(cache_dir)
    report: dict[str, Any] = {"status": "PASS", "files": {}}
    for name, pin in PINNED_FILES.items():
        path = cache_dir / name
        if not path.exists():
            raise FileNotFoundError(f"missing pinned file {name} in {cache_dir}")
        size = path.stat().st_size
        digest = sha256_file(path)
        entry = {
            "sha256": digest,
            "bytes": size,
            "expected_sha256": pin["sha256"],
            "expected_bytes": pin["bytes"],
            "hash_match": digest == pin["sha256"],
            "bytes_match": size == pin["bytes"],
        }
        if not entry["hash_match"] or not entry["bytes_match"]:
            report["status"] = "FAIL"
        report["files"][name] = entry
    if report["status"] != "PASS":
        raise RuntimeError(
            "HeartSteps pinned-file verification FAILED: " + json.dumps(report)
        )
    return report


def download_pinned_files(cache_dir: str | Path, timeout: int = 120) -> None:
    """Download the pinned release into the cache dir (idempotent)."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    for name, pin in PINNED_FILES.items():
        target = cache_dir / name
        if target.exists() and sha256_file(target) == pin["sha256"]:
            continue
        print(f"[preprocess] downloading {name} from pinned commit ...", flush=True)
        urllib.request.urlretrieve(pin["url"], target)
        digest = sha256_file(target)
        if digest != pin["sha256"] or target.stat().st_size != pin["bytes"]:
            target.unlink(missing_ok=True)
            raise RuntimeError(f"downloaded {name} failed hash verification")


def _read_csv(path: str | Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _csv_value(value: Any) -> str:
    """Deterministic CSV serialization round-trippable by read_csv_rows."""
    if value is None:
        return ""
    if value is True:
        return "True"
    if value is False:
        return "False"
    if isinstance(value, float):
        return repr(value)
    return str(value)


def _row_float(row: dict[str, str], key: str) -> float | None:
    return _as_float(row.get(key))


def _row_int(row: dict[str, str], key: str) -> int | None:
    return _as_int(row.get(key))


def _row_bool(row: dict[str, str], key: str) -> bool | None:
    raw = row.get(key)
    if _is_blank(raw):
        return None
    return str(raw).strip().lower() in {"true", "1"}


def read_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    """Read a preprocessor analysis table back into typed rows for the runner."""
    typed: list[dict[str, Any]] = []
    for row in _read_csv(path):
        typed.append(
            {
                "user_index": int(row["user_index"]),
                "decision_index": _row_int(row, "decision_index"),
                "decision_utime": row.get("decision_utime") or None,
                "decision_utime_epoch": _row_float(row, "decision_utime_epoch"),
                "decision_slot": _row_int(row, "decision_slot"),
                "is_randomized": _row_bool(row, "is_randomized"),
                "action": row.get("action"),
                "avail": _row_bool(row, "avail"),
                "study_day": _row_int(row, "study_day"),
                "study_week": _row_int(row, "study_week"),
                "rel_time_seconds": _row_float(row, "rel_time_seconds"),
                "activity_bucket": row.get("activity_bucket"),
                "location_bucket": row.get("location_bucket"),
                "weather_bucket": row.get("weather_bucket"),
                "prior_step_bucket": row.get("prior_step_bucket"),
                "jbsteps30_raw": _row_float(row, "jbsteps30_raw"),
                "jbsteps30_zero": _row_float(row, "jbsteps30_zero"),
                "gfsteps30": _row_float(row, "gfsteps30"),
                "y": _row_float(row, "y"),
                "y_gf": _row_float(row, "y_gf"),
                "raw_outcome_nonmissing": row.get("raw_outcome_nonmissing") == "True",
                "gf_outcome_nonmissing": row.get("gf_outcome_nonmissing") == "True",
            }
        )
    return typed


# ---------------------------------------------------------------------------
# Frozen derivations
# ---------------------------------------------------------------------------

def reconstruct_action(row: dict[str, str]) -> str | None:
    """Return one of ACTIONS, or None when the encoding is inconsistent.

    Exactly one of the three frozen encodings is valid.  Anything else
    (contradictory flags, incomplete rows) yields None and is counted as
    INVALID by the caller; it is never repaired.
    """
    send = _as_bool(row.get("send"))
    active = _as_bool(row.get("send.active"))
    sedentary = _as_bool(row.get("send.sedentary"))
    if send is None or active is None or sedentary is None:
        return None
    encoding = (send, active, sedentary)
    for action, frozen in ACTION_ENCODING.items():
        if encoding == frozen:
            return action
    return None


def bucket_activity(raw: Any) -> str:
    if _is_blank(raw):
        return "unknown"
    return ACTIVITY_BUCKET_MAP.get(str(raw).strip(), "other")


def bucket_location(raw: Any) -> str:
    if _is_blank(raw):
        return "unknown"
    text = str(raw).strip().lower()
    if text in {"home", "work"}:
        return text
    return "other"


def bucket_weather(raw: Any) -> str:
    if _is_blank(raw):
        return "unknown"
    text = str(raw).strip().lower()
    if any(token in text for token in WEATHER_PRECIPITATION_TOKENS):
        return "precipitation_or_snow"
    return "other"


def bucket_prior_steps(raw: Any) -> str:
    value = _as_float(raw)
    if value is None:
        return "missing"
    if value == 0:
        return "0"
    if value < 200:
        return "1_199"
    return "ge_200"


def study_week_from_day(day: int | None) -> int | None:
    if day is None:
        return None
    return (day - 1) // 7 + 1


def derive_study_day(
    row: dict[str, str],
    user_first_utime: datetime | None,
    study_day_column: str | None,
) -> int | None:
    """Derived study day 1..42 boundary.

    Prefers a released study-day column when present and nonblank; otherwise
    derives day = floor((utime - first_decision_utime)/86400) + 1.  The chosen
    source is recorded in the exclusion-rules manifest so the derivation is
    fully reproducible.
    """
    if study_day_column and not _is_blank(row.get(study_day_column)):
        day = _as_int(row.get(study_day_column))
        if day is not None:
            return day
    utime = _parse_utime(row.get("sugg.decision.utime"))
    if utime is None or user_first_utime is None:
        return None
    delta = (utime - user_first_utime).total_seconds()
    if delta < 0:
        return None
    return int(delta // 86400) + 1


# ---------------------------------------------------------------------------
# Eligibility flow (frozen, fixed order)
# ---------------------------------------------------------------------------

# (rule_id, rule, source_fields, classification, note)
ELIGIBILITY_RULES = (
    (
        "R1",
        "missing_required_operational_fields",
        list(REQUIRED_OPERATIONAL_FIELDS),
        "FROZEN_PREREG",
        "any required operational field blank",
    ),
    (
        "R2",
        "invalid_decision_slot",
        ["sugg.decision.slot"],
        "FROZEN_PREREG",
        "decision slot not in 1..5 or unparseable",
    ),
    (
        "R3",
        "travel_or_technical_decision_gap",
        ["decision.index.nogap"],
        "PUBLIC_RELEASE_OPERATIONALIZATION",
        (
            "rows excluded from the released no-gap decision index; matches the "
            "paper's 390 travel/technical count when the column is present"
        ),
    ),
    (
        "R4",
        "study_day_outside_1_42",
        ["sugg.decision.utime", "study.day.nogap", "study.day"],
        "PUBLIC_RELEASE_OPERATIONALIZATION",
        "derived study day missing or outside 1..42",
    ),
    (
        "R5",
        "not_available",
        ["avail"],
        "FROZEN_PREREG",
        "avail != True",
    ),
    (
        "R6",
        "inconsistent_action_encoding",
        ["send", "send.active", "send.sedentary"],
        "FROZEN_PREREG",
        "row does not match exactly one frozen action encoding",
    ),
    (
        "R7",
        "duplicate_decision_key",
        ["user.index", "decision.index"],
        "FROZEN_PREREG",
        "duplicate (user.index, decision.index)",
    ),
    (
        "R8",
        "invalid_primary_outcome",
        ["jbsteps30.zero"],
        "FROZEN_PREREG",
        "jbsteps30.zero blank, non-finite or negative",
    ),
)


def apply_eligibility(
    rows: list[dict[str, str]],
    users: list[dict[str, str]],
    duplicate_policy: str = "fail",
) -> dict[str, Any]:
    """Apply the frozen eligibility rules in exact order; returns flow result.

    ``duplicate_policy``: "fail" (preregistered default; raises when R7 fires)
    or "report" (records the count and continues - preflight diagnostics only).
    """
    user_ids = {str(row.get("user.index", "")).strip() for row in users}
    first_utime_by_user: dict[str, datetime] = {}
    for row in rows:
        uid = str(row.get("user.index", "")).strip()
        utime = _parse_utime(row.get("sugg.decision.utime"))
        if utime is not None:
            first_utime_by_user.setdefault(uid, utime)
            first_utime_by_user[uid] = min(first_utime_by_user[uid], utime)

    study_day_column = None
    if rows:
        header = set(rows[0].keys())
        for candidate in STUDY_DAY_COLUMN_CANDIDATES:
            if candidate in header:
                study_day_column = candidate
                break

    rule_stats = {rule[0]: {"rule": rule[1], "source_fields": rule[2],
                            "classification": rule[3], "note": rule[4],
                            "excluded": 0, "remaining": 0} for rule in ELIGIBILITY_RULES}

    remaining: list[dict[str, str]] = list(rows)
    raw_total = len(remaining)
    for rule_id, _, _, _, _ in ELIGIBILITY_RULES:
        kept: list[dict[str, str]] = []
        for row in remaining:
            if _rule_excludes(rule_id, row, user_ids, first_utime_by_user,
                              study_day_column):
                rule_stats[rule_id]["excluded"] += 1
            else:
                kept.append(row)
        remaining = kept
        rule_stats[rule_id]["remaining"] = len(remaining)

    duplicates = _count_duplicate_keys(remaining)
    if duplicates > 0 and duplicate_policy == "fail":
        raise RuntimeError(
            f"duplicate (user.index, decision.index) keys present ({duplicates}); "
            "preregistered duplicate_policy=fail blocks the run"
        )

    return {
        "raw_total": raw_total,
        "final_rows": remaining,
        "rule_stats": rule_stats,
        "duplicates": duplicates,
        "study_day_column": study_day_column,
        "first_utime_by_user": first_utime_by_user,
    }


def _rule_excludes(
    rule_id: str,
    row: dict[str, str],
    user_ids: set[str],
    first_utime_by_user: dict[str, datetime],
    study_day_column: str | None,
) -> bool:
    if rule_id == "R1":
        return any(_is_blank(row.get(field)) for field in REQUIRED_OPERATIONAL_FIELDS)
    if rule_id == "R2":
        slot = _as_int(row.get("sugg.decision.slot"))
        return slot not in DECISION_SLOTS
    if rule_id == "R3":
        if "decision.index.nogap" not in row:
            return False  # column absent -> handled by the manifest note
        return _is_blank(row.get("decision.index.nogap"))
    if rule_id == "R4":
        uid = str(row.get("user.index", "")).strip()
        day = derive_study_day(row, first_utime_by_user.get(uid), study_day_column)
        return day is None or not (STUDY_DAY_MIN <= day <= STUDY_DAY_MAX)
    if rule_id == "R5":
        return _as_bool(row.get("avail")) is not True
    if rule_id == "R6":
        return reconstruct_action(row) not in ACTIONS
    if rule_id == "R7":
        return False  # handled after the pass; needs global duplicate counting
    if rule_id == "R8":
        outcome = _as_float(row.get("jbsteps30.zero"))
        return outcome is None or outcome < 0
    raise KeyError(rule_id)


def _count_duplicate_keys(rows: list[dict[str, str]]) -> int:
    seen: set[tuple[str, str]] = set()
    duplicates = 0
    for row in rows:
        key = (str(row.get("user.index", "")).strip(),
               str(row.get("decision.index", "")).strip())
        if key in seen:
            duplicates += 1
        else:
            seen.add(key)
    return duplicates


def build_analysis_rows(
    final_rows: list[dict[str, str]],
    flow: dict[str, Any],
) -> list[dict[str, Any]]:
    """Deterministic analysis table for the external evaluator (no raw files)."""
    study_day_column = flow["study_day_column"]
    first_utime_by_user = flow["first_utime_by_user"]
    analysis = []
    for row in final_rows:
        uid = str(row.get("user.index", "")).strip()
        utime = _parse_utime(row.get("sugg.decision.utime"))
        first = first_utime_by_user.get(uid)
        rel_seconds = (
            (utime - first).total_seconds() if utime is not None and first is not None else None
        )
        day = derive_study_day(row, first, study_day_column)
        raw_outcome = _as_float(row.get("jbsteps30"))
        zero_outcome = _as_float(row.get("jbsteps30.zero"))
        gf_outcome = _as_float(row.get("gfsteps30"))
        analysis.append(
            {
                "user_index": uid,
                "decision_index": _as_int(row.get("decision.index")),
                "decision_utime": utime.isoformat() if utime else None,
                "decision_utime_epoch": utime.timestamp() if utime else None,
                "decision_slot": _as_int(row.get("sugg.decision.slot")),
                "is_randomized": _as_bool(row.get("is.randomized")),
                "action": reconstruct_action(row),
                "avail": _as_bool(row.get("avail")),
                "study_day": day,
                "study_week": study_week_from_day(day),
                "rel_time_seconds": rel_seconds,
                "activity_bucket": bucket_activity(row.get("recognized.activity")),
                "location_bucket": bucket_location(row.get("dec.location.category")),
                "weather_bucket": bucket_weather(row.get("dec.weather.condition")),
                "prior_step_bucket": bucket_prior_steps(row.get("jbsteps30pre")),
                "jbsteps30_raw": raw_outcome,
                "jbsteps30_zero": zero_outcome,
                "gfsteps30": gf_outcome,
                "y": math.log(zero_outcome + 0.5) if zero_outcome is not None else None,
                "y_gf": math.log(gf_outcome + 0.5) if gf_outcome is not None else None,
                "raw_outcome_nonmissing": raw_outcome is not None,
                "gf_outcome_nonmissing": gf_outcome is not None,
            }
        )
    return analysis


# ---------------------------------------------------------------------------
# Manifests
# ---------------------------------------------------------------------------

def emit_flow_manifests(
    flow: dict[str, Any],
    analysis_rows: list[dict[str, Any]],
    users: list[dict[str, str]],
    out_dir: str | Path,
) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rule_stats = flow["rule_stats"]
    final_rows = flow["final_rows"]

    action_counts = {"none": 0, "walking": 0, "antisedentary": 0}
    invalid_action_rows = 0
    for row in final_rows:
        action = reconstruct_action(row)
        if action in action_counts:
            action_counts[action] += 1
        else:
            invalid_action_rows += 1

    ops_rows = flow["raw_total"] - rule_stats["R1"]["excluded"]
    flow_json = {
        "manifest_id": "stage9_preprocessing_flow_v1",
        "schema_version": "1.1",
        "source": {
            "name": "HeartSteps V1",
            "commit": PINNED_COMMIT,
            "raw_rows": flow["raw_total"],
        },
        "flow": {
            "raw_rows": flow["raw_total"],
            "rows_with_operational_fields": ops_rows,
            "rows_after_travel_or_technical": rule_stats["R3"]["remaining"],
            "day_1_42_rows": rule_stats["R4"]["remaining"],
            "available_rows": rule_stats["R5"]["remaining"],
            "action_consistent_rows": rule_stats["R6"]["remaining"],
            "final_primary_rows": len(final_rows),
        },
        "action_counts": action_counts,
        "invalid_action_rows": invalid_action_rows,
        "duplicates": flow["duplicates"],
        "participant_continuity": {
            "unique_users_in_suggestions": len(
                {str(row.get("user.index", "")).strip() for row in final_rows}
            ),
            "unique_users_in_users_table": len(users),
            "users_with_primary_rows": len(
                {str(row.get("user.index", "")).strip() for row in final_rows}
            ),
            "expected_public_users": 37,
        },
        "study_day_source": flow["study_day_column"] or "derived_from_utime",
        "paper_comparison_only": {
            "paper_included_decision_points": 7540,
            "paper_available_decision_points": 6061,
            "note": "comparison targets only; no identity is claimed",
        },
        "primary_outcome": "ln(jbsteps30.zero + 0.5)",
        "formal_cf_result_computed": False,
    }
    with open(out_dir / "preprocessing_flow_v1.json", "w", encoding="utf-8") as handle:
        json.dump(flow_json, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    per_user: dict[str, dict[str, int]] = {}
    for row in final_rows:
        uid = str(row.get("user.index", "")).strip()
        entry = per_user.setdefault(uid, {"primary_rows": 0, "none": 0,
                                          "walking": 0, "antisedentary": 0})
        entry["primary_rows"] += 1
        action = reconstruct_action(row)
        if action in entry:
            entry[action] += 1
    with open(out_dir / "preprocessing_flow_by_user_v1.csv", "w",
              encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["user.index", "primary_rows", "none", "walking",
                         "antisedentary"])
        for uid in sorted(per_user, key=lambda value: int(value)):
            entry = per_user[uid]
            writer.writerow([uid, entry["primary_rows"], entry["none"],
                             entry["walking"], entry["antisedentary"]])

    rules_out = []
    running_total = flow["raw_total"]
    for rule_id, rule_name, sources, classification, note in ELIGIBILITY_RULES:
        stats = rule_stats[rule_id]
        running_total -= stats["excluded"]
        entry = {
            "rule_id": rule_id,
            "rule": rule_name,
            "source_fields": sources,
            "excluded": stats["excluded"],
            "remaining_after": running_total,
            "classification": classification,
            "note": note,
        }
        if rule_id == "R3" and "decision.index.nogap" not in (
            final_rows[0].keys() if final_rows else {}
        ):
            entry["reconstructability"] = "NOT_EXACTLY_RECONSTRUCTABLE_FROM_PUBLIC_FIELDS"
        if rule_id == "R4":
            entry["day_source"] = flow["study_day_column"] or "derived_from_utime"
            entry["reconstructability"] = (
                "EXACTLY_RECONSTRUCTABLE_FROM_PUBLIC_FIELDS"
                if flow["study_day_column"]
                else "DERIVED_DETERMINISTICALLY_FROM_PUBLIC_FIELDS"
            )
        rules_out.append(entry)

    rules_json = {
        "manifest_id": "stage9_public_release_exclusion_rules_v1",
        "schema_version": "1.1",
        "frozen_order": [rule[1] for rule in ELIGIBILITY_RULES],
        "rules": rules_out,
        "final_cohort": {
            "definition": "reproducible Stage 9 public-release cohort; not a "
                          "fabricated reconstruction of the paper cohort",
            "rows": len(final_rows),
        },
        "paper_comparison_only": {
            "paper_included_decision_points": 7540,
            "paper_available_decision_points": 6061,
            "note": "comparison targets only; no identity is claimed",
        },
    }
    with open(out_dir / "stage9_public_release_exclusion_rules_v1.json", "w",
              encoding="utf-8") as handle:
        json.dump(rules_json, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    with open(out_dir / "preprocessing_analysis_sha256_v1.json", "w",
              encoding="utf-8") as handle:
        json.dump({"analysis_rows": len(analysis_rows)}, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run_preprocessing(
    cache_dir: str | Path,
    out_dir: str | Path,
    verify_hashes: bool = True,
    duplicate_policy: str = "fail",
) -> dict[str, Any]:
    """Full preprocessing pipeline; returns a summary dict."""
    cache_dir = Path(cache_dir)
    out_dir = Path(out_dir)
    verification = verify_pinned_files(cache_dir) if verify_hashes else None

    users = _read_csv(cache_dir / "users.csv")
    suggestions = _read_csv(cache_dir / "suggestions.csv")
    if not suggestions:
        raise ValueError("suggestions.csv is empty")

    flow = apply_eligibility(suggestions, users, duplicate_policy=duplicate_policy)
    if not flow["final_rows"]:
        raise ValueError(
            "the frozen eligibility rules exclude every row; refusing to emit "
            "an empty analysis table (check the flow manifest for rule counts)"
        )
    analysis_rows = build_analysis_rows(flow["final_rows"], flow)
    emit_flow_manifests(flow, analysis_rows, users, out_dir)

    with open(cache_dir / "analysis_table_v1.csv", "w", encoding="utf-8",
              newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(analysis_rows[0].keys()), extrasaction="ignore"
        )
        writer.writeheader()
        for row in analysis_rows:
            writer.writerow({key: _csv_value(value) for key, value in row.items()})

    return {
        "verification": verification,
        "raw_rows": flow["raw_total"],
        "final_primary_rows": len(flow["final_rows"]),
        "users": len(users),
        "analysis_table": str(cache_dir / "analysis_table_v1.csv"),
        "flow_manifest": str(out_dir / "preprocessing_flow_v1.json"),
        "exclusion_rules_manifest": str(
            out_dir / "stage9_public_release_exclusion_rules_v1.json"
        ),
    }


def _cli() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", default=str(Path(".runtime") / "stage9_heartsteps"))
    parser.add_argument("--out-dir", default=str(Path("evaluation/stage9/preformal")))
    parser.add_argument("--no-download", action="store_true",
                        help="fail instead of downloading when files are missing")
    parser.add_argument("--no-verify-hashes", action="store_true",
                        help="dev/test only: skip frozen hash verification")
    parser.add_argument("--duplicate-policy", choices=("fail", "report"),
                        default="fail")
    args = parser.parse_args()

    cache_dir = Path(args.cache_dir)
    if not args.no_download:
        try:
            download_pinned_files(cache_dir)
        except Exception as error:  # noqa: BLE001 - surfaced for the operator
            print(f"[preprocess] download failed: {error}", file=sys.stderr)
            print("[preprocess] place the pinned files in the cache dir and "
                  "re-run with --no-download", file=sys.stderr)
            return 2
    try:
        summary = run_preprocessing(
            cache_dir,
            args.out_dir,
            verify_hashes=not args.no_verify_hashes,
            duplicate_policy=args.duplicate_policy,
        )
    except Exception as error:  # noqa: BLE001
        print(f"[preprocess] FAILED: {error}", file=sys.stderr)
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
