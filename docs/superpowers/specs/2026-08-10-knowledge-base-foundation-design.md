# 微律知识库基础阶段设计

**状态：** 已确认作为 Stage 1 设计基线；按 Agent 总规划进入最小纵向切片  
**日期：** 2026-08-10  
**范围：** Stage 1 完成权威资料、数据规范、审核微任务和安全边界；只允许下一张 Ticket 所需的 Stage 2 最小技术验证
**总规划：** [`../../agent/WEILV_AGENT_PLAN.md`](../../agent/WEILV_AGENT_PLAN.md)

## 1. 目标

建立一套可追溯、可审核、可向量化的青少年健康知识基础，为后续BM25、向量检索、`qwen3-rerank`、Personal RAG和LangGraph编排提供统一输入。

第一版核心对象是初中生和高中生，内容覆盖：久坐、用眼、户外活动、运动、睡眠、学习间歇和轻量恢复。

## 2. 已确认的前提

- Web优先，前端采用Vue + Element。
- 后端采用Python + FastAPI，不使用Spring Boot作为主后端。
- LangGraph负责后续Agentic RAG编排。
- Elasticsearch同时承担业务数据、公共知识、微任务、User Memory、BM25和向量检索。
- Embedding采用阿里云 `text-embedding-v4`，第一版使用1024维。
- 纯文本重排序采用阿里云 `qwen3-rerank`。
- 每个查询召回BM25 Top 10和Vector Top 10，合并去重后送入Reranker。
- 公共健康知识库、审核微任务库和用户记忆库严格分开。
- 竞赛POC允许只使用Elasticsearch；出现复杂事务或生产级并发后再评估关系数据库。

## 3. 方案比较

### 方案A：知识库优先，逐步打通链路（采用）

先完成真实资料、清洗、Metadata和审核，再实现最小检索链路，最后接入页面和Agentic RAG。

优点：符合老师意见；每一步都可验证；安全和来源问题能在模型生成前解决。缺点：早期可见页面较少。

### 方案B：前后端与知识库同时全面开发（不采用）

优点：较早看到完整界面。缺点：知识结构尚未稳定时会反复修改接口和页面，且容易把普通LLM调用误当成RAG成果。

### 方案C：直接使用云厂商托管知识库（不采用）

优点：搭建快。缺点：难以完整展示ES双路检索、候选合并、独立Reranker和用户记忆，不利于竞赛技术说明。

## 4. 第一阶段交付边界

### 本阶段完成

1. 权威来源准入规则；
2. 首批官方资料清单；
3. 原始文档、知识Chunk和微任务的数据结构；
4. 文档清洗、审核、切片和向量化流程；
5. 安全规则与人工审核责任；
6. 后续实现所需的验收标准。

### 本阶段不完成

- Vue页面；
- 登录和权限系统；
- 完整LangGraph工作流；
- 协同过滤；
- 真实未成年人健康效果研究；
- 医疗诊断、药物建议或疾病预测。

## 5. 来源准入规则

来源按以下顺序选择：

1. 国家卫生健康委、教育部、国家疾控局、中国疾控中心等政府或国家级专业机构；
2. WHO等国际公共卫生机构；
3. 确有缺口时才考虑学会指南或同行评审研究，并单独标注证据等级；
4. 自媒体、营销公众号、问答社区和短视频不能作为健康事实来源。

每份资料必须保存机构、标题、发布时间、原文链接、获取日期、原文定位信息和审核状态。过期资料只用于历史对照，不能覆盖更新版本。

## 6. 数据对象

### 6.1 原始资料 `source_document`

存储位置固定为：

```text
本地原始文件：data/raw/source_documents/
ES元数据索引：source_documents_v1
```

原始PDF和网页快照保存在本地目录；Elasticsearch只保存来源、版本、获取日期、哈希、审核状态和本地相对路径，不保存原始文件二进制内容。

必需字段：

```text
document_id
title
source_org
source_url
published_at
retrieved_at
document_type
domains
target_stage
license_note
content_hash
local_path
review_status
```

`review_status` 只允许：`collected`、`source_verified`、`content_reviewed`、`rejected`。

### 6.2 公共知识Chunk `knowledge_chunk`

必需字段：

```text
chunk_id
document_id
title
section_path
content
domain
target_stage
applicability
warnings
source_locator
source_url
published_at
review_status
embedding_model
embedding_dim
embedding
```

`domain` 只允许：`sedentary`、`eye_health`、`outdoor`、`physical_activity`、`sleep`、`study_break`、`light_recovery`。

