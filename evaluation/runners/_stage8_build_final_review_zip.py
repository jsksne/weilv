"""Stage 8 — build the final human-review-prep bundle ZIP."""

import hashlib
import json
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PREP_DIR = ROOT / "evaluation" / "stage8" / "final_human_review_prep_v1"
REVIEWS = ROOT / "evaluation" / "reviews"
ZIP_PATH = ROOT / "evaluation" / "stage8_final_human_review_prep_bundle.zip"

ENTRIES = [
    (PREP_DIR / "factor_coverage_status.md", "factor_coverage_status.md"),
    (PREP_DIR / "stage8_soft_preference_human_review_v1.csv", "stage8_soft_preference_human_review_v1.csv"),
    (PREP_DIR / "stage8_soft_preference_human_review_instructions_v1.md", "stage8_soft_preference_human_review_instructions_v1.md"),
    (PREP_DIR / "final_closeout_status.json", "final_closeout_status.json"),
    (PREP_DIR / "raw_results_sha256.txt", "raw_results_sha256.txt"),
    (REVIEWS / "stage8_agentic_factor_coverage_human_review_v1.SUPERSEDED.md", "factor_review_superseded_note.md"),
    (REVIEWS / "stage8_agentic_factor_coverage_human_review_v1.csv", "factor_review/SUPERSEDED_stage8_agentic_factor_coverage_human_review_v1.csv"),
]

MANIFEST = {
    "artifact": "stage8_final_human_review_prep_bundle",
    "created_at": datetime.now(UTC).isoformat(),
    "original_frozen_run_id": "20260818T020417Z_stage8_formal",
    "raw_results_sha256": (PREP_DIR / "raw_results_sha256.txt").read_text(encoding="utf-8").strip().splitlines()[1],
    "note": "derived-artifact-only closeout prep; NO production rerun",
    "entries": [archive for _, archive in ENTRIES],
}


def main() -> None:
    missing = [path for path, _ in ENTRIES if not path.exists()]
    if missing:
        raise SystemExit(f"missing files: {missing}")
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path, archive in ENTRIES:
            bundle.write(path, archive)
        bundle.writestr("manifest.json", json.dumps(MANIFEST, ensure_ascii=False, indent=2))
    sha = hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest()
    print(f"zip: {ZIP_PATH}")
    print(f"sha256: {sha}")
    (PREP_DIR / "acceptance_bundle_sha256.txt").write_text(
        f"{ZIP_PATH.name}\n{sha}\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
