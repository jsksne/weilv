"""Sandbox-adaptive test fixtures.

Overrides pytest's built-in ``tmp_path`` fixture: pytest's implementation
creates directories through extended (``\\\\?\\``) Windows paths, which the DSH
file sandbox denies in this environment.  This conftest provides an equivalent
temporary directory under ``.runtime/`` (gitignored, inside the writable
workspace) using plain paths.  Test semantics are unchanged; only the backing
directory differs.  Stage 9B files use the same mechanism via their own
``workdir`` fixture.
"""

import shutil
import uuid
from pathlib import Path

import pytest

_TMP_ROOT = Path(".runtime") / "stage9-test-tmp"


@pytest.fixture
def tmp_path(request):
    _TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = _TMP_ROOT / f"tmp-{uuid.uuid4().hex[:10]}"
    path.mkdir(parents=True, exist_ok=True)

    def _cleanup():
        shutil.rmtree(path, ignore_errors=True)

    request.addfinalizer(_cleanup)
    return path
