# 微律 UI 迁移 Sprint 0：仓库审查与执行准备报告

> 审查日期：2026-08-22  
> 审查角色：Lead Engineer  
> 审查依据：`docs/superpowers/plans/2026-08-22-weilv-ui-migration-v3.md`、`ui-prototypes/02-sakura-spring.html` 及当前仓库只读检查结果  
> 结论：**当前不满足 Sprint 1 开始条件。存在 2 个阻塞项，须人工处理后重新确认。**

## 审查边界与验证结果

本次没有修改前端、后端、配置或依赖；没有进入 Sprint 1。除本报告外未创建任何文件。

已执行的只读/诊断检查：

- 完整读取《微律 UI 迁移实施计划 v3》；
- 完整读取唯一视觉基线 `ui-prototypes/02-sakura-spring.html`；
- 读取前端入口、配置、全部组件、composable、API 类型与客户端；
- 读取 FastAPI 的 `schemas.py`、`app.py` 及 Questionnaire schema；
- 运行 `npm test`：7 个测试文件、46 个测试全部通过；
- 运行 `npm run lint`：通过；
- 运行 `npm list --depth=0`：已安装依赖可解析，无缺失依赖报告；
- 未运行 `npm run build`，因为该命令会重写 `dist/` 和 TypeScript build info，不符合 Sprint 0 的零修改约束。现有 `dist/` 不能作为本次新鲜 build 证据。

---

## 1. 当前工程状态

### 1.1 前端工程结构

#### Current

当前 `frontend/src/` 只有以下一级结构：

```text
frontend/src/
├── api/
├── components/
├── composables/
├── test/
├── App.vue
├── main.ts
├── style.css
├── env.d.ts
└── 7 个 *.test.ts 测试文件
```

当前不存在：

- `frontend/src/contracts/`；
- `frontend/src/layouts/`；
- `frontend/src/views/`；
- `frontend/src/styles/`；
- `frontend/src/data/`；
- `frontend/src/config/`；
- `docs/ui-migration/records/`。

这些目录缺失符合尚未开始 Sprint 1 的仓库状态，不属于异常。

实际工具版本：

| 项目 | package.json 声明 | 当前安装版本 | 结论 |
|---|---:|---:|---|
| Vue | `^3.5.18` | 3.5.41 | 与 v3 的 Vue 3.5 一致 |
| TypeScript | `~5.8.3` | 5.8.3 | 与 v3 一致 |
| Vite | `^7.1.2` | 7.3.6 | 与 v3 的 Vite 7 一致 |
| Vitest | `^3.2.4` | 3.2.7 | 与 v3 的 Vitest 3 一致 |
| Vue Test Utils | `^2.4.6` | 2.4.11 | 已具备组件挂载测试能力 |
| vue-tsc | `^3.0.5` | 3.3.9 | 已具备 Vue/TS build 检查能力 |

TypeScript 配置：

- 根 `tsconfig.json` 使用 project references，引用 app 与 node 配置；
- `tsconfig.app.json` 继承 `@vue/tsconfig/tsconfig.dom.json`，间接启用 `strict`、`noUncheckedIndexedAccess`、`verbatimModuleSyntax`；
- `@/*` 已映射到 `./src/*`；
- `src/**/*.test.ts` 被排除在 app build 类型检查之外；
- `tsconfig.node.json` 只覆盖 `vite.config.ts`。

Vite/Vitest 配置：

- 使用 `@vitejs/plugin-vue`；
- `@` alias 与 TypeScript 路径一致；
- Vitest 环境为 `jsdom`；
- 启用 globals；
- setup 文件为 `src/test/setup.ts`；
- setup 在每个测试后恢复 mock 与 global stub。

当前入口：

- `src/main.ts`：创建 Vue app，导入 `App.vue` 和唯一全局样式 `./style.css`，挂载到 `#app`；
- `src/App.vue`：使用 `<script setup lang="ts">`，承担完整功能闭环编排；
- `src/style.css`：181 行全局 CSS，无 scoped/component CSS，无 CSS variable/token 系统。

#### 目标

