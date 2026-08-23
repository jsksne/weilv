# Stage 1/2 最小检索纵向切片实施计划

> **执行状态（2026-08-11）：** 本计划已完成；随后补齐并验证了 Stage 2 的 Embedding 重试、Metadata filter 和 LLM 独立调用。本文件保留原始计划清单作为历史记录。

> **执行方式：** 当前会话内联执行，逐项遵循测试先行。当前目录不是 Git 仓库，不执行提交步骤。

**目标：** 用少量可追溯的知识 Chunk 打通 `text-embedding-v4`、Elasticsearch BM25/向量检索和 `qwen3-rerank`，完整展示重排前后结果。

**架构：** Markdown 切片、DashScope 模型边界、Elasticsearch 检索和命令行展示分别保持为小模块。正式索引只接收显式提供的 Chunk 记录；自动切片结果是待审核候选，不自动变成健康推荐知识。

**技术栈：** Python 3.12、DashScope Python SDK、Elasticsearch 8.19、pytest、uv。

## 全局约束

- Embedding 模型固定为 `text-embedding-v4`，维度固定为 1024。
- BM25 和 Vector 均请求 Top 10；向量相似度固定为 cosine。
- Reranker 固定为 `qwen3-rerank`，失败必须显式报错。
- 不实现 Vue、FastAPI 业务接口、Personal RAG、LangGraph 或协同过滤。
- 不把本次结果描述为 Stage 2 完成；LLM 独立调用测试不在本次范围。
- 不把自动切片候选描述为已完成人工内容审核。

---

### Task 1：Markdown Chunk 候选生成

**文件：**
- 新建：`src/weilv/markdown_chunks.py`
- 新建：`tests/test_markdown_chunks.py`

**接口：**
- `chunk_markdown(markdown: str, source_path: str, min_chars: int = 400, max_chars: int = 900) -> list[dict]`
- 每个结果包含 `section_path`、`content`、`source_locator`。

- [ ] 先写测试：标题层级会进入 `section_path`，段落合并不会拆开单个完整段落，定位包含原 Markdown 行号。
- [ ] 运行 `uv run pytest tests/test_markdown_chunks.py -q`，确认因模块不存在而失败。
- [ ] 用标准库实现最小 Markdown 标题/段落切分。
- [ ] 重跑测试，确认通过。

### Task 2：DashScope Embedding 与 Reranker 边界

**文件：**
- 新建：`src/weilv/dashscope_models.py`
- 新建：`tests/test_dashscope_models.py`

**接口：**
- `embed_texts(texts: list[str], api_key: str, text_type: str) -> list[list[float]]`
- `rerank_texts(query: str, documents: list[str], api_key: str) -> list[dict]`
- `ModelAPIError` 统一表示非 200、缺失结果和错误向量维度。

- [ ] 先写测试：请求参数固定模型/维度；返回按原输入索引排列；1024 维被验证；Reranker 返回原候选索引和分数；失败不静默降级。
- [ ] 运行 `uv run pytest tests/test_dashscope_models.py -q`，确认因模块不存在而失败。
- [ ] 使用已安装 DashScope SDK 实现最小包装器。
- [ ] 重跑测试，确认通过。

### Task 3：Elasticsearch 入库与双路检索

**文件：**
- 修改：`src/weilv/elasticsearch_indices.py`
- 新建：`src/weilv/retrieval.py`
- 修改：`tests/test_elasticsearch_indices.py`
- 新建：`tests/test_retrieval.py`

**接口：**
- `index_chunks(client, chunks: list[dict], index_name: str) -> int`
- `bm25_search(client, query: str, index_name: str, size: int = 10) -> list[dict]`
- `vector_search(client, query_vector: list[float], index_name: str, size: int = 10) -> list[dict]`
- `merge_candidates(bm25: list[dict], vector: list[dict]) -> list[dict]`
- `apply_rerank(candidates: list[dict], rerank_results: list[dict]) -> list[dict]`

- [ ] 先写测试：Mapping 保持 1024/cosine 和全部追溯字段；批量入库使用 `chunk_id` 幂等覆盖及 `refresh=wait_for`；两路搜索均请求 10；合并按 `chunk_id` 去重并保留两路分数；重排按 API 索引重建顺序。
- [ ] 运行相关测试，确认新接口缺失导致预期失败。
- [ ] 实现最小 Elasticsearch 调用和纯函数合并/重排。
- [ ] 重跑测试，确认通过。

### Task 4：可观察命令行纵向切片

**文件：**
- 新建：`scripts/run_retrieval_slice.py`
- 新建：`tests/test_retrieval_slice.py`
- 修改：`.env.example`

**接口：**
- `uv run python scripts/run_retrieval_slice.py "健康问题" --chunks <jsonl>`
- 顺序输出 Query、BM25、Vector、合并候选、Reranker 前后、最终 Top 结果和 `document_id`。

- [ ] 先写测试：使用假的 ES/模型边界运行脚本主流程，输出所有阶段且来源字段存在；缺密钥时明确失败。
- [ ] 运行脚本测试，确认入口尚不存在而失败。
- [ ] 实现 JSONL 读取、环境加载、批量向量化、入库、检索、重排和文本展示。
- [ ] 重跑脚本测试，确认通过。

### Task 5：真实服务验证

**文件：**
- 修改：`tests/integration/test_elasticsearch_indices_integration.py`
- 新建：`tests/integration/test_retrieval_integration.py`

- [ ] 启动 Elasticsearch 8.19.18 并运行全部单元测试、Ruff 和 ES 集成测试。
- [ ] 若 `DASHSCOPE_API_KEY` 已配置，运行真实 Embedding/Reranker 纵向切片并保存终端证据。
- [ ] 若密钥未配置，只报告模型实测未执行，不伪造通过，也不宣布最小纵向切片已完整验证。
- [ ] 最终报告修改文件、运行方式、测试结果，以及 Stage 2 仍缺 LLM 独立调用测试等项目。
