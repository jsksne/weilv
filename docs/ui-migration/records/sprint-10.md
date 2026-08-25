# Sprint 10 迁移记录 — Cleanup, Visual Regression & Release Gate

- **baseline commit:** `8db1af0`（fix: remove legacy runtime path）
- **release commit:** `chore: complete weilv ui migration release`

## 清理结论（逐项证明，见 release-checklist）

- **删除文件：无。** 全量引用扫描（含 tests）显示 `frontend/src` 中只有 `env.d.ts` 无引用（Vite env 类型声明，构建必需，非死代码）。
- **保留为 test harness（非 runtime）：**
  - `views/LegacyConsole.vue`
  - `components/{ColdStartQuestionnaire,FeedbackForm,FeedbackResult,RecommendationForm,RecommendationResult,SafetyResult,ServiceStatus,UserProfileSettings}.vue`
  - `composables/{useRecommendationFlow,useQuestionnaire,useFeedbackFlow,useUserProfile}.ts`
  - 理由：新 UI 不提供旧业务入口（7 题问卷提交、结构化 Feedback 表单、Profile 编辑表单、手动推荐表单）。`questionnaire-flow / feedback-flow / profile-flow / recommendation-flow` 四个测试直接挂载 LegacyConsole，验证真实 HTTP/business 契约（问卷保存、结构化 feedback payload、consent 保存、推荐请求形状）。删除即失去这些契约测试覆盖（Sprint 10 禁止）。
- **保留为 runtime 共享组件：** `components/EvidenceList.vue`（新 Assistant → AgentPipeline → AnswerCard → EvidenceList 使用）。
- **保留为视觉级联必需：** `styles/style.css`（legacy 最先导入，冻结 CSS 依赖其 base 复位；`visual-system.test.ts` 锁定顺序）。
- **样式入口：** `src/styles/index.css` 为唯一 style entry（内部按已记录顺序 @import 冻结资产）。

## Visual Regression Gate（可重复机制）

- 脚本：`frontend/scripts/visual-regression.mjs`
- 依赖：`puppeteer-core` + `pixelmatch` + `pngjs`（新增 devDependencies）
- 固定参数（写入 manifest/checklist）：
  - Browser: Chromium headless（ms-playwright chromium-1234 / Edge fallback）
  - Viewports: 1080/960/720/560 × 固定高 900，deviceScaleFactor=1，zoom=1
  - Fonts: `document.fonts.ready` + networkidle0
  - Animation determinism: 注入 `animation:none;transition:none` + `prefers-reduced-motion: reduce`（CDP Emulation.setEmulatedMedia）→ 画面确定，无需随机种子
  - checkpoint: 每个 viewport 独立 reload + 固定 300ms settle
- 捕获集：
  - baseline/prototype/（02-sakura-spring.html 4 viewport fullPage —— 唯一视觉基线）
  - baseline/app/（demo app 20 张：onboarding-step1 + today/assistant/profile/weekly × 4 viewport）
  - candidate/app/（cleanup 后重捕获）
  - diff/（pixelmatch threshold 0.1，pass 阈值 diffRatio ≤ 0.2%）
- 结果：baseline(app) vs candidate(app) —— 见 `tests/visual/diff/manifest.json`

## Accessibility

- 新增 `frontend/src/accessibility.test.ts`（7 用例）：语义导航 aria-label、按钮可理解名称、chat composer label、onboarding consent label、disabled 显式、错误非仅颜色（role=alert + 文本）、reduced-motion 内容可读可交互。
- 通过（不改冻结视觉）。

## Secret / Internal Boundary

- `secret-boundary.test.ts` 扩展：新增 ES 凭据 / raw_query / retrieval_text / embedding 模式；新增"Views 不得 import api/types 或 fixtures"断言。
- 结果：通过。View 层零 DTO/fixture import；前端源码无 keys/内部字段。

## 已知限制（必须持续记录）

- USER_IDENTITY_SEAM：Production 用显式 VITE_USER_ID（可替换 seam），非完整认证系统。
- LOCAL_DAY_BOUNDARY_LIMITATION：Weekly 为 UTC date 边界，非用户本地自然日。
- TODAY_QUERY_DEFAULT 审计：`config/recommendationContext.ts` 只含固定产品意图 query（"请为我推荐一个适合现在完成的微任务。"，VITE_TODAY_QUERY 可覆盖）+ current_context='unknown' + activity_context='unknown'。**不包含** 硬编码睡眠/健康状态/activity/safety boolean/时间/用户偏好。target_stage 来自真实 Profile。无 blocker。
- B3 deferred：Production Assistant 无 fake trace；真实 live trace 不随本 release 提供。

## 测试 / Lint / Build

- `npm test`：31 个文件、全部通过（新增 accessibility 7 用例 + secret-boundary 扩展）。
- `npm run lint`：通过。
- `npm run build`（vue-tsc + vite）：成功。
- 后端相关测试：`test_api / test_task_events / test_weekly / test_memory / test_questionnaire` 通过；`src/weilv` diff = 0。

## Runtime smoke

- Demo：visual capture 脚本 + 浏览器实测 Today/Assistant/Profile/Weekly/Onboarding 均渲染（automated + runtime verified）。
- Production：本地无 Elasticsearch / 后端 → `RUNTIME_PRODUCTION_BLOCKED_BY_ENVIRONMENT`；数据链由 sprint9-integration 自动测试覆盖。
