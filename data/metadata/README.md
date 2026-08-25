# 来源元数据

`source_documents.jsonl` 是 `source_documents_v1` 的本地种子数据。每行对应一份真实原始资料。

当前共 8 份资料，均已下载、计算哈希并完成文本转换。其中 3 份标记为 `collected`，5 份标记为 `source_verified`；8 份资料均为：

```text
allowed_for_knowledge_index = false
```

`collected` 是设计中允许的第一步状态，只表示文件已经真实落盘。`source_verified` 只表示来源机构、官方入口和本地快照等来源信息已核验。两种状态都不表示其中每一段已经完成健康内容审核，也不表示资料可以直接成为健康知识或微任务。完成适用年龄、风险边界、版权和内容审核后，才能把审核过的 Chunk 写入 `health_knowledge_v1`。

`knowledge_chunks.poc.jsonl` 保存 5 条与 SRC-001 原文行号逐条匹配的技术 POC 样例，状态固定为 `poc_unreviewed`。默认检索脚本将它们写入独立的 `health_knowledge_poc_v1`；正式 `health_knowledge_v1` 只接受 `review_status=content_reviewed` 的 Chunk。

## 可分发 provenance 与外部原文核验

仓库不再分发第三方原始资料或转换后的完整原文。`SRC-001.provenance.v1.json` 保留 SRC-001 的来源元数据、官方 URL、文档 ID、原始定位符，以及每条 POC Chunk 的内容 SHA-256；它用于在干净 checkout 中校验已提交的派生 Chunk 未被静默修改。

完整原文逐行核验是可选的外部校验：将原文目录显式设置为 `WEILV_SOURCE_DOCUMENTS_DIR`，其中包含 `SRC-001-student-common-diseases-2024.md`，即可执行。未提供该外部资料时，测试会以 `EXTERNAL_SOURCE_NOT_DISTRIBUTED` 跳过；这不影响可分发 provenance 校验。来源元数据、可用边界和审核状态不构成对内容再利用权利的法律结论。