Sprint 1 的直接目标不是页面迁移，而是：

- 新建最小 `AppShell.vue`，只提供根容器和默认 slot；
- 新建 `contracts/` 骨架；
- 新建 `styles/index.css`，只导入原有 `../style.css`；
- `App.vue` 仅增加 AppShell 包裹，保留现有 script 与业务模板；
- `main.ts` 仅把样式入口改为 `./styles/index.css`；
- 新增 skeleton/边界测试，不迁移视觉、页面或 API。

#### 差异

- 目标目录均尚未建立；这是 Sprint 1 的预期工作，不是前置缺陷。
- 当前 CSS 是全局单文件；目标要求先增加兼容入口，再在后续 Sprint 拆分。
- 当前 App 直接依赖 API DTO；v3 的 Contract 边界尚不存在。
- 当前没有 AppShell、视图容器或 UI DataSource seam。
- 当前没有 Router、Pinia、组件库或动画库，符合 v3 的依赖限制。

#### 风险

- `style.css` 使用全局 `main`、`section`、`form`、`article`、`details`、`button` 等选择器；AppShell 若引入同名语义节点或可见控件，会立刻改变布局或测试 selector。
- `tsconfig.app.json` 排除测试文件，未来 Contract validation 测试不会自动接受 `vue-tsc -b` 的类型检查；只靠 Vitest 运行不能证明测试代码本身经过完整 TypeScript 检查。
- 当前有 `node_modules/` 和 `dist/`，但当前目录不是 Git 工作树，无法判定这些产物是否受版本控制、是否已有用户修改。
- 原型依赖 Google Fonts；当前前端没有字体资源或字体加载策略，后续视觉回归的可重复性存在风险。

### 1.2 当前 App 挂载链

当前挂载链：

```text
index.html #app
  ↓
src/main.ts
  ↓
createApp(App).mount('#app')
  ↓
App.vue <main>
  ↓
旧功能组件与 composable/API 流程
```

#### App.vue 当前职责

`App.vue` 不是纯展示根组件，而是当前功能闭环的页面控制器，承担：

- 服务健康状态；
- 用户画像读取与保存；
- Memory consent 的 `memory_enabled` 设置；
- 冷启动 Questionnaire 的加载、显示和完成状态；
- 推荐请求表单与 Recommendation API 调用；
- allowed / blocked / help_seeking / no_safe_task 分支渲染；
- RecommendationResult 与 EvidenceList；
- Feedback 可用性判断、提交、重试和结果展示；
- profile identity 向推荐表单同步；
- 推荐与反馈的 reset 编排。

#### script setup 与 API 行为

`App.vue` 使用 `<script setup lang="ts">`，直接创建五个 composable：

- `useServiceHealth()`：创建时立即调用 `/health`；
- `useUserProfile()`：在 `onMounted` 中读取 profile；
- `useQuestionnaire()`：profile 已存在时继续读取 schema 与用户 questionnaire；
- `useRecommendationFlow()`：用户提交后调用 Recommendation API；
- `useFeedbackFlow()`：满足 eligibility 后由用户提交 Feedback API。

`App.vue` 还直接导入 `UserProfile` DTO，用于 profile 与 recommendation identity 同步。该依赖属于现有 legacy 功能，Sprint 1 明确要求保留；不能在 Sprint 1 借机迁移到 Contract。

#### template 结构

当前根节点是唯一 `<main>`，内部顺序为：

1. 标题与产品说明；
2. `ServiceStatus`；
3. `UserProfileSettings`；
4. 条件显示的 `ColdStartQuestionnaire`；
5. `RecommendationForm`；
6. 推荐错误分支；
7. allowed 推荐、证据与 Feedback 分支；
8. 非 allowed 的 `SafetyResult` 分支。

#### CSS 依赖

- 所有组件依赖 `main.ts` 导入的单一全局 `style.css`；
- 当前 Vue 文件均没有 `<style>`；
- `main` 的宽度和外边距由全局 `main` selector 控制；
- 问卷和 Feedback 使用共享 `.actions`、表单元素及 questionnaire 专用全局类。

