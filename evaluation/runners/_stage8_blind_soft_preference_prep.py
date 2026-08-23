"""Stage 8 — system-blinded soft preference human review preparation.

Derived-artifact-only. Uses ONLY the frozen formal run outputs. No production
call, no model call, no raw-results / Gold / claims modification.

Creates:
- reviewer sheet: evaluation/reviews/stage8_soft_preference_blinded_review_v2.csv
- private mapping: evaluation/reviews/private/stage8_soft_preference_blind_mapping_v2.csv
- instructions:   evaluation/reviews/stage8_soft_preference_blinded_review_instructions_v2.md
- prep dir:       evaluation/stage8/soft_preference_blind_review_prep_v2/
- reviewer ZIP / audit ZIP under evaluation/
"""

import csv
import hashlib
import json
import random
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.runners.run_stage8_formal_evaluation import (  # noqa: E402
    FROZEN_GOLD,
    SYSTEMS,
    load_formal_micro_tasks,
    read_jsonl,
)

RUN_ID = "20260818T020417Z_stage8_formal"
RUN_DIR = ROOT / "evaluation" / "runs" / RUN_ID
REVIEWS = ROOT / "evaluation" / "reviews"
PRIVATE = REVIEWS / "private"
PREP_DIR = ROOT / "evaluation" / "stage8" / "soft_preference_blind_review_prep_v2"
V1_SHEET = REVIEWS / "stage8_soft_preference_human_review_v1.csv"
BLIND_SHEET = REVIEWS / "stage8_soft_preference_blinded_review_v2.csv"
BLIND_MAP = PRIVATE / "stage8_soft_preference_blind_mapping_v2.csv"
INSTRUCTIONS = REVIEWS / "stage8_soft_preference_blinded_review_instructions_v2.md"
REVIEWER_ZIP = ROOT / "evaluation" / "stage8_soft_preference_blinded_review_package.zip"
AUDIT_ZIP = ROOT / "evaluation" / "stage8_soft_preference_blinding_audit_bundle.zip"

RAW_SHA_EXPECTED = "906b4ed190594e5db2831e6240180b57b93963408f38750f309eb3922a3ba84d"
BLIND_SEED = 20260818  # deterministic, recorded

SHEET_FIELDS = (
    "review_id", "scenario", "gold_soft_preferences",
    "selected_task_id", "selected_task_title",
    "reviewer_A_alignment", "reviewer_A_notes",
    "reviewer_B_alignment", "reviewer_B_notes",
    "reviewer_C_alignment", "reviewer_C_notes",
    "consensus_alignment", "consensus_status", "consensus_notes",
)
MAP_FIELDS = ("review_id", "case_id", "system", "selected_task_id")

INSTRUCTIONS_TEXT = """# Stage 8 — Blinded Soft Preference Human Review Instructions (v2)

## Setup

This review is **system-blinded**. The sheet you received contains 33 rows
identified only by opaque review IDs (SP-001 .. SP-033). The producing system
(Basic / Personal / Agentic), the Gold labels, and all metrics are hidden and
must remain hidden until consensus is finalized.

## Question for every row

For each row answer ONLY:

> Does the selected formal task **meaningfully contradict** the stated soft
> preference in this scenario?

## Judgement values

- **ALIGNED** — the selected task does not meaningfully contradict the stated
  soft preference.
- **MISALIGNED** — the selected task meaningfully contradicts the stated soft
  preference.

## What reviewers must NOT use

- The producing system identity (not visible)
- Gold Utility or any aggregate metric (not visible)
- Preferred / Acceptable / Invalid Gold labels (not visible)
- Claim results (not visible)
- Other reviewers' decisions

Reviewers judge ONLY the question above, from the scenario text, the stated
soft preference, and the selected task id/title semantics.

## Process

1. Three reviewers each complete ALL 33 rows independently, filling only their
   own reviewer_A/B/C_alignment and notes columns.
2. Do NOT discuss decisions until all independent judgments are complete.
3. Afterward, disagreements may be discussed until consensus.
4. A final **consensus_alignment** is required for each row.
5. `consensus_status` = PASS (three agree) or DISCUSSED (consensus after
   discussion); DISAGREEMENT if consensus cannot be reached (with notes).

Reviewers MUST NOT receive the private system mapping before consensus is
finalized.
"""


