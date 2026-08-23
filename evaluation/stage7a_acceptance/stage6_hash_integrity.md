# Stage 6 Hash Integrity

| Artifact | Frozen SHA-256 | Recomputed SHA-256 | Result |
|---|---|---|---|
| `evaluation/datasets/safety_gold_v1.jsonl` | `aa975d5cd58deec5c837b1ca2b5e4723229fd71c08c64df85ba39d8819372e7f` | `aa975d5cd58deec5c837b1ca2b5e4723229fd71c08c64df85ba39d8819372e7f` | UNCHANGED |
| canonical sorted `data/metadata/micro_tasks_v1.jsonl` | `40d53d96a89124f387d65dea3e97bbeb8da878ef1e9ccd2fbc971cd08096bb48` | `40d53d96a89124f387d65dea3e97bbeb8da878ef1e9ccd2fbc971cd08096bb48` | UNCHANGED |

The task-corpus value was recomputed with `evaluation/runners/_stage6g_verify_task_corpus.py`, using the frozen sorted canonical JSONL contract. No frozen Stage 6 evaluation run was rerun or overwritten.

