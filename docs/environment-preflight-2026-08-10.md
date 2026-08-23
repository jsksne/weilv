# 微律第一张 Ticket：环境预检与实装记录

**初次检查日期：** 2026-08-10  
**Stage 2 复核日期：** 2026-08-11  
**当前状态：** Python、MarkItDown、Elasticsearch、Embedding、Reranker 和 LLM 独立技术 POC 均已验证

## 本机检查结果

| 项目 | 实际结果 | 当前处理 |
|---|---|---|
| Git 仓库 | 当前目录尚未初始化 Git | 不阻塞 POC；正式持续开发前再确认仓库策略 |
| Python | 系统原有 Python 3.14.6 | 由 uv 单独安装并锁定 Python 3.12.13，不改系统 Python |
| uv | 0.12.0 | 已生成 `.venv` 和 `uv.lock` |
| Python 依赖 | 原先不存在项目依赖文件 | 已建立 `pyproject.toml`，FastAPI、ES 客户端、MarkItDown、DashScope 等均可导入 |
| Docker | 未安装 | 当前不用 Docker Desktop，减少额外环境负担 |
| Elasticsearch | 原先未安装 | 已使用 Elasticsearch 8.19.18 Windows ZIP 和内置 JDK 运行 |
| MarkItDown | 原先未安装 | 已安装 `markitdown[pdf]` 0.1.7，命令可运行 |
| 原始资料 | 原先没有 PDF 或网页快照 | 已保存 SRC-001、SRC-005、SRC-006，并记录官方 URL、SHA-256 和审核状态 |
| 阿里云密钥 | 已在本地 `.env` 配置并完成在线验证 | 密钥值不进入代码、测试输出或项目文档，仓库仅保留 `.env.example` |

## 已固定的环境方案

- Elasticsearch 服务端：8.19.18 Windows ZIP，使用内置 JDK。
- Python：3.12.13，由 uv 管理。
- Elasticsearch Python 客户端：8.19.3，由 `uv.lock` 固定。
- 原始资料目录：`data/raw/source_documents/`。
- 来源元数据索引：`source_documents_v1`。
- 知识 Chunk 索引：`health_knowledge_v1`。
- 审核微任务索引：`micro_tasks_v1`。
- 本机连接：`http://127.0.0.1:9200`，仅用于 POC。

## Windows 本机运行处理

项目路径含中文。Elasticsearch 8.19.18 启动时，其 Java entitlement agent 无法正确解析该路径，因此启动脚本会自动使用 Windows 短路径运行；不需要移动或重命名整个项目。

本项目当前不使用 Elasticsearch 的机器学习原生进程，且该进程在本机启动时会阻塞，因此 POC 启动参数设置：

```text
xpack.ml.enabled=false
```

本机磁盘剩余约 5.7GB，但使用率已超过 Elasticsearch 默认的 95% flood-stage 水位。生产保护规则会阻止新索引写入。为完成本机 POC，启动脚本临时关闭磁盘水位判断：

```text
cluster.routing.allocation.disk.threshold_enabled=false
```

这两个设置只服务本机 POC。正式部署时必须重新启用磁盘水位保护，并启用认证和 TLS。

## 已验证结果

- Elasticsearch 版本：8.19.18。
- 节点数量：1。
- 集群可达到 green 状态。
- Python 客户端连接成功。
- 已创建 `dense_vector` 1024 维、`cosine` 相似度的临时索引。
- 已写入测试向量并通过 kNN 命中，得分 1.0。
- 临时测试索引已删除，没有混入正式业务数据。
- 已保存两份国家疾控局资料和一份 WHO 指南原文。
- 三份资料已计算 SHA-256，并登记到 `data/metadata/source_documents.jsonl`。
- 三份资料均已通过 MarkItDown 转换；当前仍待人工审核，尚未写入正式知识索引。
- 已创建 `source_documents_v1`、`health_knowledge_v1`、`micro_tasks_v1` 三个正式 POC 索引。
- `source_documents_v1` 已写入 SRC-001、SRC-005、SRC-006 共 3 条来源元数据。
- `health_knowledge_v1` 和 `micro_tasks_v1` 均保持 0 条，未审核内容没有提前进入推荐数据。
- `text-embedding-v4` 在线调用成功并返回 1024 维向量；瞬时 429/5xx 失败支持最多 3 次明确重试。
- `qwen3-rerank` 在线调用成功，能返回原候选索引和相关性分数，失败路径不会静默伪装为正常重排。
- BM25 与 Vector Search 均已用真实 Elasticsearch 验证精确 Metadata filter。
- 3 组真实查询均完整展示 BM25、Vector、合并候选、Reranker 前后顺序、分数与来源定位。
- `qwen-plus` 独立在线调用成功，能够接收带 `document_id` 和 `source_locator` 的 RAG Context。
- LLM POC 系统约束明确禁止自由生成健康建议、健康任务、诊断或个性化方案，并要求原样保留来源字段。

## 启动与检查

在一个 PowerShell 窗口中前台运行：

```powershell
.\scripts\start-elasticsearch.ps1
```

不要关闭这个窗口。另开一个 PowerShell 窗口检查：

```powershell
Invoke-RestMethod http://127.0.0.1:9200
Invoke-RestMethod http://127.0.0.1:9200/_cluster/health
```

## 下一步

1. Stage 2 核心基础设施技术 POC 的出口条件已验证；不自动进入 Stage 3。
2. `data/metadata/knowledge_chunks.poc.jsonl` 的 5 条 SRC-001 样例仍是 `poc_unreviewed`，只能写入独立 POC 索引；人工内容审核后才能进入正式 `health_knowledge_v1`。
3. Stage 0 的需求验证、Stage 1 的知识内容审核与安全规则仍需按计划继续推进。
4. Stage 3 基础 RAG 必须由后续 Ticket 明确范围，并继续遵守输入风险分流、来源追溯和输出安全边界。