#### 是否可以安全包裹 AppShell

**条件性可以。** Sprint 1 必须同时满足：

- AppShell 根元素不能是 `<main>`，否则会形成嵌套 `<main>` 并同时命中全局 `main` 样式；
- AppShell 只渲染默认 slot，不添加导航、按钮、header、进度条、异步逻辑或 DataSource；
- 不改变 `App.vue` 的 script、composable 创建顺序、`onMounted`、事件处理和条件分支；
- 不把现有 `<main>` 替换成别的元素；
- 不在 Sprint 1 给 AppShell 引入会改变 slot 子树布局的样式；
- 新 `styles/index.css` 只导入一次旧 `style.css`，`main.ts` 不得同时导入两个入口。

满足以上边界时，现有 CSS 没有依赖 `#app > main` 或直接子选择器，最小外层容器不会天然破坏布局。但新增任何可见 Shell 控件都会破坏 Sprint 1 边界及部分测试的“第一个按钮”假设。

---

## 2. Sprint 1 前置条件检查

| 前置条件 | 状态 | 证据/说明 |
|---|---|---|
| v3 计划可读取 | 通过 | 文件存在并已完整读取 |
| 唯一原型可读取 | 通过 | `ui-prototypes/02-sakura-spring.html` 存在，1854 行，已完整读取 |
| 迁移评估报告可读取 | **失败** | 仓库中不存在该报告；当前任务上下文也未提供报告正文 |
| 前端依赖已安装 | 通过 | `npm list --depth=0` 成功，核心版本与 v3 匹配 |
| Vue/TS/Vite 基础配置可用 | 通过 | alias、Vue plugin、strict TS、jsdom Vitest 均已配置 |
| 现有测试基线 | 通过 | 7 个文件、46/46 测试通过 |
| lint 基线 | 通过 | `npm run lint` 通过 |
| build 基线 | 未验证 | Sprint 0 禁止产生文件变更，因此未执行会重写产物的 build |
| App.vue 可最小包裹 | 条件通过 | 必须使用无业务、无可见控件、非 `<main>` 的默认 slot 容器 |
| 旧业务可保持 | 条件通过 | Sprint 1 不得改 script、API、composable、旧 template 分支 |
| 工作树可检查 | **失败** | 当前根目录和 `frontend/` 均无 `.git`，`git status` 返回 not a git repository |
| 单职责 commit/回滚可执行 | **失败** | 无 Git 工作树，无法满足 v3 的每 Sprint commit、Sprint 9/10 分离及回滚要求 |
| Sprint 1 目标目录为空 | 通过 | contracts/layouts/styles 尚不存在，无覆盖冲突 |

**Sprint 1 开始判定：不通过。**

### 2.1 当前测试体系

测试框架：Vitest 3.2.7 + Vue Test Utils 2.4.11 + jsdom 26.1.0。

实际测试分布：

| Test | Location | Dependency | Sprint 影响 |
|---|---|---|---|
| API client，5 个 | `frontend/src/api/client.test.ts` | `api/client.ts`、DTO、mock fetch；不依赖 DOM | Sprint 1 应保持不变；后续 API 扩展必须保留错误净化和 HTTP 契约 |
| Secret boundary，1 个 | `frontend/src/secret-boundary.test.ts` | 递归扫描全部生产 `.ts/.vue`；不依赖旧组件 DOM | Sprint 1 新增的 contracts/layouts 会自动进入扫描范围 |
| App service status，3 个 | `frontend/src/App.test.ts` | 直接挂载 App；依赖 ServiceStatus 文案，并使用 `wrapper.get('button')` 获取第一个按钮 | Sprint 1 AppShell 不得在旧内容前添加按钮或可见 Shell UI |
| Profile flow，3 个 | `frontend/src/profile-flow.test.ts` | `useUserProfile`、App、UserProfileSettings、RecommendationForm；依赖 profile/recommendation select 和 save action selector | Sprint 1 必须保持 template 与 identity 同步逻辑原样 |
| Questionnaire flow，8 个 | `frontend/src/questionnaire-flow.test.ts` | `useQuestionnaire`、App、ColdStartQuestionnaire；依赖 questionnaire testid、action selector、选项 input | Sprint 1 包裹不能改变 conditional mount、问题状态或事件传播 |
| Recommendation flow，15 个 | `frontend/src/recommendation-flow.test.ts` | `useRecommendationFlow`、App、RecommendationForm、RecommendationResult、SafetyResult、EvidenceList；依赖第一个 form、textarea、submit/retry、task/evidence/context selector | Sprint 1 不得增加位于旧 RecommendationForm 之前的 form；不得改变 allowed/safety 分支 |
| Feedback flow，11 个 | `frontend/src/feedback-flow.test.ts` | `useFeedbackFlow`、App、FeedbackForm、FeedbackResult，并复用旧 Recommendation 流程；依赖 feedback testid/action 和 recommendation form | Sprint 1 必须保持 eligibility、推荐 session、反馈提交与重试逻辑 |

