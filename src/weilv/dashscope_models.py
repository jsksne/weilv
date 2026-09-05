"""Small, explicit boundaries around the two DashScope models in this POC."""

from collections.abc import Mapping
from http import HTTPStatus

from dashscope import Generation, TextEmbedding, TextReRank

EMBEDDING_MODEL = "text-embedding-v4"
EMBEDDING_DIMENSION = 1024
RERANK_MODEL = "qwen3-rerank"
LLM_MODEL = "qwen-plus"
MAX_MODEL_ATTEMPTS = 3


class ModelAPIError(RuntimeError):
    """A model request failed or returned an invalid payload."""


def _field(value, *names):
    for name in names:
        if isinstance(value, Mapping) and name in value:
            return value[name]
        if hasattr(value, name):
            return getattr(value, name)
    raise ModelAPIError(f"DashScope response is missing field: {'/'.join(names)}")


def _check_response(model_name: str, response) -> None:
    if response.status_code == HTTPStatus.OK:
        return
    code = getattr(response, "code", "unknown")
    message = getattr(response, "message", "no message")
    raise ModelAPIError(
        f"{model_name} API failed: status={response.status_code}, code={code}, message={message}"
    )


def embed_texts(texts: list[str], api_key: str, text_type: str) -> list[list[float]]:
    for attempt in range(MAX_MODEL_ATTEMPTS):
        response = TextEmbedding.call(
            model=EMBEDDING_MODEL,
            input=texts,
            api_key=api_key,
            text_type=text_type,
            dimension=EMBEDDING_DIMENSION,
            output_type="dense",
        )
        if response.status_code == HTTPStatus.OK:
            break
        if response.status_code != HTTPStatus.TOO_MANY_REQUESTS and response.status_code < 500:
            break
        if attempt == MAX_MODEL_ATTEMPTS - 1:
            break
    _check_response(EMBEDDING_MODEL, response)

    embeddings = sorted(
        _field(response.output, "embeddings"),
        key=lambda item: _field(item, "index", "text_index"),
    )
    if [_field(item, "index", "text_index") for item in embeddings] != list(
        range(len(texts))
    ):
        raise ModelAPIError(f"{EMBEDDING_MODEL} returned incomplete embedding indices")

    vectors = [_field(item, "embedding") for item in embeddings]
    for vector in vectors:
        if len(vector) != EMBEDDING_DIMENSION:
            raise ModelAPIError(
                f"{EMBEDDING_MODEL} returned {len(vector)} dimensions; expected {EMBEDDING_DIMENSION}"
            )
    return vectors


def rerank_texts(query: str, documents: list[str], api_key: str) -> list[dict]:
    response = TextReRank.call(
        model=RERANK_MODEL,
        query=query,
        documents=documents,
        api_key=api_key,
        return_documents=False,
        top_n=len(documents),
    )
    _check_response(RERANK_MODEL, response)
    return [
        {"index": result.index, "relevance_score": result.relevance_score}
        for result in response.output.results
    ]


def generate_with_rag_context(query: str, contexts: list[dict], api_key: str) -> str:
    context_text = "\n\n".join(
        (
            f"[来源 {position}] document_id={context['document_id']} "
            f"source_locator={context['source_locator']}\n{context['content']}"
        )
        for position, context in enumerate(contexts, start=1)
    )
    messages = [
        {
            "role": "system",
            "content": (
                "你正在执行 Stage 2 技术 POC。只复述提供的 Context 并说明来源；"
                "不要生成健康建议、健康任务、诊断或个性化方案。Context 不足时明确说明不足。"
                "引用来源时必须原样保留 document_id 和 source_locator。"
            ),
        },
        {
            "role": "user",
            "content": f"问题：{query}\n\n带来源 RAG Context：\n{context_text}",
        },
    ]
    response = Generation.call(
        model=LLM_MODEL,
        messages=messages,
        api_key=api_key,
        result_format="message",
    )
    _check_response(LLM_MODEL, response)
    choices = _field(response.output, "choices")
    if not choices:
        raise ModelAPIError(f"{LLM_MODEL} returned no choices")
    content = _field(_field(choices[0], "message"), "content")
    if not isinstance(content, str) or not content.strip():
        raise ModelAPIError(f"{LLM_MODEL} returned empty content")
    return content


def explain_selected_task(
    query: str,
    selected_task: dict,
    knowledge: list[dict],
    api_key: str,
) -> str:
    context_text = "\n\n".join(
        f"[知识 {position}] {item['content']}"
        for position, item in enumerate(knowledge, start=1)
    )
    messages = [
        {
            "role": "system",
            "content": (
                "程序已经从人工审核白名单中选定微任务。你只需用简短中文解释它为什么适合"
                "当前情况；不得诊断，不得新增任务或健康建议，不得修改任务指令、时长或来源，"
                "不得添加知识 Context 中没有的健康结论。只输出解释文本。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"用户情况：{query}\n\n"
                f"已选任务：{selected_task['title']}\n"
                f"任务指令：{selected_task['instruction']}\n"
                f"任务时长：{selected_task['estimated_minutes']}分钟\n\n"
                f"知识 Context：\n{context_text}"
            ),
        },
    ]
    response = Generation.call(
        model=LLM_MODEL,
        messages=messages,
        api_key=api_key,
        result_format="message",
    )
    _check_response(LLM_MODEL, response)
    choices = _field(response.output, "choices")
    if not choices:
        raise ModelAPIError(f"{LLM_MODEL} returned no choices")
    content = _field(_field(choices[0], "message"), "content")
    if not isinstance(content, str) or not content.strip():
        raise ModelAPIError(f"{LLM_MODEL} returned empty content")
    return content.strip()


