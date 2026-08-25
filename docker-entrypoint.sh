#!/bin/sh
set -eu

python -m weilv.runtime_config

if [ "${WEILV_BOOTSTRAP_ON_START:-0}" = "1" ]; then
  python scripts/bootstrap_micro_tasks.py
  python scripts/bootstrap_health_knowledge.py
fi

exec uvicorn weilv.api.app:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers
