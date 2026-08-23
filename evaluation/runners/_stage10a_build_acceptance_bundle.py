"""Stage 10A — build the acceptance bundle ZIP and report its SHA-256."""

import hashlib
import json
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from weilv import questionnaire as q

ZIP_PATH = ROOT / "evaluation" / "stage10a_questionnaire_acceptance_bundle.zip"
ARTIFACT_DIR = ROOT / ".runtime" / "stage10a_bundle"
DEMO_REPORT = ROOT / ".runtime" / "stage10a_demo" / "stage10a_demo_report.json"

ENTRIES = [
    # changed source files
    (ROOT / "src/weilv/questionnaire.py", "source/questionnaire.py"),
    (ROOT / "src/weilv/user_memory.py", "source/user_memory.py"),
    (ROOT / "src/weilv/elasticsearch_indices.py", "source/elasticsearch_indices.py"),
    (ROOT / "src/weilv/api/app.py", "source/api_app.py"),
    (ROOT / "src/weilv/api/schemas.py", "source/api_schemas.py"),
    # questionnaire schema + memory mapping
    (ARTIFACT_DIR / "questionnaire_schema.json", "schema/questionnaire_schema.json"),
    (ARTIFACT_DIR / "memory_mapping.json", "schema/memory_mapping.json"),
    # tests and results
    (ROOT / "tests/test_questionnaire.py", "tests/test_questionnaire.py"),
    (ARTIFACT_DIR / "backend_tests.txt", "tests/backend_tests.txt"),
    (ARTIFACT_DIR / "frontend_tests.txt", "tests/frontend_tests.txt"),
    # frontend
    (ROOT / "frontend/src/api/types.ts", "frontend/types.ts"),
    (ROOT / "frontend/src/api/client.ts", "frontend/client.ts"),
    (ROOT / "frontend/src/composables/useQuestionnaire.ts", "frontend/useQuestionnaire.ts"),
    (ROOT / "frontend/src/components/ColdStartQuestionnaire.vue", "frontend/ColdStartQuestionnaire.vue"),
    (ROOT / "frontend/src/App.vue", "frontend/App.vue"),
    (ROOT / "frontend/src/style.css", "frontend/style.css"),
    (ROOT / "frontend/src/questionnaire-flow.test.ts", "frontend/questionnaire-flow.test.ts"),
    # documentation
    (
        ROOT / "docs/stage10/stage10a_questionnaire_and_cold_start_memory.md",
        "docs/stage10a_questionnaire_and_cold_start_memory.md",
    ),
    # demo fixture and report
    (ROOT / "scripts/stage10a_demo_fixture.py", "demo/stage10a_demo_fixture.py"),
    (DEMO_REPORT, "demo/stage10a_demo_report.json"),
]

MANIFEST = {
    "artifact": "stage10a_questionnaire_acceptance_bundle",
    "created_at": datetime.now(UTC).isoformat(),
    "questionnaire_version": q.QUESTIONNAIRE_VERSION,
    "entries": [archive for _, archive in ENTRIES],
    "secrets_excluded": [".env", ".env.example", "DASHSCOPE_API_KEY", "ES passwords"],
    "notes": "Questionnaire initializes existing User Memory only; Safety/Evidence/"
    "Output-Guard/Personal-RAG-weights are unchanged.",
}


def _write_artifacts() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    (ARTIFACT_DIR / "questionnaire_schema.json").write_text(
        json.dumps(q.questionnaire_schema(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    mapping = {
        "rest_preference": {
            value: list(instructions)
            for value, instructions in q._REST_PREFERENCE.items()
        },
        "annoying_reminders": {
            value: list(instructions)
            for value, instructions in q._ANNOYING_REMINDERS.items()
        },
        "main_context": {value: list(instructions) for value, instructions in q._MAIN_CONTEXT.items()},
        "leave_seat_allowed": {
            value: list(instructions) for value, instructions in q._LEAVE_SEAT.items()
        },
        "break_minutes": {
            value: list(instructions) for value, instructions in q._BREAK_MINUTES.items()
        },
    }
    (ARTIFACT_DIR / "memory_mapping.json").write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> None:
    _write_artifacts()
    missing = [path for path, _ in ENTRIES if not path.exists()]
    if missing:
        raise SystemExit(f"missing files: {missing}")
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path, archive in ENTRIES:
            bundle.write(path, archive)
        bundle.writestr(
            "manifest.json", json.dumps(MANIFEST, ensure_ascii=False, indent=2)
        )
    sha = hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest()
    sha_path = ROOT / "evaluation" / "stage10a_questionnaire_acceptance_bundle_sha256.txt"
    sha_path.write_text(f"{ZIP_PATH.name}\n{sha}\n", encoding="utf-8")
    print(f"zip: {ZIP_PATH}")
    print(f"sha256: {sha}")
    print(f"sha256 file: {sha_path}")


if __name__ == "__main__":
    main()
