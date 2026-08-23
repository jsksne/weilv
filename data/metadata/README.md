# 来源元数据

`source_documents.jsonl` 是 `source_documents_v1` 的本地种子数据。每行对应一份真实原始资料。

当前共 8 份资料，均已下载、计算哈希并完成文本转换。其中 3 份标记为 `collected`，5 份标记为 `source_verified`；8 份资料均为：

```text
allowed_for_knowledge_index = false
```

`collected` 是设计中允许的第一步状态，只表示文件已经真实落盘。`source_verified` 只表示来源机构、官方入口和本地快照等来源信息已核验。两种状态都不表示其中每一段已经完成健康内容审核，也不表示资料可以直接成为健康知识或微任务。完成适用年龄、风险边界、版权和内容审核后，才能把审核过的 Chunk 写入 `health_knowledge_v1`。

`knowledge_chunks.poc.jsonl` 保存 5 条与 SRC-001 原文行号逐条匹配的技术 POC 样例，状态固定为 `poc_unreviewed`。默认检索脚本将它们写入独立的 `health_knowledge_poc_v1`；正式 `health_knowledge_v1` 只接受 `review_status=content_reviewed` 的 Chunk。
