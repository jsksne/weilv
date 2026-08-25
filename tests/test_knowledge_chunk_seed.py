import hashlib
import json
import os
import re
from pathlib import Path

import pytest

CHUNK_PATH = Path("data/metadata/knowledge_chunks.poc.jsonl")
PROVENANCE_PATH = Path("data/metadata/SRC-001.provenance.v1.json")
SOURCE_DOCUMENTS_PATH = Path("data/metadata/source_documents.jsonl")
EXTERNAL_SOURCE_ENV = "WEILV_SOURCE_DOCUMENTS_DIR"
SKIP_REASON = "EXTERNAL_SOURCE_NOT_DISTRIBUTED"


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _content_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _line_range(source_locator: str) -> tuple[str, int, int]:
    match = re.fullmatch(r"(.+):L(\d+)-L(\d+)", source_locator)
    assert match
    source_path, start, end = match.groups()
    return source_path, int(start), int(end)


def _external_source_path(manifest: dict) -> Path:
    source_dir = os.environ.get(EXTERNAL_SOURCE_ENV)
    if not source_dir:
        pytest.skip(SKIP_REASON)

    source_path = Path(source_dir) / manifest["external_line_source"]["filename"]
    if not source_path.is_file():
        pytest.skip(SKIP_REASON)
    return source_path


def test_poc_knowledge_chunks_match_distributable_provenance_manifest():
    from weilv.retrieval_slice import load_chunks

    chunks = load_chunks(CHUNK_PATH)
    manifest = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))
    source_documents = _load_jsonl(SOURCE_DOCUMENTS_PATH)
    source_document = next(
        item for item in source_documents if item["document_id"] == manifest["document_id"]
    )

    assert manifest["schema_version"] == "1"
    assert manifest["provenance_scope"] == "poc_unreviewed"
    assert manifest["document_id"] == "SRC-001"
    assert manifest["source_metadata"] == {
        "title": source_document["title"],
        "source_org": source_document["source_org"],
        "source_url": source_document["source_url"],
        "published_at": source_document["published_at"],
        "retrieved_at": source_document["retrieved_at"],
        "document_type": source_document["document_type"],
        "raw_source_content_sha256": source_document["content_hash"],
        "raw_source_local_path": source_document["local_path"],
        "review_status": source_document["review_status"],
        "conversion_status": source_document["conversion_status"],
        "allowed_for_knowledge_index": source_document["allowed_for_knowledge_index"],
    }

    required = {
        "chunk_id",
        "document_id",
        "title",
        "section_path",
        "content",
        "domain",
        "target_stage",
        "applicability",
        "warnings",
        "source_locator",
        "source_url",
        "published_at",
        "review_status",
    }

    manifest_chunks = {item["chunk_id"]: item for item in manifest["chunks"]}
    assert len(chunks) == 5
    assert len({chunk["chunk_id"] for chunk in chunks}) == len(chunks)
    assert set(manifest_chunks) == {chunk["chunk_id"] for chunk in chunks}

    for chunk in chunks:
        assert set(chunk) == required
        assert chunk["document_id"] == "SRC-001"
        assert chunk["review_status"] == "poc_unreviewed"
        provenance = manifest_chunks[chunk["chunk_id"]]
        assert provenance == {
            "chunk_id": chunk["chunk_id"],
            "document_id": chunk["document_id"],
            "source_locator": chunk["source_locator"],
            "source_url": chunk["source_url"],
            "content_sha256": _content_sha256(chunk["content"]),
        }


def test_poc_knowledge_chunks_match_external_source_when_supplied():
    manifest = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))
    source_path = _external_source_path(manifest)

    assert hashlib.sha256(source_path.read_bytes()).hexdigest() == manifest["external_line_source"][
        "sha256"
    ]
    lines = source_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == manifest["external_line_source"]["line_count"]

    chunks = _load_jsonl(CHUNK_PATH)
    for chunk in chunks:
        locator_path, start, end = _line_range(chunk["source_locator"])
        assert Path(locator_path).name == source_path.name
        source_text = "\n".join(lines[start - 1 : end]).strip()
        assert chunk["content"] == source_text
