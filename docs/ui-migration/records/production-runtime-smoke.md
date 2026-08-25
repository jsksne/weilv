# Production Runtime Smoke — 记录

- **baseline commit:** `387d319433e3895d18ea413c300deda02ef650bf`
- 目的：真实验证 Production frontend + backend 数据链；如实区分 ENVIRONMENT / CONFIGURATION / CODE_DEFECT blocker。

## 最小运行依赖

| 依赖 | 要求 | 本机状态 |
|---|---|---|
| Frontend | Node + Vite（`VITE_UI_MODE=production` + `VITE_USER_ID` + `VITE_API_BASE_URL`） | 可运行 |
| Backend | Python venv + uvicorn `weilv.api.app:app` | 启动失败（见下） |
| Elasticsearch | `127.0.0.1:9200`（`.env`/默认），需 7 个 index（`elasticsearch_indices.py`） | 缺失 |
| Model/API | `DASHSCOPE_API_KEY`（`.env`） | PRESENT（未实际触发模型调用） |

## 实测结果

### Backend boot → BLOCKED（ENVIRONMENT）

`uvicorn weilv.api.app:app` 首次真实启动：

- FastAPI lifespan 创建 ES client 并执行 `ensure_stage_one_indices` / `ensure_user_memory_indices`（`app.py:71-84`）。
- ES `127.0.0.1:9200` 连接被拒（WinError 10061）→ `Application startup failed. Exiting.`

分类：**ENVIRONMENT**（ES 依赖缺失），非 CONFIGURATION（默认值即项目文档本地 POC 值）、非 CODE_DEFECT（代码按设计硬依赖 ES）。

### Elasticsearch → BLOCKED（ENVIRONMENT）

- 本机无 ES 服务、无安装目录、`elasticsearch` 不在 PATH。
- Docker 未安装；仓库无 docker-compose / Dockerfile。
- 无现成轻量启动方案。按 COST/STOP 规则不再尝试安装（下载大型服务不必要）。
- 精确需求：ES 8.x 于 `127.0.0.1:9200`；index：`source_documents_v1 / health_knowledge_v1 / micro_tasks_v1 / user_profiles_v1 / user_memory_v1 / interaction_logs_v1 / user_questionnaire_v1`（`elasticsearch_indices.py`）；初始化命令：启动 ES 后由 lifespan 的 `ensure_*_index` 自动建索引，另需导入知识库/任务文档数据。

### Frontend Production boot → PASS

`VITE_UI_MODE=production VITE_USER_ID=smoke-user-001 VITE_API_BASE_URL=http://127.0.0.1:8000 npm run dev` + `scripts/production-smoke.mjs`：

- `mode: PRODUCTION`（无 demo badge / hero / fixture task）。
- 真实 API 请求（backend 不可达时仍发出）：`GET /api/v1/users/smoke-user-001/profile` ×2、`GET /api/v1/users/smoke-user-001/weekly?start_date=2026-08-19&end_date=2026-08-25`（UTC 近 7 天正确）。
- 错误态诚实显示"无法连接服务 + 重试"；**无 fixture fallback**；无致命 console error。

### 其余矩阵项 → BLOCKED_BY_ELASTICSEARCH

Existing user / New user onboarding B6 / Today B1 / Task events B2 / Memory B4 / Weekly B5 / Assistant / Safety：全部依赖 ES + 运行中的 backend，本机无法执行真实数据流。自动测试覆盖见 `sprint9-integration.test.ts`（Production API-only 数据链）。

## 已知限制复核

- **USER_IDENTITY_SEAM**：`VITE_USER_ID` 可工作（已实测请求使用 `smoke-user-001`）；非完整认证。
  - 比赛/受控演示：可接受。
  - 公网真实多用户：需替换为真实认证身份（下一阶段候选，不实现）。
- **LOCAL_DAY_BOUNDARY_LIMITATION**：Weekly 请求为 UTC 日期边界（实测 URL 确认），未伪装为本地自然日；未改 backend。
- **TODAY_QUERY_DEFAULT**：Sprint 10 已审计 PASS，本 ticket 未重审；Production 请求 target_stage 来自真实 Profile（代码路径 `buildRecommendationRequest`）。
- **B3 DEFERRED**：Production Assistant 无 fake trace，本 ticket 不实现。

## 代码变更

- 仅新增验证脚本 `frontend/scripts/production-smoke.mjs`（smoke helper）。
- 产品代码 / backend / AI core：0 改动。

## 验证

- frontend tests：239 passed；lint PASS；build（vue-tsc + vite）PASS。
- backend relevant tests：54 passed + 1 已知 pre-existing ES 依赖失败（`test_questionnaire_api_schema_requires_no_dependencies`）。
- `git diff --name-only -- src/weilv`：空（backend 无改动）。
