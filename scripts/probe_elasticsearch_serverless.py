"""Verify Elastic Serverless index creation without bootstrapping production data."""

from datetime import UTC, datetime
from pathlib import Path

from weilv.elasticsearch_indices import (
    elasticsearch_serverless_enabled,
    get_index_definitions,
    index_create_kwargs,
)
from weilv.retrieval_slice import create_elasticsearch_client


def main() -> int:
    if not elasticsearch_serverless_enabled():
        print("SERVERLESS_PROBE=FAIL reason=WEILV_ELASTICSEARCH_SERVERLESS_not_enabled")
        return 1

    probe_index = f"weilv-serverless-probe-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
    client = create_elasticsearch_client(Path(".env"))
    created = False
    try:
        definition = get_index_definitions()["health_knowledge_v1"]
        client.indices.create(**index_create_kwargs(probe_index, definition))
        created = True
        mapping = client.indices.get_mapping(index=probe_index)
        properties = mapping[probe_index]["mappings"]["properties"]
        if properties.get("embedding", {}).get("type") != "dense_vector":
            print("SERVERLESS_PROBE=FAIL reason=mapping_validation_failed")
            return 1
        client.index(
            index=probe_index,
            id="probe",
            document={"chunk_id": "probe", "content": "serverless compatibility probe"},
            refresh="wait_for",
        )
        document = client.get(index=probe_index, id="probe")
        if document["_source"].get("chunk_id") != "probe":
            print("SERVERLESS_PROBE=FAIL reason=get_validation_failed")
            return 1
        print("SERVERLESS_PROBE=PASS create=PASS mapping=PASS index_get_delete=PASS")
        return 0
    except Exception as error:
        status = getattr(error, "status_code", "unknown")
        print(f"SERVERLESS_PROBE=FAIL type={type(error).__name__} status={status}")
        return 1
    finally:
        if created:
            try:
                client.indices.delete(index=probe_index)
            except Exception:
                print("SERVERLESS_PROBE_DELETE=FAIL")
        client.close()
