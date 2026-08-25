import json


def test_bootstrap_health_knowledge_uses_serverless_create_bodies(monkeypatch, tmp_path):
    from scripts import bootstrap_health_knowledge as bootstrap

    knowledge_path = tmp_path / "health_knowledge_v1.jsonl"
    knowledge_path.write_text(
        json.dumps({"chunk_id": "chunk-1", "content": "reviewed knowledge"}) + "\n",
        encoding="utf-8",
    )

    class Indices:
        def __init__(self):
            self.names = set()
            self.create_calls = []

        def exists(self, *, index):
            return index in self.names

        def create(self, **kwargs):
            self.names.add(kwargs["index"])
            self.create_calls.append(kwargs)

    class Client:
        def __init__(self):
            self.indices = Indices()

        def bulk(self, **kwargs):
            return {"errors": False, "items": []}

    monkeypatch.setenv("WEILV_ELASTICSEARCH_SERVERLESS", "true")
    monkeypatch.setattr(bootstrap, "KNOWLEDGE_PATH", knowledge_path)
    monkeypatch.setattr(
        bootstrap,
        "embed_texts",
        lambda values, api_key, text_type: [[0.1] * 1024 for _ in values],
    )

    client = Client()
    assert bootstrap.bootstrap_health_knowledge(client, "test-key") == 1
    assert len(client.indices.create_calls) == 3
    assert all("settings" not in call for call in client.indices.create_calls)
