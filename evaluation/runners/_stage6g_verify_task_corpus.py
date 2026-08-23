"""Verify task corpus SHA under the documented hash contract:

  "SHA-256 over UTF-8 canonical JSON; corpus is task_id-sorted canonical JSONL with final LF"
"""
import hashlib
import json
from pathlib import Path

p = Path("data/metadata/micro_tasks_v1.jsonl")
rows = []
for line in p.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line:
        continue
    rows.append(json.loads(line))

# Sort by task_id; canonical JSON (sorted keys, separators=(',',':')), one per line, final LF.
rows.sort(key=lambda r: r["task_id"])
buf = "\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for r in rows) + "\n"
sha = hashlib.sha256(buf.encode("utf-8")).hexdigest()
print("recomputed sha:", sha)
print("expected:        40d53d96a89124f387d65dea3e97bbeb8da878ef1e9ccd2fbc971cd08096bb48")
print("match:", sha == "40d53d96a89124f387d65dea3e97bbeb8da878ef1e9ccd2fbc971cd08096bb48")