# Sprint 9 迁移记录 — Formal Integration Switch

- **baseline commit:** `fa03f95`（feat: connect production onboarding consent）
- **sprint commit:** `feat: switch to integrated weilv application`

## 运行结构

```
App.vue
  → AppShell（四视图 slot + 轻量导航，默认 Today，无 Vue Router）
  → TodayView / AssistantView / ProfileView / WeeklyView
  → UI Contract → UiDataSource → FixtureUiDataSource | ApiUiDataSource → Adapter → Backend DTO
```

- View 只依赖 `@/contracts`；DTO→Contract 只在 `data/adapters.ts` / DataSource。
- Demo 只走 Fixture；Production 只走 API；无任何 fixture fallback。
- 旧组件/旧 CSS/旧 flow 源码保留，仅 `?legacy=1` 之后可达（Sprint 10 清理）。

## DataSource 模式行为

- `config/uiMode.ts`（VITE_UI_MODE）：demo | production，缺失/非法 → 配置错误。
- `config/userContext.ts`（新增，Sprint 9）：VITE_USER_ID 显式用户身份 seam；Production 缺失 → 配置错误（绝不落入 demo 用户）。
- `config/recommendationContext.ts`（新增，Sprint 9）：VITE_TODAY_QUERY 默认 query + current_context='unknown'；冻结 Today UI 无查询输入，故提供显式可替换默认 query。

## Production 接入的后端接口

| 页面 | Backend | 说明 |
|---|---|---|
| Today | B1 `POST /recommendations` | 同一次 run 0～3 surfaced tasks；rank1 才有 LLM explanation |
| Today 动作 | B2 `POST .../events` | 每个任务用自己的 recommendation_id；事件体只有 action |
| Profile | B4 `GET/POST .../memories`、`.../memories/{id}/delete` | Memory list 真实展示；删除由后端 forget_memory 完成，成功后才刷新 |
| Weekly | B5 `GET .../weekly` | UTC date 边界；确定性统计 insight，无 AI 文案 |
| Assistant | Agentic `POST /recommend/agentic` | 最终真实回答 + sources + Safety；B3 未实现，管线阶段保持 unavailable |
| Onboarding | B6 `PUT /profile` | grade→target_stage；显式 memory consent；404 新用户→引导，500→error |

## 关键集成决策

- **target_stage 来源**：RecommendationRequest 的 target_stage 由已加载真实 Profile 派生（ApiUiDataSource.buildRecommendationRequest），无硬编码；测试锁定 profile.target_stage == request.target_stage。
- **新用户 → Onboarding**：getProfile 404 → unavailable 语义 → App 展示冻结 5 步引导；500 → app error，绝不当作新用户。
- **Onboarding 完成**：submitOnboarding 成功后 App 重新 `ui.load()` 拉取真实 Profile，关闭引导进入 Today；失败保留错误态。
- **Onboarding skip**：不提交任何数据，Memory 保持关闭；无 Profile 时 Today 诚实显示"完成首次引导后即可获得推荐"。
- **B2 动作**：useDailyTasks.onAction → App 接 DataSource.submitTaskAction(task.recommendation_id, action)；B2 事件 ≠ Feedback（不构造 usefulness/difficulty/reason）。
- **Replace**：Production `canReplace=false`（无后端替代来源），Demo 保留本地 fixture 换卡；restore 在两类模式都只记录本任务事件。

## 仍为 unavailable 的 Production 字段

- Today：sleep/vision/mood stats、rhythm、replace pool、lowMoodSwap（后端无来源）。
- Profile：timePreference、taskPreference、completionPattern（无正式统计来源）；Memory 仅在 B4 可用且 consent 开启时展示。
- Weekly：无 AI 洞察；只展示确定性统计事实。

## 记录的限制

- **USER_IDENTITY_SEAM**：无认证系统；Production 用户身份来自显式 VITE_USER_ID（可替换 integration seam），真实身份提供方接入时替换 `config/userContext.ts`。
- **LOCAL_DAY_BOUNDARY_LIMITATION**：B5 为 UTC date 边界；前端不改后端语义，Weekly 描述与 header 明确标注"UTC 日期边界"。
- **TODAY_QUERY_DEFAULT**：冻结 Today 无查询输入，使用显式默认 query（VITE_TODAY_QUERY 可覆盖）。
- **B3 延后**：Production Assistant 不显示虚构 decomposition/chunk/score/stage 轨迹。

## 测试 / Lint / Build

- `npm test`：30 个文件、227 用例全部通过（新增 sprint9-integration.test.ts 14 例 + api/client.test.ts 4 例）。
- `npm run lint`：eslint 通过。
- `npm run build`：vue-tsc + vite 构建成功。
- 后端 `src/weilv` diff = 0；`test_api/test_task_events/test_weekly/test_memory` 35 passed。

## Runtime smoke

- Demo（VITE_UI_MODE=demo，localhost:5173）：Today 3 卡 + hero、Assistant、Profile（4 section）、Weekly（chart）、Onboarding 首屏均渲染正常（automated + runtime verified）。
- Production：本地无 Elasticsearch / 后端，未做 live 冒烟（blocked by environment）；数据链由集成测试覆盖。