`target_stage` 只允许：`junior_high`、`senior_high`、`both`。

### 6.3 审核微任务 `micro_task`

必需字段：

```text
task_id
name
instruction
domain
duration_minutes
intensity
scenarios
exam_week_fit
allow_conditions
stop_conditions
source_chunk_ids
review_status
```

LLM不能创建可直接推荐的新任务。任务可以由AI辅助起草，但只有 `review_status=approved` 的任务能够进入推荐候选。

## 7. 资料处理流程

```text
发现官方资料
    ↓
核验机构、版本和链接
    ↓
保存原始文件或网页快照
    ↓
计算SHA-256并将来源元数据写入source_documents_v1
    ↓
使用MarkItDown转为Markdown
    ↓
去除导航、重复页眉和无关附件
    ↓
按原文标题和语义段落切片
    ↓
补充Metadata与来源定位
    ↓
人工检查事实、适龄性和安全边界
    ↓
text-embedding-v4生成1024维向量
    ↓
写入health_knowledge_v1
```

切片优先沿用原文章节。单个Chunk以约400～900个中文字符为起始范围；不为了凑长度拆开一条完整的建议、条件或警示。超长章节再按语义段落拆分，并保留不超过100字的上下文重叠。

## 8. 检索边界

第一版检索流程固定为：

```text
用户问题或子问题
    ├─ BM25 Top 10
    └─ Vector Top 10
          ↓
       按chunk_id去重
          ↓
       qwen3-rerank
          ↓
       安全与适用性过滤
          ↓
       构建带来源的RAG上下文
```

候选集合最多20条，暂不增加独立向量数据库、复杂检索代理或模型横评平台。

## 9. 安全与真实数据

- 健康事实必须来自真实权威资料，不能由AI凭空生成。
- 演示画像可以使用合成数据，但必须明确标注，不能冒充真实调查结果。
- 真实评估优先采集匿名问卷和最少量交互反馈，不采集姓名、学校、班级、联系方式、精确地址、医疗诊断和用药信息。
- 如由高校对初高中生开展健康或行为研究，先确认伦理审查要求；取得监护人书面知情同意，并在学生能够理解的范围内说明和征得其同意。
- 输入出现明显疼痛、严重不适、急性风险或求医需求时，停止普通任务推荐并进入求助提示。

### 9.1 公开调查数据边界

- CEPS、YRBSS、WHO GSHS、PISA 可用于研究真实群体分布、设计画像字段和构造合成用户。
- 公开调查样本不是微律真实用户，不得直接写入 `user_memory_v1`。
- Personal RAG 和协同过滤 POC 使用的合成用户、合成交互必须标记 `synthetic = true`。
- 协同过滤需要 `User × MicroTask × Feedback`，普通公开调查问卷不能替代这种产品交互数据。
- 当前技术 POC 不采集真实未成年人产品使用行为；Stage 0 需求问卷只有在伦理、监护人同意和发放责任明确后才可开展。

## 10. 异常处理

- 来源机构或版本无法确认：标记 `rejected`，不进入索引。
- 网页内容与附件冲突：以正式附件为准，并记录冲突。
- Chunk缺少原文定位：不得标记为 `content_reviewed`。
- Embedding或写入失败：保留已审核文本，记录失败原因，允许幂等重试。
- Reranker不可用：测试环境可以返回未重排候选并明确标记降级；正式演示不得静默降级。
- 安全规则无法判断：不推荐任务，转为保守提示。

## 11. 验收标准

第一阶段完成需同时满足：

1. 首批至少6份官方资料通过来源核验；
2. 七个健康领域均有明确的数据字段和来源扩展计划；
3. 任意Chunk都能追溯到原始文档和具体章节；
4. 公共知识、微任务和用户记忆不存在混存设计；
5. 模型名称、向量维度、索引名称和目标人群在项目文档中一致；
6. 不存在Spring Boot或多模态Reranker作为当前方案的残留描述；
7. 数据伦理和真实数据使用边界写入问卷与技术文档。
8. 公开调查数据、合成用户、真实微律交互三类数据的用途与标记规则明确。

## 12. 下一阶段

下一步严格执行 Agent 总规划中的推荐 Ticket：先完成资料落盘、MarkItDown转换、结构校验、首批Chunk样例、ES索引和最小BM25/Vector/Reranker检索测试；通过后再扩展到30～60份权威资料。暂不实现完整Vue、Personal RAG、LangGraph、协同过滤或真实未成年人产品行为采集。