测试基线命令结果：

```text
Test Files  7 passed (7)
Tests       46 passed (46)
```

DOM/旧组件依赖结论：

- 40 个测试位于 App、profile、questionnaire、recommendation、feedback 流程文件中，其中大量测试直接或间接依赖旧 App/组件；
- 只有 API client 5 个和 secret boundary 1 个完全不依赖旧 DOM；
- `App.test.ts` 的 first-button selector 与 recommendation/feedback 流程中的 first-form selector 比较脆弱；
- Sprint 1 可以增加外层 DOM，但不能增加先于旧内容的按钮或 form，也不能更换旧 selector；
- v3 所说“现有 46 个测试继续通过”应理解为这 46 个 legacy tests 继续通过，新增 Sprint 1 测试不包含在 46 这个历史基线数字内。

### 2.2 API 与 DTO 边界

#### 前端当前 DTO

`frontend/src/api/types.ts` 已定义：

| 能力 | 已有请求/响应与字段 | 当前缺口 |
|---|---|---|
| Recommendation | `RecommendationRequest`：user_id、query、target_stage、current_context、activity_context、available_minutes 与 6 个安全/场景布尔值；`RecommendationResponse`：status、单个 selected_task、explanation、sources、context_sources、matched_rule_ids、reason_codes、explanation_guard、personalization、recommendation_id、feedback_available | 没有三任务今日面板、任务动作、睡眠/用眼/情绪、节奏、替换池 |
| Selected task | task_id、title、instruction、evidence_chunk_ids、covered_domains、estimated_minutes | 只有单任务；没有 UI 本地状态或三任务独立 session |
| Agentic | **前端没有 Agentic DTO，也没有 Agentic client 方法** | 后端 endpoint 已存在，但前端尚未建模/调用 |
| Feedback | completion_status、usefulness、difficulty、reason；响应含 recommendation_id、task_id、memory_persisted、memory_id、confidence | 没有仅表示 started/replaced/restored 的轻量任务动作 API；完成按钮不能直接伪造成完整反馈 |
| Profile | `UserProfileUpsertRequest` 与 `UserProfile`：user_id、target_stage、memory_enabled、created_at、updated_at | 没有时间偏好、任务偏好、完成率、Memory 列表或删除 |
| Questionnaire | schema、question、option、state、answers、completion_state、memory_record_ids | 前端类型可表示动态题目，但原型五步内容与真实七题 schema 不同 |
| Health | `{ status: string }` | 只用于服务状态 |

`frontend/src/api/client.ts` 当前只有：

- `GET /health`；
- `GET/PUT /api/v1/users/{user_id}/profile`；
- `POST /api/v1/recommendations`；
- `POST /api/v1/users/{user_id}/recommendations/{recommendation_id}/feedback`；
- `GET /api/v1/questionnaire`；
- `GET/PUT /api/v1/users/{user_id}/questionnaire`；
- `POST /api/v1/users/{user_id}/questionnaire/skip`。

#### 后端当前 DTO 与路由

后端还实际存在：

- `POST /api/v1/recommend/agentic`；
- `AgenticRecommendationResponse` 在 RecommendationResponse 基础上增加 `agentic: bool` 与 `diagnostics: dict[str, Any]`。