def write_csv(path: Path, rows: list[dict], fields: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    PREP_DIR.mkdir(parents=True, exist_ok=True)

    # ---- frozen run integrity -------------------------------------------------
    raw_sha = hashlib.sha256((RUN_DIR / "raw_results.jsonl").read_bytes()).hexdigest()
    if raw_sha != RAW_SHA_EXPECTED:
        raise SystemExit(f"raw_results.jsonl SHA mismatch: {raw_sha}")

    gold = read_jsonl(FROZEN_GOLD)
    records = read_jsonl(RUN_DIR / "raw_results.jsonl")
    task_by_id = {task["task_id"]: task for task in load_formal_micro_tasks()}

    # ---- build the 33 frozen source rows --------------------------------------
    soft_cases = [case for case in gold if case.get("gold_soft_preferences")]
    assert len(soft_cases) == 11
    source = []
    for case in soft_cases:
        for system in SYSTEMS:
            record = next(
                r for r in records
                if r["case_id"] == case["case_id"] and r["system"] == system
            )
            result = record.get("result")
            selected_id = result.get("selected_task_id") if result else None
            source.append(
                {
                    "case_id": case["case_id"],
                    "system": system,
                    "scenario": case["query"][:80],
                    "gold_soft_preferences": " | ".join(case["gold_soft_preferences"]),
                    "selected_task_id": selected_id,
                    "selected_task_title": (
                        task_by_id[selected_id]["title"] if selected_id in task_by_id else ""
                    ),
                }
            )
    assert len(source) == 33

    # ---- deterministic single randomization of the 33 rows ----------------------
    rng = random.Random(BLIND_SEED)
    order = list(range(33))
    rng.shuffle(order)
    blinded = []
    mapping = []
    for position, source_index in enumerate(order, start=1):
        review_id = f"SP-{position:03d}"
        item = source[source_index]
        blinded.append(
            {
                "review_id": review_id,
                "scenario": item["scenario"],
                "gold_soft_preferences": item["gold_soft_preferences"],
                "selected_task_id": item["selected_task_id"],
                "selected_task_title": item["selected_task_title"],
                "reviewer_A_alignment": "",
                "reviewer_A_notes": "",
                "reviewer_B_alignment": "",
                "reviewer_B_notes": "",
                "reviewer_C_alignment": "",
                "reviewer_C_notes": "",
                "consensus_alignment": "",
                "consensus_status": "",
                "consensus_notes": "",
            }
        )
        mapping.append(
            {
                "review_id": review_id,
                "case_id": item["case_id"],
                "system": item["system"],
                "selected_task_id": item["selected_task_id"],
            }
        )

    write_csv(BLIND_SHEET, blinded, SHEET_FIELDS)
    write_csv(BLIND_MAP, mapping, MAP_FIELDS)

    # ---- blinding integrity ------------------------------------------------------
    def sheet_json():
        with BLIND_SHEET.open(encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))

    def map_json():
        with BLIND_MAP.open(encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))

    sheet = sheet_json()
    mapping_rows = map_json()
    sheet_text = json.dumps(sheet, ensure_ascii=False)
    visible_fields = set(SHEET_FIELDS)
    integrity = {
        "review_rows": len(sheet),
        "unique_review_ids": len({row["review_id"] for row in sheet}),
        "source_rows": len(source),
        "mapping_rows": len(mapping_rows),
        "bijection_source_to_blinded": (
            len({(row["case_id"], row["system"]) for row in mapping_rows}) == 33
            and len({row["review_id"] for row in mapping_rows}) == 33
        ),
        "applicable_cases": len({row["case_id"] for row in mapping_rows}),
        "basic_rows": sum(1 for row in mapping_rows if row["system"] == "basic"),
        "personal_rows": sum(1 for row in mapping_rows if row["system"] == "personal"),
        "agentic_rows": sum(1 for row in mapping_rows if row["system"] == "agentic"),
        "scenario_unchanged": all(
            row["scenario"]
            == next(s for s in source if s["case_id"] == m["case_id"] and s["system"] == m["system"])["scenario"]
            for row, m in zip(sheet, mapping_rows)
        ),
        "soft_preference_unchanged": all(
            row["gold_soft_preferences"]
            == next(s for s in source if s["case_id"] == m["case_id"] and s["system"] == m["system"])["gold_soft_preferences"]
            for row, m in zip(sheet, mapping_rows)
        ),
        "selected_task_unchanged": all(
            row["selected_task_id"] == m["selected_task_id"] and row["selected_task_title"]
            == next(s for s in source if s["case_id"] == m["case_id"] and s["system"] == m["system"])["selected_task_title"]
            for row, m in zip(sheet, mapping_rows)
        ),
        "reviewer_visible_system_labels": sum(
            sheet_text.count(word) for word in ("basic", "personal", "agentic")
        ),
        "reviewer_visible_aggregate_metrics": sum(
            sheet_text.count(word) for word in ("utility", "metric", "score", "rate")
        ),
        "reviewer_visible_gold_task_labels": sum(
            sheet_text.count(word) for word in ("preferred", "acceptable", "invalid")
        ),
        "reviewer_visible_case_id": sheet_text.count("AGX-"),
        "reviewer_fields_blank": all(
            not row[k] for row in sheet
            for k in (
                "reviewer_A_alignment", "reviewer_A_notes",
                "reviewer_B_alignment", "reviewer_B_notes",
                "reviewer_C_alignment", "reviewer_C_notes",
                "consensus_alignment", "consensus_status", "consensus_notes",
            )
        ),
        "reviewer_visible_columns": sorted(visible_fields),
        "randomization": {
            "seed": BLIND_SEED,
            "method": "single deterministic shuffle of the 33 frozen source rows; opaque IDs SP-001..SP-033 assigned in shuffled order",
            "case_id_and_system_removed": True,
        },
    }
    ok = (
        integrity["review_rows"] == 33
        and integrity["unique_review_ids"] == 33
        and integrity["source_rows"] == 33
        and integrity["mapping_rows"] == 33
        and integrity["bijection_source_to_blinded"]
        and integrity["basic_rows"] == 11
        and integrity["personal_rows"] == 11
        and integrity["agentic_rows"] == 11
        and integrity["scenario_unchanged"]
        and integrity["soft_preference_unchanged"]
        and integrity["selected_task_unchanged"]
        and integrity["reviewer_visible_system_labels"] == 0
        and integrity["reviewer_visible_aggregate_metrics"] == 0
        and integrity["reviewer_visible_gold_task_labels"] == 0
        and integrity["reviewer_visible_case_id"] == 0
        and integrity["reviewer_fields_blank"]
    )
    integrity["all_checks_pass"] = ok
    integrity["generated_at"] = datetime.now(UTC).isoformat()
    (PREP_DIR / "blinding_integrity.json").write_text(
        json.dumps(integrity, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # ---- instructions --------------------------------------------------------------
    INSTRUCTIONS.write_text(INSTRUCTIONS_TEXT, encoding="utf-8")
    (PREP_DIR / "review_instructions.md").write_text(INSTRUCTIONS_TEXT, encoding="utf-8")

    # ---- formal run reference -------------------------------------------------------
    formal_ref = {
        "original_frozen_run_id": RUN_ID,
        "raw_results_sha256": raw_sha,
        "gold_dataset": "agentic_complex_gold_frozen_v1_2.jsonl",
        "source_rows": 33,
        "blinding_seed": BLIND_SEED,
        "private_mapping_path": "evaluation/reviews/private/stage8_soft_preference_blind_mapping_v2.csv",
        "note": "system-blinded soft preference human review prep; derived artifacts only; no production rerun",
    }
    (PREP_DIR / "formal_run_reference.json").write_text(
        json.dumps(formal_ref, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # ---- mark v1 sheet superseded ----------------------------------------------------
    (REVIEWS / "stage8_soft_preference_human_review_v1.SUPERSEDED.md").write_text(
        "SUPERSEDED_BY_SYSTEM_BLINDED_REVIEW_V2\n\n"
        "The v1 sheet exposed the system column and grouped rows by system within "
        "cases, which could bias human semantic judgment. It is preserved for audit "
        "history; its reviewer fields were never filled and must remain blank. "
        "Reviewers use stage8_soft_preference_blinded_review_v2.csv instead.\n",
        encoding="utf-8",
    )

    # ---- reviewer package ZIP (ONLY sheet + instructions) ----------------------------
    with zipfile.ZipFile(REVIEWER_ZIP, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.write(BLIND_SHEET, "stage8_soft_preference_blinded_review_v2.csv")
        bundle.write(INSTRUCTIONS, "stage8_soft_preference_blinded_review_instructions_v2.md")
    reviewer_zip_sha = hashlib.sha256(REVIEWER_ZIP.read_bytes()).hexdigest()

    # ---- audit bundle ZIP --------------------------------------------------------------
    with zipfile.ZipFile(AUDIT_ZIP, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.write(BLIND_SHEET, "review_sheet/stage8_soft_preference_blinded_review_v2.csv")
        bundle.write(BLIND_MAP, "private_mapping/stage8_soft_preference_blind_mapping_v2.csv")
        bundle.write(PREP_DIR / "blinding_integrity.json", "audit/blinding_integrity.json")
        bundle.write(INSTRUCTIONS, "instructions/stage8_soft_preference_blinded_review_instructions_v2.md")
        bundle.write(PREP_DIR / "formal_run_reference.json", "audit/formal_run_reference.json")
        bundle.writestr(
            "manifest.json",
            json.dumps(
                {
                    "artifact": "stage8_soft_preference_blinding_audit_bundle",
                    "original_frozen_run_id": RUN_ID,
                    "raw_results_sha256": raw_sha,
                    "blinding_seed": BLIND_SEED,
                    "note": "includes PRIVATE system mapping - audit use only, not for reviewers",
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    audit_zip_sha = hashlib.sha256(AUDIT_ZIP.read_bytes()).hexdigest()

    (PREP_DIR / "reviewer_package_sha256.txt").write_text(
        f"{REVIEWER_ZIP.name}\n{reviewer_zip_sha}\n", encoding="utf-8"
    )
    (PREP_DIR / "audit_bundle_sha256.txt").write_text(
        f"{AUDIT_ZIP.name}\n{audit_zip_sha}\n", encoding="utf-8"
    )

    print(json.dumps(
        {
            "blinding_integrity": {k: v for k, v in integrity.items() if k != "reviewer_visible_columns"},
            "reviewer_zip": str(REVIEWER_ZIP.name),
            "reviewer_zip_sha256": reviewer_zip_sha,
            "audit_zip": str(AUDIT_ZIP.name),
            "audit_zip_sha256": audit_zip_sha,
        },
        ensure_ascii=False, indent=2, sort_keys=True,
    ))


if __name__ == "__main__":
    main()
