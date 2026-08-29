import json
from io import StringIO

import pytest


class SliceClient:
    def __init__(self):
        self.bulk_calls = []
        self.search_calls = []

    def bulk(self, **kwargs):
        self.bulk_calls.append(kwargs)
        return {"errors": False, "items": []}

    def search(self, **kwargs):
        self.search_calls.append(kwargs)
        if len(self.search_calls) == 1:
            return {
                "hits": {
                    "hits": [
                        {"_score": 3.0, "_source": _chunk("a", "SRC-001", "久坐内容")},
                        {"_score": 2.0, "_source": _chunk("b", "SRC-005", "运动内容")},
                    ]
                }
            }
        return {
            "hits": {
                "hits": [
                    {"_score": 0.9, "_source": _chunk("b", "SRC-005", "运动内容")},
                    {"_score": 0.8, "_source": _chunk("a", "SRC-001", "久坐内容")},
                ]
            }
        }


def _chunk(chunk_id, document_id, content):
    return {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "title": "标题",
        "section_path": ["章节"],
        "content": content,
        "domain": "sedentary",
        "target_stage": "both",
        "applicability": "学习场景",
        "warnings": "技术POC样例",
        "source_locator": f"{document_id}.md:L1-L1",
        "source_url": "https://example.test/source",
        "published_at": "2024-01-01",
        "review_status": "poc_unreviewed",
    }


def test_load_chunks_reads_jsonl_records(tmp_path):
    from weilv.retrieval_slice import load_chunks

    path = tmp_path / "chunks.jsonl"
    records = [_chunk("a", "SRC-001", "久坐内容"), _chunk("b", "SRC-005", "运动内容")]
    path.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in records), encoding="utf-8"
    )

    assert load_chunks(path) == records


def test_load_api_key_fails_clearly_when_not_configured(tmp_path, monkeypatch):
    from weilv.retrieval_slice import load_api_key

    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="DASHSCOPE_API_KEY"):
        load_api_key(tmp_path / ".env")


def test_managed_elasticsearch_client_uses_documented_authentication(tmp_path, monkeypatch):
    from weilv.retrieval_slice import create_elasticsearch_client

    for name in (
        "ELASTICSEARCH_URL",
        "ELASTICSEARCH_API_KEY",
        "ELASTICSEARCH_USERNAME",
        "ELASTICSEARCH_PASSWORD",
        "ELASTICSEARCH_CA_CERTS",
        "ELASTICSEARCH_VERIFY_CERTS",
    ):
        monkeypatch.delenv(name, raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ELASTICSEARCH_URL=https://elastic.example.test:9243\n"
        "ELASTICSEARCH_API_KEY=test-api-key\n"
        "ELASTICSEARCH_CA_CERTS=/run/secrets/elastic-ca.pem\n"
        "ELASTICSEARCH_VERIFY_CERTS=true\n",
        encoding="utf-8",
    )

    class ClientFactory:
        def __init__(self, url, **options):
            self.url = url
            self.options = options

    client = create_elasticsearch_client(env_file, client_factory=ClientFactory)

    assert client.url == "https://elastic.example.test:9243"
    assert client.options == {
        "request_timeout": 30,
        "api_key": "test-api-key",
        "ca_certs": "/run/secrets/elastic-ca.pem",
        "verify_certs": True,
    }


def test_formal_index_rejects_chunks_without_content_review():
    from weilv.retrieval_slice import validate_index_target

    with pytest.raises(RuntimeError, match="content_reviewed"):
        validate_index_target(
            [_chunk("a", "SRC-001", "久坐内容")],
            index_name="health_knowledge_v1",
        )


def test_retrieval_cli_configures_utf8_stdout_before_loading_settings(monkeypatch):
    from weilv import retrieval_slice

    class Output(StringIO):
        requested_encoding = None

        def reconfigure(self, *, encoding):
            self.requested_encoding = encoding

    output = Output()
    monkeypatch.setattr("sys.stdout", output)
    monkeypatch.setattr("sys.argv", ["run_retrieval_slice", "问题"])
    monkeypatch.setattr(
        retrieval_slice,
        "load_api_key",
        lambda *_: (_ for _ in ()).throw(RuntimeError("DASHSCOPE_API_KEY is missing")),
    )

    with pytest.raises(RuntimeError, match="DASHSCOPE_API_KEY"):
        retrieval_slice.main()

    assert output.requested_encoding == "utf-8"


def test_run_slice_and_print_results_exposes_every_retrieval_stage(monkeypatch, capsys):
    from weilv import retrieval_slice as run_retrieval_slice

    chunks = [_chunk("a", "SRC-001", "久坐内容"), _chunk("b", "SRC-005", "运动内容")]
    client = SliceClient()
    embedding_calls = []

    def fake_embed(texts, api_key, text_type):
        embedding_calls.append((texts, api_key, text_type))
        value = 0.1 if text_type == "document" else 0.2
        return [[value] * 1024 for _ in texts]

    monkeypatch.setattr(run_retrieval_slice, "embed_texts", fake_embed)
    monkeypatch.setattr(
        run_retrieval_slice,
        "rerank_texts",
        lambda query, documents, api_key: [
            {"index": 1, "relevance_score": 0.95},
            {"index": 0, "relevance_score": 0.35},
        ],
    )

    result = run_retrieval_slice.run_slice(
        "久坐复习后怎么活动",
        chunks,
        client=client,
        api_key="test-key",
    )
    run_retrieval_slice.print_results(result)
    output = capsys.readouterr().out

    assert embedding_calls == [
        (["久坐内容", "运动内容"], "test-key", "document"),
        (["久坐复习后怎么活动"], "test-key", "query"),
    ]
    assert result["indexed_count"] == 2
    assert [item["chunk_id"] for item in result["merged"]] == ["a", "b"]
    assert [item["chunk_id"] for item in result["reranked"]] == ["b", "a"]
    assert len(client.bulk_calls[0]["operations"][1]["embedding"]) == 1024

    for heading in [
        "Query",
        "BM25 Top 10",
        "Vector Cosine kNN Top 10",
        "合并候选 / Reranker 前",
        "Reranker 后",
        "最终 Top 结果",
    ]:
        assert heading in output
    assert "document_id=SRC-001" in output
    assert "document_id=SRC-005" in output
    assert "source=SRC-001.md:L1-L1" in output