未发现以下公开 API：

- 今日聚合面板；
- 三任务清单；
- started/replaced/restored 等任务动作；
- Memory 列表与删除；
- Weekly 历史与趋势聚合；
- 真实 Agentic 分阶段事件/流式 trace。

#### DTO 精度风险

前端 DTO 比 FastAPI schema 更严格，但不是由后端 schema 生成：

- 后端 `RecommendationResponse.status` 是普通 `str`，前端收窄为四种 union；
- 后端 selected_task、sources、explanation_guard、personalization 使用 `dict[str, Any]`，前端假定固定字段；
- 后端 Agentic diagnostics 是任意 dict，且现有 diagnostics 包含内部 candidate/ranking/chunk/memory 相关信息；
- 后端 Questionnaire completion_state 是普通 `str`，questions/answers 也是宽泛 dict；
- 前端 API client 使用类型断言返回 T，没有运行时 DTO validation。

因此，Sprint 4～6 的离线 Contract Validation 可以验证“当前批准的代表性 DTO fixture → Adapter → Contract”，但不能仅凭现有宽泛 Pydantic 声明证明所有真实响应都符合前端类型。Agentic diagnostics 未形成前端公开 allowlist 前，不应整体映射到 UI Contract。

---

## 3. Prototype 迁移准备

原型是一个无 Router 的单 HTML SPA，包含四个主视图与一个五步 Onboarding overlay。页面切换由 `.view.active`、tab glider 和全局 JS 控制。

