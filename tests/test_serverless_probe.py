def test_serverless_probe_uses_sanitized_create_body_and_deletes_its_index(monkeypatch):
    from scripts import probe_elasticsearch_serverless as probe

    class Indices:
        def __init__(self):
            self.create_calls = []
            self.deleted = []

        def create(self, **kwargs):
            self.create_calls.append(kwargs)

        def get_mapping(self, *, index):
            return {index: {"mappings": {"properties": {"embedding": {"type": "dense_vector"}}}}}

        def delete(self, *, index):
            self.deleted.append(index)

    class Client:
        def __init__(self):
            self.indices = Indices()
            self.index_calls = []
            self.get_calls = []
            self.closed = False

        def index(self, **kwargs):
            self.index_calls.append(kwargs)

        def get(self, **kwargs):
            self.get_calls.append(kwargs)
            return {"_source": {"chunk_id": "probe"}}

        def close(self):
            self.closed = True

    client = Client()
    monkeypatch.setenv("WEILV_ELASTICSEARCH_SERVERLESS", "1")
    monkeypatch.setattr(probe, "create_elasticsearch_client", lambda env_file: client)

    assert probe.main() == 0
    assert len(client.indices.create_calls) == 1
    assert "settings" not in client.indices.create_calls[0]
    assert client.indices.create_calls[0]["mappings"]["properties"]["embedding"]["type"] == "dense_vector"
    assert len(client.index_calls) == len(client.get_calls) == 1
    assert client.indices.deleted == [client.indices.create_calls[0]["index"]]
    assert client.closed is True
