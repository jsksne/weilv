# 本地 Production Smoke — 可复现启动手册

本文记录在 Windows 本机启动最小 Production 环境并跑通真实 E2E 的步骤。
所有命令不含 secret；`.env` 不在 git 中，DASHSCOPE_API_KEY 由本机 `.env` 提供。

## 前置

- Python venv（`.venv`）已装项目依赖（elasticsearch>=8.19,<9 客户端）。
- 进程环境（或本机未跟踪的 `.env`）必须提供 `DASHSCOPE_API_KEY`；`ELASTICSEARCH_URL=http://127.0.0.1:9200` 为 POC 默认。
- Elasticsearch 8.19.18 Windows ZIP 已位于 `.runtime/elasticsearch-8.19.18`（含内置 JDK）。

## 1. 启动 Elasticsearch

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-elasticsearch.ps1
# 另开窗口验证：
Invoke-RestMethod http://127.0.0.1:9200/_cluster/health
```

- 8.19.18、single-node、yellow 即正常（replicas=0）。
- 本地 POC 关闭 security/TLS/ML/磁盘水位（仅 loopback；正式部署必须恢复认证与磁盘保护）。

## 2. 导入正式数据（真实 DashScope embedding）

```powershell
.\.venv\Scripts\python.exe scripts\bootstrap_micro_tasks.py
.\.venv\Scripts\python.exe scripts\bootstrap_health_knowledge.py
```

- `micro_tasks_v1`：23 条审核微任务。
- `health_knowledge_v1`：29 条审核知识 chunk。
- `source_documents_v1`、`user_*`、`interaction_logs_v1`、`user_questionnaire_v1` 由 backend lifespan 自动创建。

## 3. 启动 Backend

```powershell
.\.venv\Scripts\python.exe -m uvicorn weilv.api.app:app --host 127.0.0.1 --port 8000
```

- 看到 `Application startup complete` 即 PASS（lifespan 会确保 user 索引并连接 ES）。
- 验证：`Invoke-RestMethod http://127.0.0.1:8000/health`

## 4. 启动 Production Frontend

```powershell
$env:VITE_UI_MODE='production'
$env:VITE_USER_ID='smoke-user-002'   # 受控测试身份，非默认生产用户
$env:VITE_API_BASE_URL='http://127.0.0.1:8000'
npm run dev   # 或 npm run build + preview
```

## 5. 运行 E2E smoke

```powershell
node scripts/production-e2e-smoke.mjs http://localhost:5173/ 127.0.0.1:8000
```

- 输出 `mode: PRODUCTION`、network summary（PUT /profile、POST /recommendations、POST events、GET memories、GET weekly、POST /recommend/agentic 均 200）。
- 新用户（profile 404）→ Onboarding → 完成后进入 Today；已存在用户 → 直接 Today。
- B2 事件持久化可用 ES 复核：
  ```powershell
  .\.venv\Scripts\python.exe -c "from elasticsearch import Elasticsearch; import json; c=Elasticsearch('http://127.0.0.1:9200'); [print(json.dumps(h['_source'], ensure_ascii=False)) for h in c.search(index='interaction_logs_v1', query={'query_string': {'query': '*smoke-user-002*'}}, size=5)['hits']['hits']]"
  ```

## 6. 停止

- Ctrl+C 停 frontend / backend；ES 窗口 Ctrl+C 停止。

## 已知边界

- ES security/TLS 关闭仅限本机 loopback POC，不作为部署建议。
- `smoke-user-002` 为受控测试身份；公开上线需真实认证身份替换 USER_IDENTITY_SEAM。
- Weekly 为 UTC 日期边界（LOCAL_DAY_BOUNDARY_LIMITATION）。
- B3：Assistant 走 `POST /api/v1/recommend/agentic/stream`（NDJSON 真实 trace）；旧
  `/recommend/agentic` 保持兼容；一次 submit 只执行一次 Agentic。
- B3 live trace 只暴露粗粒度公开阶段（无 reasoning / 检索原文 / 分数 / diagnostics）。