| Prototype 区域 | 对应 Vue 目标 | 依赖 | 难点 |
|---|---|---|---|
| `.bg`、`.blob.b1～b4`、`.bg-grid`、`#petalField`、`#dust`、`.bg-noise` | `AuroraBackground.vue`、`PetalField.vue`、`DustField.vue` 与 effects styles | CSS tokens、RAF、随机数、viewport resize、inline SVG/data URI | 26 花瓣持续 RAF、54 光尘随机属性、SVG gradient ID、卸载清理、确定性视觉测试 |
| `.topbar-wrap/.topbar` | `DockedTaskProgress.vue` | Today 进度、scroll/IntersectionObserver | 只在 Hero 进度滚出视口后显示；与 navbar top 联动，任何时刻只保留一个状态条 |
| `.navbar/.nav-pill/.tabs/.tab-glider` | `AppNavigation.vue`、`BrandLogo.vue`、AppShell view container | active view、本地导航状态、字体加载、resize | glider 依赖 tab offsetWidth/offsetLeft；sticky/fixed/z-index；不允许引入 Router |
| `#view-today .hero` 与 `.progress-row` | `TodayHero.vue`、`TaskProgress.vue` | Today Contract、用户名/日期/状态/进度 fixture 或 API | Hero arc、文字渐变、highlight pulse、进度与 docked 状态同步 |
| `.observe-card` | `ObservationCard.vue` | Demo fixture；Production 需要 B1 | 当前 API 无睡眠、用眼、情绪和今日建议聚合；Production 必须 unavailable |
| `.mood-card`、`#moodRow`、`#timeChips`、`#btnCheck` | `DailyCheckCard.vue`、`MoodSelector.vue`、`AvailableTimeSelector.vue` | 本地 UI state、Today Contract | 原型会因 mood 在前端直接替换任务内容；只能作为 Demo fixture 行为，不能迁移成 Production 推荐逻辑 |
| `#taskList/.task-card` | `TaskList.vue`、`TaskCard.vue`、`useDailyTasks.ts` | 三任务 fixture、单任务 API、task local state、Feedback seam | pending/start/done/partial/skip/restore/replace；现 API 只返回一任务且无动作 API；完成动效含粒子汇聚、orb、halo、check path 和进度联动 |
| `.breath-card/.breath-stage` | `BreathCard.vue`、`useBreathCycle.ts` | CSS 9 秒 cycle、同步计时器 | CSS 与文字计时同频、interval/timeout/RAF 清理、reduced-motion |
| `.rhythm-card` | `RhythmTimeline.vue` | Demo fixture；Production 需要 B1 | 当前无节奏 API，不能把原型时间当真实用户数据 |
| `#view-assistant/.ask-wrap` | `AssistantView.vue`、`AssistantHero.vue`、`AssistantOrb.vue` | Assistant Contract、Demo fixture、Agentic final API | 专属极光背景、orb/ring、多级入场与页面级滚动 |
| `.quick-row/.ask-log/.pipe/.stage-card/.chunk/.answer-card/.safety-card/.cites` | Quick prompts、ConversationLog、AgentPipeline、Stage、KnowledgeChunk、AnswerCard、SafetyNotice、EvidenceList | Demo fixture；Production 只有 Agentic 最终响应 | 原型阶段、chunk、相关度和延迟均为前端模拟；现后端无真实事件 seam；原型大量 innerHTML，Vue 必须改为结构化渲染 |
| `#chatForm` 与原型输入分流 | `ChatComposer.vue`、`useAssistantFlow.ts` | Demo key/fixture 或 Production Agentic API | 原型用疼/睡/考试关键词正则决定 Safety/回答；该逻辑严禁迁移到 Production，Safety 必须来自后端结构化状态 |
| `#view-profile/.profile-grid` | `ProfileView.vue`、PreferenceCard、CompletionPatternCard、CompletionRing | Demo fixture；Production Profile API 与未来 B4/B5 | 当前 API 只有 stage 与 memory_enabled；偏好、完成率和规律没有查询来源 |
| `#memList/.mem-item/.consent` | `MemoryCard.vue`、`MemoryList.vue`、`MemoryItem.vue` | Demo fixture；Production 需要 B4 与 consent | 原型宣称删除后真正消失且影响推荐；当前无查询/删除 API，Production 不能展示或承诺 |
| `#view-weekly/.chart-card/.week-grid` | `WeeklyView.vue`、WeeklyMinutesChart、AdjustmentTimeline、WeeklyInsightCard | Demo fixture；Production 需要 B5 | SVG path/dots/labels 动态插入、一次性播放、当前无历史 API、洞察不能由前端或 LLM补造 |
| `#onboard/.ob-step.s1～s5` | `OnboardingFlow.vue`、OnboardingStep、ProfileGenerationStage | Demo fixture、localStorage；Production Questionnaire/Profile 与 B6 | 原型 5 步对真实 7 题；原型含“大学”但后端 TargetStage 不含大学；sleep/issues/duration/slot 与真实 schema 不一一对应；Memory consent 不得默认开启 |
| `#toastBox/.toast` | `ToastHost.vue`、`useToast.ts` | 本地 UI event | timeout 清理；原型部分文案错误承诺已同步/已记住，Production 必须由 API 成功状态决定 |
| `#protoTag` | `PrototypeReplayControl.vue` | Demo Mode、Onboarding replay | 只应在显式 Demo Mode 出现；不得进入 Production |
| inline SVG symbol sprite | `IconSprite.vue` | 原型 SVG path | 需要保持原图形与统一线宽，避免重复 symbol/gradient ID |

原型迁移总体难点：

1. 原型视觉、交互和数据语义混在单文件全局 CSS/JS 中，需要拆所有权但不能改变行为；
2. 原型持续 RAF、interval、timeout 和全局 listener 没有卸载生命周期，Vue 化必须补清理；
3. 原型通过 `innerHTML` 生成任务、pipeline 与回答，不能直接搬入 Vue；
4. 原型把 Demo 数据描述成真实记忆、真实反馈和真实历史，Production 必须改由 Contract 状态控制；
5. 原型依赖随机粒子和外部字体，视觉回归必须控制随机数与字体完成状态；
6. 原型的 Safety 关键词正则、mood 改写任务和预设 Assistant 回答只是演示行为，不能成为第二套前端 AI/推荐逻辑。

---

## 4. 阻塞问题

### BLOCK-01：迁移评估报告缺失

