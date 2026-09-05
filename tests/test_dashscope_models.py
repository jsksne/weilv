from types import SimpleNamespace

import pytest


def test_embed_texts_uses_v4_1024_dense_vectors_and_restores_input_order(monkeypatch):
    from weilv import dashscope_models

    calls = []
    first = [0.1] * 1024
    second = [0.2] * 1024

    def fake_call(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            status_code=200,
            output=SimpleNamespace(
                embeddings=[
                    SimpleNamespace(index=1, embedding=second),
                    SimpleNamespace(index=0, embedding=first),
                ]
            ),
        )

    monkeypatch.setattr(dashscope_models.TextEmbedding, "call", fake_call)

    vectors = dashscope_models.embed_texts(
        ["久坐后怎么活动", "如何保持规律作息"],
        api_key="test-key",
        text_type="document",
    )

    assert vectors == [first, second]
    assert calls == [
        {
            "model": "text-embedding-v4",
            "input": ["久坐后怎么活动", "如何保持规律作息"],
            "api_key": "test-key",
            "text_type": "document",
            "dimension": 1024,
            "output_type": "dense",
        }
    ]


def test_embed_texts_accepts_the_mapping_shape_returned_by_the_live_sdk(monkeypatch):
    from weilv import dashscope_models

    first = [0.1] * 1024
    second = [0.2] * 1024
    monkeypatch.setattr(
        dashscope_models.TextEmbedding,
        "call",
        lambda **_: SimpleNamespace(
            status_code=200,
            output={
                "embeddings": [
                    {"text_index": 1, "embedding": second},
                    {"text_index": 0, "embedding": first},
                ]
            },
        ),
    )

    assert dashscope_models.embed_texts(
        ["第一段", "第二段"], api_key="test-key", text_type="document"
    ) == [first, second]


def test_embed_texts_rejects_a_vector_with_the_wrong_dimension(monkeypatch):
    from weilv import dashscope_models

    monkeypatch.setattr(
        dashscope_models.TextEmbedding,
        "call",
        lambda **_: SimpleNamespace(
            status_code=200,
            output=SimpleNamespace(embeddings=[SimpleNamespace(index=0, embedding=[0.1, 0.2])]),
        ),
    )

    with pytest.raises(dashscope_models.ModelAPIError, match="1024"):
        dashscope_models.embed_texts(["文本"], api_key="test-key", text_type="query")


def test_embed_texts_exposes_api_failure_without_silent_fallback(monkeypatch):
    from weilv import dashscope_models

    monkeypatch.setattr(
        dashscope_models.TextEmbedding,
        "call",
        lambda **_: SimpleNamespace(
            status_code=401,
            code="InvalidApiKey",
            message="API key is invalid",
        ),
    )

    with pytest.raises(dashscope_models.ModelAPIError, match="InvalidApiKey"):
        dashscope_models.embed_texts(["文本"], api_key="test-key", text_type="query")


def test_embed_texts_retries_a_transient_api_failure(monkeypatch):
    from weilv import dashscope_models

    responses = [
        SimpleNamespace(status_code=429, code="Throttling", message="try again"),
        SimpleNamespace(
            status_code=200,
            output={
                "embeddings": [{"text_index": 0, "embedding": [0.1] * 1024}]
            },
        ),
    ]
    calls = []

    def fake_call(**kwargs):
        calls.append(kwargs)
        return responses.pop(0)

    monkeypatch.setattr(dashscope_models.TextEmbedding, "call", fake_call)

    assert len(
        dashscope_models.embed_texts(["文本"], api_key="test-key", text_type="document")[0]
    ) == 1024
    assert len(calls) == 2


def test_rerank_texts_returns_original_candidate_indices_and_scores(monkeypatch):
    from weilv import dashscope_models

    calls = []

    def fake_call(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            status_code=200,
            output=SimpleNamespace(
                results=[
                    SimpleNamespace(index=1, relevance_score=0.91),
                    SimpleNamespace(index=0, relevance_score=0.25),
                ]
            ),
        )

    monkeypatch.setattr(dashscope_models.TextReRank, "call", fake_call)

    results = dashscope_models.rerank_texts(
        "久坐后怎么活动",
        ["睡眠内容", "久坐内容"],
        api_key="test-key",
    )

    assert results == [
        {"index": 1, "relevance_score": 0.91},
        {"index": 0, "relevance_score": 0.25},
    ]
    assert calls == [
        {
            "model": "qwen3-rerank",
            "query": "久坐后怎么活动",
            "documents": ["睡眠内容", "久坐内容"],
            "api_key": "test-key",
            "return_documents": False,
            "top_n": 2,
        }
    ]


