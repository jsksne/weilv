def test_bootstrap_indexes_all_formal_tasks_idempotently_with_frozen_mapping(monkeypatch):
    from scripts import bootstrap_micro_tasks as bootstrap

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
            self.bulk_calls = []

        def bulk(self, **kwargs):
            self.bulk_calls.append(kwargs)
            return {"errors": False, "items": []}

    tasks = bootstrap.load_formal_micro_tasks(bootstrap.FORMAL_TASKS_PATH)
    texts = []
    monkeypatch.setattr(
        bootstrap,
        "embed_texts",
        lambda values, api_key, text_type: (
            texts.extend(values) or [[position / 100] * 1024 for position in range(len(values))]
        ),
    )
    client = Client()

    assert bootstrap.bootstrap_micro_tasks(client, "test-key") == 23
    assert bootstrap.bootstrap_micro_tasks(client, "test-key") == 23

    micro_mapping = next(
        call for call in client.indices.create_calls if call["index"] == "micro_tasks_v1"
    )
    assert micro_mapping["mappings"]["properties"]["embedding"]["dims"] == 1024
    first_operations = client.bulk_calls[0]["operations"]
    ids = [action["index"]["_id"] for action in first_operations[::2]]
    documents = first_operations[1::2]
    assert len(ids) == len(set(ids)) == 23
    assert ids == [task["task_id"] for task in tasks]
    assert {document["review_status"] for document in documents} == {"content_reviewed"}
    assert all(len(document["embedding"]) == 1024 for document in documents)
    assert {key: value for key, value in documents[0].items() if key != "embedding"} == tasks[0]
    assert texts[:23] == [bootstrap.embedding_text(task) for task in tasks]
    assert client.bulk_calls[0]["refresh"] == "wait_for"
    assert [action["index"]["_id"] for action in client.bulk_calls[1]["operations"][::2]] == ids


def test_bootstrap_micro_tasks_uses_serverless_create_bodies(monkeypatch):
    from scripts import bootstrap_micro_tasks as bootstrap

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

    monkeypatch.setenv("WEILV_ELASTICSEARCH_SERVERLESS", "1")
    monkeypatch.setattr(
        bootstrap,
        "embed_texts",
        lambda values, api_key, text_type: [[0.1] * 1024 for _ in values],
    )

    client = Client()
    assert bootstrap.bootstrap_micro_tasks(client, "test-key") == 23
    assert len(client.indices.create_calls) == 3
    assert all("settings" not in call for call in client.indices.create_calls)


def test_bootstrap_rejects_wrong_embedding_dimension(monkeypatch):
    from scripts import bootstrap_micro_tasks as bootstrap

    monkeypatch.setattr(
        bootstrap,
        "embed_texts",
        lambda values, api_key, text_type: [[0.1, 0.2] for _ in values],
    )

    class Client:
        class Indices:
            def exists(self, *, index):
                return True

        indices = Indices()

        def bulk(self, **kwargs):
            raise AssertionError("invalid vectors must not be indexed")

    try:
        bootstrap.bootstrap_micro_tasks(Client(), "test-key")
    except ValueError as error:
        assert "1024" in str(error)
    else:
        raise AssertionError("wrong embedding dimension was accepted")