- **问题：** v3 在 Global Constraints、Prototype Reading Rule 和统一执行纪律中均要求每个 Sprint 开始前读取《02-sakura-spring Vue 工程化迁移评估报告》。仓库搜索只找到 v3 对报告的引用，没有报告文件；当前任务也未提供报告正文。
- **影响 Sprint：** Sprint 1 起全部 Sprint。
- **建议：** 人工提供报告正文，或把已批准报告放入明确的仓库文档路径；随后由执行 Agent 完整读取并在 Sprint 1 迁移记录中引用。不得由 v3 或原型反推报告内容。
- **是否阻塞：** **是，P0。** v3 明确规定资料缺失时停止当前 Sprint。

### BLOCK-02：当前目录不是 Git 工作树

- **问题：** 根目录与 `frontend/` 均不存在 `.git`；`git status` 返回“not a git repository”。因此无法检查用户已有改动、建立单职责 commit、比较冻结核心文件、回滚 Sprint，亦无法满足 Sprint 9/10 必须分属两个提交的要求。
- **影响 Sprint：** Sprint 1～10；Sprint 1 已要求检查工作树并提交单职责 commit。
- **建议：** 人工确认当前目录是否为导出的副本，并将 Codex 切换到真实 Git checkout；若项目尚未纳入版本控制，应由人工单独授权和决定初始化/基线策略。本 Sprint 0 不初始化 Git。
- **是否阻塞：** **是，P0。** 在没有可追踪基线的情况下开始结构迁移，不满足 v3 的回滚与冻结审计要求。

---

## 5. 计划冲突与风险列表

### 5.1 计划可执行性问题

| 严重度 | 问题 | 影响 Sprint | 建议 | 是否阻塞 Sprint 1 |
|---|---|---|---|---|
| P0 | 迁移评估报告不存在 | 1～10 | 提供已批准报告并明确路径 | 是 |
| P0 | 无 Git 工作树，无法执行工作树检查、commit 和回滚 | 1～10 | 切换到真实 checkout 或由人工另行决定版本控制基线 | 是 |
| P1 | `tsconfig.app.json` 排除 `*.test.ts`，未来 Contract validation 测试不受 app build 类型检查 | 1、4～8 | 不引入新栈；在编码阶段明确使用现有工具提供测试文件 type-check 证据，或用 source/runtime test 覆盖边界 | 否 |
| P1 | v3 的“View 只可导入 `@/contracts/*`”按字面执行会禁止 Vue、组件和 composable import | 4～10 | 人工确认该规则指“View 的业务数据类型不得来自 API DTO”；不要扩大解释为禁止正常 Vue/组件依赖 | 否，影响后续 |
| P1 | Sprint 5 已要求补 Agentic DTO，Sprint 8 又写“增加 Agentic endpoint 客户端和 DTO 类型” | 5、8 | Sprint 8 应视为复用/完成 Sprint 5 DTO，仅新增 client 与 DataSource 接入；不要重复定义类型 | 否，影响后续 |
| P1 | “可公开的粗粒度 diagnostics”没有正式字段 allowlist，而后端 diagnostics 是宽泛 dict 且含内部轨迹/ID | 5、8 | 未获得 allowlist 前全部映射为 unavailable；不得整体透传 diagnostics | 否，影响后续 |
| P1 | 计划要求可重复视觉回归，但当前无视觉测试机制，原型字体来自 Google Fonts | 3、10 | 在不强制新依赖的前提下，于对应 Sprint 确定固定浏览器、字体就绪与 baseline 机制；外部字体不可用时不得偷偷替换设计字体 | 否，影响后续 |
| P1 | 原型 5 步 Onboarding 与后端真实 7 题不匹配；原型含“大学”，后端 stage 不支持 | 6 | 遵守 B6；Demo 使用 fixture，Production 使用真实 schema/unavailable，不提交原型答案 | 否，影响后续 |
| P1 | FastAPI response schema 多处是 `str`/`dict[str, Any]`，不能单靠 schema 证明前端严格 DTO | 4～8 | 离线 validation 使用经过后端测试验证的代表性 DTO fixture；对未知字段/状态 fail closed 或 unavailable | 否，影响后续 |
| P2 | 当前 legacy 测试使用 first-button、first-form 等位置敏感 selector | 1、2、9 | Sprint 1 不新增可见控件/form；后续只在对应测试迁移 Sprint 修改 selector，不在 Sprint 1 改旧断言 | 否 |
| P2 | `npm run build` 未在 Sprint 0 新鲜验证 | 1 | 解除 P0 后，在任何编辑前先运行并记录 baseline build，再开始 Sprint 1 | 否，但必须先做 |

