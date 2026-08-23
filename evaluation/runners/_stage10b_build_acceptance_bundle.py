"""Stage 10B — build the acceptance bundle ZIP and report its SHA-256."""

import hashlib
import json
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ZIP_PATH = ROOT / "evaluation" / "stage10b_feedback_loop_acceptance_bundle.zip"
ARTIFACT_DIR = ROOT / ".runtime" / "stage10b_bundle"
DEMO_REPORT = ROOT / ".runtime" / "stage10b_demo" / "stage10b_demo_report.json"

ENTRIES = [
    # changed source files
    (ROOT / "src/weilv/feedback_loop.py", "source/feedback_loop.py"),
    (ROOT / "src/weilv/user_memory.py", "source/user_memory.py"),
    (ROOT / "src/weilv/api/app.py", "source/api_app.py"),
    (ROOT / "src/weilv/api/schemas.py", "source/api_schemas.py"),
    (ROOT / "src/weilv/elasticsearch_indices.py", "source/elasticsearch_indices.py"),
    (ROOT / "src/weilv/questionnaire.py", "source/questionnaire.py"),  # unchanged, context
    # tests and results
    (ROOT / "tests/test_feedback_loop.py", "tests/test_feedback_loop.py"),
    (ROOT / "tests/test_api.py", "tests/test_api.py"),
    (ROOT / "tests/test_elasticsearch_indices.py", "tests/test_elasticsearch_indices.py"),
    (ARTIFACT_DIR / "backend_tests.txt", "tests/backend_tests.txt"),
    (ARTIFACT_DIR / "frontend_tests.txt", "tests/frontend_tests.txt"),
    # frontend
    (ROOT / "frontend/src/api/types.ts", "frontend/types.ts"),
    (ROOT / "frontend/src/composables/useFeedbackFlow.ts", "frontend/useFeedbackFlow.ts"),
    (ROOT / "frontend/src/components/FeedbackForm.vue", "frontend/FeedbackForm.vue"),
    (ROOT / "frontend/src/style.css", "frontend/style.css"),
    (ROOT / "frontend/src/feedback-flow.test.ts", "frontend/feedback-flow.test.ts"),
    # documentation
    (ROOT / "docs/stage10/stage10b_feedback_memory_loop.md", "docs/stage10b_feedback_memory_loop.md"),
    # demo fixture and report
    (ROOT / "scripts/stage10b_feedback_loop_demo.py", "demo/stage10b_feedback_loop_demo.py"),
    (DEMO_REPORT, "demo/stage10b_demo_report.json"),
]

MANIFEST = {
    "artifact": "stage10b_feedback_loop_acceptance_bundle",
    "created_at": datetime.now(UTC).isoformat(),
    "entries": [archive for _, archive in ENTRIES],
    "secrets_excluded": [".env", ".env.example", "DASHSCOPE_API_KEY", "ES passwords"],
    "notes": "Feedback writes only task_feedback memory through the frozen gate; "
    "Safety/Evidence/Output-Guard/Basic-RAG/Agentic/CF unchanged.",
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
    sha_path = ROOT / "evaluation" / "stage10b_feedback_loop_acceptance_bundle_sha256.txt"
    sha_path.write_text(f"{ZIP_PATH.name}\n{sha}\n", encoding="utf-8")
    print(f"zip: {ZIP_PATH}")
    print(f"sha256: {sha}")
    print(f"sha256 file: {sha_path}")


if __name__ == "__main__":
    main()
