"""Safe runtime configuration diagnostics for managed deployment startup."""

import os
from collections.abc import Mapping
from urllib.parse import urlsplit

DIAGNOSTIC_ENV_NAMES = (
    "DASHSCOPE_API_KEY",
    "ELASTICSEARCH_URL",
    "ELASTICSEARCH_API_KEY",
    "WEILV_BOOTSTRAP_ON_START",
)


def runtime_environment_diagnostics(environ: Mapping[str, str] | None = None) -> list[str]:
    values = os.environ if environ is None else environ
    lines = [
        f"{name}={'PRESENT' if values.get(name) else 'MISSING'}"
        for name in DIAGNOSTIC_ENV_NAMES
    ]
    if url := values.get("ELASTICSEARCH_URL"):
        parsed = urlsplit(url)
        if parsed.scheme and parsed.hostname:
            lines.append(f"ELASTICSEARCH_URL_TARGET={parsed.scheme}://{parsed.hostname}")
        else:
            lines.append("ELASTICSEARCH_URL_TARGET=INVALID")
    return lines


def main() -> None:
    print("\n".join(runtime_environment_diagnostics()))


if __name__ == "__main__":
    main()
