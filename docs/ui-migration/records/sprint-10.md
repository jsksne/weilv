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

---

# Sprint 10.1 — Animation & Dynamic-State Visual Regression Gate（追加，不改写上文）

- **inherited:** `02ade27`（chore: complete weilv ui migration release）
- **脚本:** `frontend/scripts/animation-regression.mjs`（STATIC gate `visual-regression.mjs` 原样保留，未替换）
- **产物:** `frontend/tests/visual/dynamic/{baseline,candidate,diff,.selfcheck}` + `manifest.json`

## 确定性动画机制（TEST-ONLY，经 evaluateOnNewDocument 注入，不进产品 bundle）

1. 种子化 PRNG（0x9E3779B9）替换 `Math.random`——两侧 petals(26×11)/dust(54×6)/fx(16×3) 随机序列逐字对齐；
2. 虚拟时钟接管 `performance.now / rAF / setTimeout / setInterval`，`__vl.advance(ms)` 以 16ms 帧步进泵送（含微任务排水，safety 3850ms 异步管线可完整推进）；
3. CSS 动画/过渡：`document.getAnimations()` → `pause()` + `playbackRate=0` + `currentTime` 定点 seek；触发前已存在的动画打 `vl-pre-` 标签统一 seek 到 2000ms 相位（两端口径一致）。

**Selfcheck（确定性证明）:** baseline 双跑 0px / 972000、candidate 双跑 0px / 972000。checkpoint 与机器速度无关。

## Browser config

- Normal motion: `prefers-reduced-motion: no-preference`（默认）；启动参数含 `--disable-lcd-text --disable-font-subpixel-positioning`（消除 headless 次像素光栅化噪声）
- Reduced motion: CDP `Emulation.setEmulatedMedia` `prefers-reduced-motion: reduce`；因两侧 reduce CSS 只折叠 duration、不清零 `animation-delay`（badgeIn 1.05s 等），harness 在 reduce 场景真实等待 ≥ 最大 delay 后统一 freeze 终态（两侧同规则）

## Checkpoint 定义（来自原型真实时长，非猜测）

- 任务完成链: done-note(noteIn .15+.8s) / ck-ring(ringDraw .65+.9s) / ck-path(pathDraw .95+.55s) / badge(badgeIn 1.05+.8s，总 1.85s) / fx(particles ≤896ms, orb 620+1150, halo 780+950)
- → **cpA=16ms**（触发后第一帧）**cpB=1100ms**（ring 50%/orb 中段）**cpC=2200ms**（全链完成）
- Safety 管线: 700+650+850+850+800=3850ms → settle 5000ms；view transition: 350ms
- Prototype selector: `.task-card [data-act] / #obSkip / [data-q="neck"] / nav .tab`；Vue selector: `TaskCard.vue / OnboardingFlow.vue [data-action=*] / AssistantView quick chip / AppNavigation.vue`
- Viewport: DYNAMIC 1080 + 560（最低覆盖）；pixelmatch DYNAMIC 容差 0.5%（STATIC 0.2% 不变）

## Pixel diff result（12 pass / 16，4 FAIL = 真实保真度差异，见 manifest rootCause）

| 状态 | 结果 |
|---|---|
| task-completion 1080/560 × cpA/cpB/cpC | 任务卡区域 **6/6 全部 0px**；1080/cpA full 差 0.199%（toast 缺失所致） |
| safety | FAIL（几何差 6px/段距/滚动锚点，见下） |
| memory-consent | pass（prototype 无 consent UI——B6 生产新增，如实记录非发明） |
| view-transition | pass（契约把门：viewIn 存在 + glider transform 一致） |
| motion-contract | 装饰动画 aurora/petals/dust/pulse 全 PASS（name/duration/timing/iteration/direction + petals=26/dust=54 计数）；today 总数 104 vs 103 |
| normal-motion / reduced-motion | 均 pass（reduce 下内容可见、任务可达、终态可见） |

## ANIMATION_REGRESSION_FOUND（只报告，不自动修复）

1. **onboarding 欢迎 toast 缺失**：原型 `finish()`（完成与跳过同路径，02 L1819-1831）→ `toast("🌸 欢迎来到微律 · 春日极光")` 2600ms；Vue `OnboardingFlow.vue` 未实现。影响 task-1080/cpA（full 0.199%）+ motion-contract 计数 −1。
2. **safety 会话栈保真度**（动态门首次暴露；Sprint 10 static gate 为 app-vs-app 对比，从未对原型像素对比）：
   - greeting 原型 `<br><br>`（02 L1013）112px/4行 vs Vue fixture 纯文本（assistant.fixture.ts L239）84px/3行
   - ask-hero/quick-row 区高 +24px（AssistantView/assistant.css）
   - q-bubble 原型「我脖子有点疼。」（02 L1710）vs Vue 缺句号（assistant.fixture.ts L232 / adapters.ts L347）
   - safety-card `p+p` 间距 6px vs 0px（style.css legacy base 复位 p margin）→ 卡高 157 vs 151
   - 自动滚动锚点：原型滚 630px vs Vue ~757px
3. **viewIn 计数 −1**：fill-mode both→backwards（visual-system.test.ts L232-238 白名单的计划内工程化差异，非回归）。

## 验证

- `npm test` 235/235；`npm run lint` 0 error；`npm run build` 成功；backend/`src/weilv` diff = 0；STATIC gate 未触碰（本 sprint 零产品文件修改 → static 像素输出不变）。
- 产品 Vue/CSS：**未修改**（工作区仅新增 scripts/tests/docs）。等待人工授权后才处理上述差异。
