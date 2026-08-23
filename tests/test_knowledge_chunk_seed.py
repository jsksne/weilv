import re
from pathlib import Path


def test_poc_knowledge_chunks_are_complete_and_match_their_source_lines():
    from weilv.retrieval_slice import load_chunks

    chunks = load_chunks(Path("data/metadata/knowledge_chunks.poc.jsonl"))
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

    assert len(chunks) == 5
    assert len({chunk["chunk_id"] for chunk in chunks}) == len(chunks)

    for chunk in chunks:
        assert set(chunk) == required
        assert chunk["document_id"] == "SRC-001"
        assert chunk["review_status"] == "poc_unreviewed"

        match = re.fullmatch(r"(.+):L(\d+)-L(\d+)", chunk["source_locator"])
        assert match
        source_path, start, end = match.groups()
        lines = Path(source_path).read_text(encoding="utf-8").splitlines()
        source_text = "\n".join(lines[int(start) - 1 : int(end)]).strip()
        assert chunk["content"] == source_text