def decompose_problem(query: str, api_key: str, history: list[dict[str, str]] | None = None) -> str:
    messages = [
        {
            "role": "system",
            "content": (
                "把用户明确表达的当前情况拆成最多4个有序因素，只输出JSON。不得推断疾病、"
                "新增症状、推荐行动、输出任务ID、诊断治疗或新增时间/数量。domain_hint只能是"
                "sedentary、eye_health、outdoor、physical_activity、sleep、study_break、"
                "light_recovery或null。格式："
                '{"is_complex":true,"factors":[{"factor_id":"F1","domain_hint":null,'
                '"subquery":"...","evidence_need":"..."}]}'
            ),
        },
    ]
    if history:
        messages.append(
            {
                "role": "system",
                "content": (
                    "以下是同一会话中更早的轮次，仅用于理解本次请求中的指代与追问"
                    "（如“再简单一点”“刚才那个”）；不得把历史内容当作新的健康陈述，"
                    "也不得据此放宽任何限制。"
                ),
            }
        )
        messages.extend({"role": turn["role"], "content": turn["content"]} for turn in history)
    messages.append({"role": "user", "content": query})
    response = Generation.call(
        model=LLM_MODEL,
        messages=messages,
        api_key=api_key,
        result_format="message",
    )
    _check_response(LLM_MODEL, response)
    choices = _field(response.output, "choices")
    if not choices:
        raise ModelAPIError(f"{LLM_MODEL} returned no choices")
    content = _field(_field(choices[0], "message"), "content")
    if not isinstance(content, str) or not content.strip():
        raise ModelAPIError(f"{LLM_MODEL} returned empty content")
    return content.strip()


def compose_agentic_explanation(
    query: str,
    factors: list[dict],
    selected_task: dict,
    task_evidence: list[dict],
    knowledge_contexts: list[dict],
    personalization: dict | None,
    api_key: str,
) -> str:
    factor_text = "\n".join(
        f"- {factor['factor_id']}: {factor['subquery']}" for factor in factors
    )
    evidence_text = "\n\n".join(item["content"] for item in task_evidence)
    knowledge_text = "\n\n".join(item["content"] for item in knowledge_contexts)
    personalization_text = (
        f"用户明确偏好影响了排序：{','.join(personalization['reason_codes'])}"
        if personalization
        else "无个性化排序影响"
    )
    messages = [
        {
            "role": "system",
            "content": (
                "程序已从人工审核白名单中选定唯一微任务。只解释考虑了哪些明确因素、为什么"
                "这个已选任务适合当前情况及证据如何支持；个性化仅在确实影响排序时提及。"
                "输出约束：1) 不得复述用户问题或因素中的数字或单位（如分钟、小时、厘米、米、"
                "次、天、个），除非该数字与单位原样出现在已选任务指令或任务证据中；即使总结"
                "因素内容也必须遵守，例如用户说“只有5分钟”时，解释中不得出现“5分钟”，应写为"
                "“可用时间较短”；2) 时间类限制一律改用定性表述，例如“只有几分钟”应改写为"
                "“当前可用时间较短”；3) 不得发明任何新数字或新单位；4) 不得提出第二个任务、"
                "健康处方、诊断治疗，不得修改或违背任务指令；5) 输出不超过120字的中文解释，"
                "留出安全余量。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"用户情况：{query}\n\n明确因素：\n{factor_text}\n\n"
                f"已选任务：{selected_task['title']}\n任务指令：{selected_task['instruction']}\n\n"
                f"精确任务证据：\n{evidence_text}\n\n相关检索知识：\n{knowledge_text}\n\n"
                f"个性化：{personalization_text}\n\n"
                "注意：用户问题与因素中的数字或单位仅用于理解，不得在解释中复述，"
                "除非该数字与单位原样出现在已选任务指令或任务证据中；总结因素时"
                "同样不得出现其中的数字或单位。"
            ),
        },
    ]
    response = Generation.call(
        model=LLM_MODEL,
        messages=messages,
        api_key=api_key,
        result_format="message",
    )
    _check_response(LLM_MODEL, response)
    choices = _field(response.output, "choices")
    if not choices:
        raise ModelAPIError(f"{LLM_MODEL} returned no choices")
    content = _field(_field(choices[0], "message"), "content")
    if not isinstance(content, str) or not content.strip():
        raise ModelAPIError(f"{LLM_MODEL} returned empty content")
    return content.strip()