def test_rerank_texts_exposes_api_failure_without_silent_fallback(monkeypatch):
    from weilv import dashscope_models

    monkeypatch.setattr(
        dashscope_models.TextReRank,
        "call",
        lambda **_: SimpleNamespace(
            status_code=429,
            code="Throttling",
            message="Too many requests",
        ),
    )

    with pytest.raises(dashscope_models.ModelAPIError, match="Throttling"):
        dashscope_models.rerank_texts("问题", ["候选"], api_key="test-key")


def test_generate_with_rag_context_passes_sources_and_forbids_health_task_generation(
    monkeypatch,
):
    from weilv import dashscope_models

    calls = []

    def fake_call(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            status_code=200,
            output={"choices": [{"message": {"content": "已接收来源 SRC-001。"}}]},
        )

    monkeypatch.setattr(dashscope_models.Generation, "call", fake_call)
    answer = dashscope_models.generate_with_rag_context(
        "这段资料讲了什么？",
        [
            {
                "document_id": "SRC-001",
                "source_locator": "source.md:L10-L12",
                "content": "学生每天应安排适量身体活动。",
            }
        ],
        api_key="test-key",
    )

    assert answer == "已接收来源 SRC-001。"
    assert calls[0]["model"] == "qwen-plus"
    assert calls[0]["result_format"] == "message"
    assert "不要生成健康建议、健康任务、诊断或个性化方案" in calls[0]["messages"][0][
        "content"
    ]
    assert "原样保留 document_id 和 source_locator" in calls[0]["messages"][0]["content"]
    assert "document_id=SRC-001" in calls[0]["messages"][1]["content"]
    assert "source_locator=source.md:L10-L12" in calls[0]["messages"][1]["content"]


def test_generate_with_rag_context_exposes_api_failure(monkeypatch):
    from weilv import dashscope_models

    monkeypatch.setattr(
        dashscope_models.Generation,
        "call",
        lambda **_: SimpleNamespace(
            status_code=500,
            code="InternalError",
            message="try later",
        ),
    )

    with pytest.raises(dashscope_models.ModelAPIError, match="InternalError"):
        dashscope_models.generate_with_rag_context(
            "问题",
            [{"document_id": "SRC-1", "source_locator": "a.md:L1", "content": "内容"}],
            api_key="test-key",
        )


def test_decompose_problem_without_history_keeps_single_user_turn(monkeypatch):
    from weilv import dashscope_models

    calls = []

    def fake_call(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            status_code=200,
            output=SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"factors":[]}'))]
            ),
        )

    monkeypatch.setattr(dashscope_models.Generation, "call", fake_call)

    dashscope_models.decompose_problem("现在眼睛很酸", api_key="test-key")

    roles = [message["role"] for message in calls[0]["messages"]]
    assert roles == ["system", "user"]
    assert calls[0]["messages"][1]["content"] == "现在眼睛很酸"


def test_decompose_problem_carries_session_history_before_current_query(monkeypatch):
    from weilv import dashscope_models

    calls = []

    def fake_call(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            status_code=200,
            output=SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"factors":[]}'))]
            ),
        )

    monkeypatch.setattr(dashscope_models.Generation, "call", fake_call)

    history = [
        {"role": "user", "content": "推荐一个课间能做的任务"},
        {"role": "assistant", "content": "已选择：窗边远眺 20 秒"},
    ]
    dashscope_models.decompose_problem("再简单一点", api_key="test-key", history=history)

    messages = calls[0]["messages"]
    assert [message["role"] for message in messages] == [
        "system",
        "system",
        "user",
        "assistant",
        "user",
    ]
    assert messages[2]["content"] == "推荐一个课间能做的任务"
    assert messages[3]["content"] == "已选择：窗边远眺 20 秒"
    assert messages[4]["content"] == "再简单一点"
    assert "不得据此放宽任何限制" in messages[1]["content"]
