from pathlib import Path

import pytest

from weilv.retrieval_slice import create_elasticsearch_client
from weilv.runtime_config import runtime_environment_diagnostics


def test_elasticsearch_client_defaults_to_localhost_without_environment(monkeypatch):
    captured = {}

    def factory(url, **options):
        captured["url"] = url
        captured["options"] = options
        return object()

    for name in (
        "ELASTICSEARCH_URL",
        "ELASTICSEARCH_API_KEY",
        "ELASTICSEARCH_USERNAME",
        "ELASTICSEARCH_PASSWORD",
        "ELASTICSEARCH_VERIFY_CERTS",
    ):
        monkeypatch.delenv(name, raising=False)

    create_elasticsearch_client(Path("missing.env"), client_factory=factory)

    assert captured == {"url": "http://127.0.0.1:9200", "options": {"request_timeout": 30}}


def test_elasticsearch_client_uses_api_key_and_tls_settings(monkeypatch):
    captured = {}

    def factory(url, **options):
        captured["url"] = url
        captured["options"] = options
        return object()

    monkeypatch.setenv("ELASTICSEARCH_URL", "https://managed-es.example")
    monkeypatch.setenv("ELASTICSEARCH_API_KEY", "test-api-key")
    monkeypatch.setenv("ELASTICSEARCH_VERIFY_CERTS", "true")

    create_elasticsearch_client(Path("missing.env"), client_factory=factory)

    assert captured == {
        "url": "https://managed-es.example",
        "options": {"request_timeout": 30, "api_key": "test-api-key", "verify_certs": True},
    }


def test_elasticsearch_basic_auth_requires_password(monkeypatch):
    monkeypatch.setenv("ELASTICSEARCH_USERNAME", "elastic")
    monkeypatch.delenv("ELASTICSEARCH_PASSWORD", raising=False)

    with pytest.raises(RuntimeError, match="ELASTICSEARCH_PASSWORD"):
        create_elasticsearch_client(Path("missing.env"))


def test_elasticsearch_client_falls_back_to_basic_auth(monkeypatch):
    captured = {}

    def factory(url, **options):
        captured["url"] = url
        captured["options"] = options
        return object()

    monkeypatch.setenv("ELASTICSEARCH_URL", "https://cloud.example")
    monkeypatch.delenv("ELASTICSEARCH_API_KEY", raising=False)
    monkeypatch.setenv("ELASTICSEARCH_USERNAME", "elastic")
    monkeypatch.setenv("ELASTICSEARCH_PASSWORD", "test-password")

    create_elasticsearch_client(Path("missing.env"), client_factory=factory)

    assert captured == {
        "url": "https://cloud.example",
        "options": {"request_timeout": 30, "basic_auth": ("elastic", "test-password")},
    }


def test_runtime_environment_diagnostics_never_prints_secret_values():
    lines = runtime_environment_diagnostics(
        {
            "DASHSCOPE_API_KEY": "dashscope-secret",
            "ELASTICSEARCH_URL": "https://elastic-user:es-secret@cluster.example:9243/path?token=x",
            "ELASTICSEARCH_API_KEY": "elastic-api-secret",
            "WEILV_BOOTSTRAP_ON_START": "1",
        }
    )

    output = "\n".join(lines)
    assert lines == [
        "DASHSCOPE_API_KEY=PRESENT",
        "ELASTICSEARCH_URL=PRESENT",
        "ELASTICSEARCH_API_KEY=PRESENT",
        "WEILV_BOOTSTRAP_ON_START=PRESENT",
        "ELASTICSEARCH_URL_TARGET=https://cluster.example",
    ]
    assert "secret" not in output
    assert "elastic-user" not in output
