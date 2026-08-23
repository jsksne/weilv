from pathlib import Path

import pytest


def _api_key_or_skip():
    from weilv.retrieval_slice import load_api_key

    try:
        return load_api_key(Path(".env"))
    except RuntimeError:
        pytest.skip("DASHSCOPE_API_KEY is not configured")


@pytest.mark.integration
@pytest.mark.live_model
def test_live_embedding_returns_1024_dimensions():
    from weilv.dashscope_models import embed_texts

    vectors = embed_texts(["久坐学习后适量活动。"], _api_key_or_skip(), "document")

    assert len(vectors) == 1
    assert len(vectors[0]) == 1024


@pytest.mark.integration
@pytest.mark.live_model
def test_live_reranker_returns_each_original_candidate_index():
    from weilv.dashscope_models import rerank_texts

    results = rerank_texts(
        "久坐学习后应该做什么？",
        ["保持规律睡眠。", "久坐后进行适量身体活动。"],
        _api_key_or_skip(),
    )

    assert sorted(item["index"] for item in results) == [0, 1]
    assert all(isinstance(item["relevance_score"], float) for item in results)


@pytest.mark.integration
@pytest.mark.live_model
def test_live_llm_accepts_sourced_context_without_generating_a_health_task():
    from weilv.dashscope_models import generate_with_rag_context

    answer = generate_with_rag_context(
        "请确认来源编号，并只复述资料中的事实。",
        [
            {
                "document_id": "SRC-LIVE",
                "source_locator": "live-test.md:L1-L1",
                "content": "这是一条用于技术验证的带来源测试资料。",
            }
        ],
        _api_key_or_skip(),
    )

    assert "SRC-LIVE" in answer
    assert "live-test.md:L1-L1" in answer