### 5.2 迁移技术风险

#### P0

- 无批准评估报告，无法按 v3 建立可追溯的 Sprint 1 migration record。
- 无版本控制基线，无法证明冻结 AI 核心未被修改或安全回滚。

#### P1

- AppShell 若使用 `<main>` 或添加可见控件，会破坏语义、全局 CSS 和现有 DOM 测试。
- 当前 App 在 setup/mount 阶段已有健康检查与 profile/questionnaire 请求；任何重建或条件挂载都可能改变调用次数和顺序。
- 原型随机动画、持续 RAF、interval、timeout 与 listener 需要生命周期化，否则测试和切页会泄漏。
- 原型 Demo 行为与真实 API 能力差距大，特别是三任务、Memory、Weekly、Agent trace 和任务动作。
- 后端 Agentic diagnostics 不能直接作为 UI trace 或前端公开 DTO。
- 外部字体加载不稳定可能导致 nav glider 尺寸和视觉快照漂移。

#### P2

- 旧全局 CSS 类名如 `.card`、`.live`、`.sub`、`main`、`section` 很容易污染新 Shell 和后续页面。
- 原型 SVG 动态节点和 gradient/symbol ID 可能重复。
- 当前测试 teardown 只恢复 mock/global stub，不负责 wrapper unmount；新增 timer/RAF 组件测试需要显式卸载。
- 当前 `dist/` 已存在，但没有 Git 状态，不能判断是否陈旧或属于用户产物。

---

## 6. 建议执行顺序

在人工确认前不得进入 Sprint 1。建议顺序如下：

1. **补齐迁移评估报告**  
   提供《02-sakura-spring Vue 工程化迁移评估报告》的已批准正文和稳定路径；确认其唯一视觉依据仍是 02 原型。

2. **恢复可审计的 Git 工作树**  
   将执行环境切换到真实 checkout，或由人工明确版本控制基线。确认 `git status` 可用，并记录所有既有修改；不得自动初始化、清理或覆盖当前目录。

3. **重新执行 Sprint 0 最小复核**  
   只复查上述两个 P0 是否解除；确认 v3、原型、评估报告三者均可读取，确认冻结后端文件基线可比较。

4. **在编辑前建立工程基线**  
   在真实工作树中运行 `npm test`、`npm run lint`、`npm run build`，记录 46 个 legacy tests、lint 和 build 结果。若 baseline build 失败，先停下报告，不进入 Sprint 1 修改。

5. **建立 Sprint 1 迁移记录**  
   创建 `docs/ui-migration/records/sprint-01.md`，逐项填写 Prototype、HTML selector、Original behavior、Vue component、Contract dependency；编码前完成前五项。

6. **按 v3 Sprint 1 最小边界执行**  
   先写 AppShell slot/skeleton 边界测试，再建立 contracts、非 `<main>` 的无业务 AppShell、单一样式兼容入口；只包裹现有 App，不迁移业务、API、视觉或页面。

7. **Sprint 1 独立验收并等待人工确认**  
   验证原 46 个测试仍通过，新测试通过，lint/build 通过，App script 无变化，冻结后端 diff 为零，并提交单职责 commit。人工通过后才进入 Sprint 2。

---

## 最终判定

当前前端工具链、依赖、测试和 legacy App 基线总体健康，Sprint 1 的“最小 AppShell 包裹 + 单一样式入口”在严格边界下技术上可行。

但以下条件尚未满足：

1. 迁移评估报告不可读取；
2. 当前目录不是 Git 工作树。

因此 Sprint 0 审查结果为：**BLOCKED / 不批准进入 Sprint 1。**

等待人工补齐上述条件并确认后，再重新授权 Sprint 1。
