# 微律 UI 迁移实施计划 v3

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按 Sprint 和任务逐项执行。每个 Sprint 都必须独立测试、复核并设置人工检查点。

**Goal:** 以 `ui-prototypes/02-sakura-spring.html` 为唯一视觉基线，将微律冻结 UI 原型稳定迁移到现有 Vue 3 + TypeScript + Composition API 工程，同时保持冻结 AI 核心零污染，并通过显式 UI Contract、DataSource seam 和 Demo/Production 模式隔离实现可验证的渐进交付。

**Architecture:** View 只依赖 `frontend/src/contracts/` 中的 UI Contract；DataSource Interface 向上提供 Contract，向下分别由 Fixture 和 API 实现，API Implementation 只能通过 Adapter 消化 Backend DTO。Sprint 1 先在真实 `App.vue` 挂载链建立最小 AppShell 和样式入口，Sprint 2 完成 Shell，Sprint 3 再在真实挂载上下文迁移视觉系统，随后严格按 Today、Assistant、Profile、Weekly 的产品优先级迁移页面。页面 Sprint 同步用 Mock Backend DTO 对 Adapter 与 UI Contract 做离线契约验证，但不调用真实后端。

**Tech Stack:** Vue 3.5、TypeScript 5.8、Composition API、Vite 7、Vitest 3、Vue Test Utils、原生 CSS、原生 SVG、`requestAnimationFrame`。不新增 Pinia、Vue Router、组件库或动画库。

**Spec:** `ui-prototypes/02-sakura-spring.html`；本计划基于《微律 UI 迁移实施计划 v2》做冻结修订，并继承《02-sakura-spring Vue 工程化迁移评估报告》的结论。除本版明确新增的四项门禁外，v2 的架构方向、Sprint 顺序与范围约束保持不变。

## Global Constraints

- 唯一视觉基线是 `ui-prototypes/02-sakura-spring.html`。
- 不参考其他 prototype 作为设计来源。
- 不重新设计页面结构、颜色体系、排版层级或核心动效。
- 不修改 Basic RAG、Personal RAG、Agentic RAG、Agent Graph、Memory、Feedback Loop、Safety、Output Guard 或协同排序核心逻辑。
- View 组件不得导入或依赖 FastAPI DTO。
- Fixture 与 API 必须通过同一个 DataSource Interface 输出 UI Contract。
- Demo Mode 只使用 fixture；Production Mode 只使用 API。
- API 失败不得自动 fallback 到 fixture。
- 环境模式必须显式配置，不允许根据请求成功与否隐式切换。
- 不默认开启 Memory，不代替用户作出 Memory consent。
- 不为 Feedback API 自动伪造 usefulness、difficulty 或 reason。
- 不在前端复制 Safety、RAG、Memory 排序或 Agentic 决策逻辑。
- 不让浏览器直接访问 Elasticsearch。
- 不在 UI 迁移中引入 Pinia、Vue Router、Element Plus、其他组件库或动画框架。
- 每个 Sprint 只修改其列出的范围；禁止顺手重构相邻模块。
- 每个 Sprint 结束必须运行相关测试、完整前端测试、lint 和 production build。
- 每个 Sprint 开始前必须读取本 Sprint、迁移评估报告和 02 原型对应区域，并先写迁移记录；资料缺失时停止该 Sprint，不得猜测补全。
- 最终验收必须存在可重复执行的视觉对比机制；单次人工目测不能替代视觉回归门禁。

---

## 1. 架构审查结论

### 1.1 Sprint 顺序调整：采纳

v2 确立、v3 保持并补充分段门禁的顺序为：

```text
Sprint 1  工程骨架与最小挂载切换
    ↓
Sprint 2  AppShell + 样式入口
    ↓
Sprint 3  视觉系统迁移
    ↓
Sprint 4  Today
    ↓
Sprint 5  Assistant
    ↓
Sprint 6  Profile + Onboarding
    ↓
Sprint 7  Weekly
    ↓
Sprint 8  DataSource 与现有 API 接入
    ↓
Backend Interface Gates
    ↓
Sprint 9  正式 Integration Switch
    ↓
Sprint 10 Cleanup & Release
```

调整原因：

1. CSS tokens、全局背景、sticky、fixed、z-index 和响应式规则需要在真实 AppShell DOM 中验证。
2. `backdrop-filter`、视图层级、吸附进度和全局粒子都依赖真实挂载关系。
3. 先迁移脱离挂载点的视觉系统，会增加选择器、层叠顺序和布局返工。
4. Sprint 1 的最小挂载不迁移业务，风险可控，并可保持现有功能与测试。
5. Sprint 9 只负责正式切换，Sprint 10 才清理旧实现，避免切换、删除和发布回归集中在一次提交中。

### 1.2 Sprint 1 App.vue 修改策略：允许最小切换

Sprint 1 允许：

- `App.vue` 导入并包裹 `AppShell`；
- 当前 `App.vue` 的 script、composable、API 调用和业务模板原样保留；
- `main.ts` 把样式入口从 `./style.css` 切换为 `./styles/index.css`；
- `styles/index.css` 在 Sprint 1 仅导入现有 `../style.css`，不迁移视觉规则。

Sprint 1 禁止：

- 删除或隐藏旧功能；
- 修改推荐、反馈、画像或问卷逻辑；
- 引入四页面导航；
- 接入新的 API；
- 迁移任何页面模块；
- 迁移原型 CSS 或动画；
- 修改现有 API DTO；
- 修改后端。

成功标准是：真实应用已经经过 AppShell 和新样式入口，但用户看到的功能、DOM 语义和业务行为不变。

### 1.3 UI Contract 层：新增并强制执行

最终依赖方向：

```text
Vue View / Feature Component
            ↓
       UI Contract
            ↓
   DataSource Interface
        ↙          ↘
Fixture Implementation   API Implementation
                              ↓
                           Adapter
                              ↓
                         Backend DTO
```

规则：

- View 只可导入 `@/contracts/*`。
- `api/types.ts` 只表示后端 DTO。
- DTO 到 UI Contract 的转换只能出现在 `data/adapters.ts` 或 DataSource 实现中。
- Fixture 必须直接满足同一 Contract，不得创建另一套页面专用类型。
- Contract 不暴露 Elasticsearch ID、Memory ID、Safety rule ID 或 Output Guard reason code。
- Contract 中的 unavailable、loading、error、demo 标识必须是显式状态。

### 1.4 产品优先级：保持 Today 为中心

页面开发顺序固定为：

1. Today
2. Assistant
3. Profile
4. Weekly

理由：微律核心价值链是：

```text
感知用户
   ↓
推荐微任务
   ↓
用户执行与反馈
   ↓
长期个性化
```

Assistant 是解释和交互入口，不是产品中心。不得为了聊天展示而延后 Today 的任务闭环或把 Assistant 状态提升为全局主状态。

---

## 2. 目标文件结构

```text
frontend/src/
├── main.ts
├── App.vue
├── api/
│   ├── client.ts
│   └── types.ts
├── config/
│   └── uiMode.ts
├── contracts/
│   ├── common.ts
│   ├── shell.ts
│   ├── today.ts
│   ├── assistant.ts
│   ├── profile.ts
│   ├── weekly.ts
│   ├── onboarding.ts
│   ├── uiDataSource.ts
│   └── index.ts
├── data/
│   ├── adapters.ts
│   ├── createUiDataSource.ts
│   ├── apiUiDataSource.ts
│   ├── fixtureUiDataSource.ts
│   └── fixtures/
│       ├── shell.fixture.ts
│       ├── today.fixture.ts
│       ├── assistant.fixture.ts
│       ├── profile.fixture.ts
│       ├── weekly.fixture.ts
│       └── onboarding.fixture.ts
├── layouts/
│   └── AppShell.vue
├── views/
│   ├── TodayView.vue
│   ├── AssistantView.vue
│   ├── ProfileView.vue
│   └── WeeklyView.vue
├── components/
│   ├── shell/
│   ├── effects/
│   ├── today/
│   ├── assistant/
│   ├── profile/
│   ├── weekly/
│   └── onboarding/
├── composables/
│   ├── useAppNavigation.ts
│   ├── useDockedProgress.ts
│   ├── useMotionPulse.ts
│   ├── useDecorativeField.ts
│   ├── useDailyTasks.ts
│   ├── useBreathCycle.ts
│   ├── useAssistantFlow.ts
│   ├── useOnboarding.ts
│   └── useWeeklyChart.ts
└── styles/
    ├── index.css
    ├── reset.css
    ├── tokens.css
    ├── base.css
    ├── typography.css
    ├── glass.css
    ├── animations.css
    ├── aurora.css
    ├── effects.css
    ├── navigation.css
    ├── layout.css
    ├── today.css
    ├── assistant.css
    ├── profile.css
    ├── weekly.css
    ├── onboarding.css
    └── accessibility.css
```

不新增 `models/ui.ts`。v1 中该职责统一收敛到 `contracts/`。

---

## 3. Demo Mode 与 Production Mode

### 3.1 显式模式

使用一个必填环境配置表达模式：

- `demo`：FixtureUiDataSource；
- `production`：ApiUiDataSource。

模式缺失或值非法时：

- 开发环境显示明确配置错误；
- 测试必须显式注入模式；
- production build 不得静默假定 demo；
- 不根据 API 是否可用推导模式。

### 3.2 Demo Mode

用途仅限：

- 冻结原型演示；
- 页面视觉开发；
- 自动化视觉测试；
- 动画与状态覆盖；
- 缺失后端接口前的产品验收。

规则：

- 只读 fixture；
- 不向真实后端写入推荐、反馈、问卷或 Memory；
- 显示原型的 `PrototypeReplayControl` 或等价 demo 标识；
- fixture 数据必须保存在 `src/data/fixtures/`；
- 随机动画在测试中使用固定种子。

### 3.3 Production Mode

规则：

- 只使用 API；
- API 失败显示 loading/error/retry；
- 不展示 fixture；
- 不显示模拟阶段、模拟历史、模拟记忆或模拟趋势；
- 后端无接口的模块显示明确 unavailable 状态；
- 不把本地任务状态表述为“已同步”或“薇薇已记住”。

### 3.4 禁止隐式降级

以下模式明确禁止：

```text
API 请求
  ├── 成功 → 真实数据
  └── 失败 → fixture
```

正确模式是：

```text
显式 demo → fixture only
显式 production → API only → 失败状态
```

### 3.5 Prototype Reading Rule 与迁移记录

每个 Sprint 开始前，编码 Agent 必须完整读取：

1. 本计划中当前 Sprint 的全部内容；
2. 《02-sakura-spring Vue 工程化迁移评估报告》中与当前 Sprint 对应的章节；
3. `ui-prototypes/02-sakura-spring.html` 中与当前组件、状态和动效对应的 HTML、CSS 与脚本区域。

当前仓库未发现迁移评估报告的 Markdown 文件。执行前必须由任务上下文提供该报告，或先将其作为只读依据纳入仓库文档；若无法读取，编码 Agent 必须停止当前 Sprint 并明确请求补充，不得从文件名、截图或其他 prototype 推断其内容。

每个 Sprint 必须新增或更新一份记录：

```text
docs/ui-migration/records/sprint-XX.md
```

该记录始终计入当前 Sprint 的新增/修改文件范围，即使后续 Sprint 文件清单不再重复列出。

每个迁移对象使用以下固定格式：

```text
Prototype:
HTML selector:
Original behavior:
Vue component:
Contract dependency:
Test coverage:
```

记录必须在修改组件前建立，在验收时补齐测试结果。`HTML selector` 必须能在唯一基线文件中定位；`Original behavior` 必须同时覆盖结构、状态、交互和动效，不得只写视觉描述。

明确禁止：

- 根据截图重新设计或反推未读取的实现；
- 自行补充视觉元素、文案、状态或装饰；
- 自行改变交互逻辑、动画时序或页面结构；
- 从其他 prototype 复制结构、CSS 或行为；
- 因 Vue 组件化而删减原型核心动效。

---

# Sprint 1：工程骨架与最小挂载切换

## 目标

建立真实 AppShell 挂载点、UI Contract 目录和新样式入口，同时保持当前功能、业务逻辑和页面内容不变。

## 修改文件

- `frontend/src/App.vue`
- `frontend/src/main.ts`

## 新增文件

```text
frontend/src/layouts/AppShell.vue
frontend/src/contracts/common.ts
frontend/src/contracts/shell.ts
frontend/src/contracts/today.ts
frontend/src/contracts/assistant.ts
frontend/src/contracts/profile.ts
frontend/src/contracts/weekly.ts
frontend/src/contracts/onboarding.ts
frontend/src/contracts/uiDataSource.ts
frontend/src/contracts/index.ts
frontend/src/styles/index.css
frontend/src/ui-skeleton.test.ts
```

## 实施边界

- `AppShell.vue` 在本 Sprint 只提供应用根容器和默认 slot。
- `App.vue` 只增加 AppShell import，并用 AppShell 包裹现有模板。
- `App.vue` 当前 script setup 内容不得改写。
- `main.ts` 只把样式 import 指向 `styles/index.css`。
- `styles/index.css` 只导入原有 `../style.css`。
- Contract 文件定义稳定页面结构、状态枚举和 DataSource 方法；不得包含 FastAPI DTO。
- 四个新 View 文件本 Sprint 不创建，避免空壳页面被误接入。

## 执行任务

- [ ] 为 AppShell 默认 slot 写挂载测试，确认 slot 内容原样渲染。
- [ ] 建立 Contract 文件并验证它们不导入 `@/api/types`。
- [ ] 创建最小 AppShell 根容器。
- [ ] 最小修改 App.vue，只做包裹。
- [ ] 切换 main.ts 样式入口，并让新入口只导入旧样式。
- [ ] 运行现有全部前端测试、lint 和 build。
- [ ] 检查 App.vue 原业务 import、composable 和事件处理未变化。

## 风险

- 包裹根节点改变现有 CSS 子选择器。
- `main` 元素层级变化导致测试 selector 变化。
- Contract 过早包含后端字段。
- 新样式入口造成旧样式重复加载。

## 验收标准

- 当前功能 UI 的文本、表单和按钮均可继续使用。
- 现有 46 个测试继续通过，不通过修改业务断言来规避失败。
- App.vue 业务 script 无变化。
- 没有 API 新增调用。
- 没有页面迁移、视觉迁移或动画迁移。
- `main.ts` 只加载一个样式入口。
- View 不存在对 FastAPI DTO 的依赖。
- `npm test`、`npm run lint`、`npm run build` 通过。

---

# Sprint 2：AppShell 与样式入口

## 目标

在真实挂载链中完成 AppShell 的结构接口、视图容器、导航状态、全局层级和样式 import 顺序，但不迁移页面业务。

## 修改文件

- `frontend/src/layouts/AppShell.vue`
- `frontend/src/styles/index.css`
- `frontend/src/contracts/shell.ts`
- `frontend/src/contracts/uiDataSource.ts`
- `frontend/src/App.vue`，仅补充 Shell 所需的非业务 props/slot

## 新增文件

```text
frontend/src/components/shell/AppNavigation.vue
frontend/src/components/shell/BrandLogo.vue
frontend/src/components/shell/DockedTaskProgress.vue
frontend/src/components/shell/ToastHost.vue
frontend/src/components/shell/IconSprite.vue
frontend/src/components/shell/PrototypeReplayControl.vue
frontend/src/composables/useAppNavigation.ts
frontend/src/composables/useDockedProgress.ts
frontend/src/composables/useToast.ts
frontend/src/styles/reset.css
frontend/src/styles/base.css
frontend/src/styles/navigation.css
frontend/src/styles/layout.css
frontend/src/data/fixtures/shell.fixture.ts
frontend/src/app-shell.test.ts
```

## 实施边界

- AppShell 定义 today、assistant、profile、weekly 四个 named slot，但当前 App.vue 继续把旧功能放在默认 legacy slot。
- Shell 组件通过独立测试挂载验证，不在当前业务页面中强行显示四个空页面。
- `styles/index.css` 明确 import 顺序，并暂时保留旧 `style.css` 兼容导入。
- Sprint 2 不迁移极光背景、花瓣、光尘和页面样式。
- Sprint 2 不调用 DataSource。

## Fixture 使用

`shell.fixture.ts` 只提供独立 Shell 测试所需的：

- 标签名称；
- 用户显示名；
- 日期；
- 任务进度；
- Toast 示例。

不包含推荐、健康状态、Memory 或周度数据。

## 执行任务

- [ ] 为四 slot 视图切换、导航 glider 和 docked progress 写失败测试。
- [ ] 完成 Shell Contract，固定 view key 与进度状态。
- [ ] 实现 AppNavigation 和视图容器，不引入 Router。
- [ ] 实现 useAppNavigation，并保证默认页为 Today。
- [ ] 实现 useDockedProgress，优先使用 IntersectionObserver。
- [ ] 实现 ToastHost 和 useToast。
- [ ] 建立样式 import 顺序，保留旧样式兼容入口。
- [ ] 在独立 Shell 测试中验证 resize、滚动吸附和视图 slot。
- [ ] 运行完整测试、lint 和 build。

## 风险

- 新旧 `main`、`.shell`、`.card` 类名冲突。
- glider 在字体加载后尺寸漂移。
- AppShell slot 与旧模板层级冲突。
- sticky navbar 和 fixed progress 的 z-index 不可验证。

## 验收标准

- AppShell 在真实 App 根节点中挂载。
- 旧业务继续可见且可操作。
- Shell 独立测试可切换四个 named slot。
- 不使用 Vue Router。
- 不创建全局 store。
- 新样式入口只有一个，顺序可审查。
- 导航和进度逻辑不依赖 FastAPI DTO。
- 未迁移页面业务或原型视觉系统。

---

# Sprint 3：冻结视觉系统迁移

## 目标

在真实 AppShell DOM、层级和样式入口中迁移 02 原型的 tokens、极光、玻璃、装饰层、公共动画和响应式基础。

## 修改文件

- `frontend/src/layouts/AppShell.vue`
- `frontend/src/styles/index.css`
- `frontend/src/styles/reset.css`
- `frontend/src/styles/base.css`
- `frontend/src/styles/navigation.css`
- `frontend/src/styles/layout.css`
- `frontend/src/components/shell/AppNavigation.vue`

## 新增文件

```text
frontend/src/styles/tokens.css
frontend/src/styles/typography.css
frontend/src/styles/glass.css
frontend/src/styles/animations.css
frontend/src/styles/aurora.css
frontend/src/styles/effects.css
frontend/src/styles/accessibility.css
frontend/src/components/effects/AuroraBackground.vue
frontend/src/components/effects/PetalField.vue
frontend/src/components/effects/DustField.vue
frontend/src/components/effects/AssistantOrb.vue
frontend/src/components/effects/TaskCompletionFx.vue
frontend/src/composables/useMotionPulse.ts
frontend/src/composables/useDecorativeField.ts
frontend/src/visual-system.test.ts
frontend/src/motion-cleanup.test.ts
```

## 实施范围

必须原值迁移：

- 所有 CSS 变量；
- `--grad-aurora`；
- `--ease-rise`；
- `--ease-decay`；
- body 背景；
- 字体 fallback；
- glass 背景、边框、阴影和 blur；
- 960、720、560 断点；
- `prefers-reduced-motion`。

必须保留：

- 四个 Aurora blob；
- 微网格；
- 花瓣 S 曲线与自旋；
- 光尘非对称闪烁；
- 噪点；
- Logo 摇摆；
- 通用 viewIn、msgIn、dotPulse、glowSpread 等 keyframes；
- 粒子汇聚、光球和光环能力。

## Fixture 使用

- 只使用 Shell fixture 验证视觉层。
- 动画测试使用固定随机种子。
- 不引入页面 fixture。

## 执行任务

- [ ] 建立 tokens 快照测试，逐项锁定原型变量和值。
- [ ] 将公共 keyframes 按所有权迁移到 animations/effects。
- [ ] 在 AppShell 中挂载 AuroraBackground 和 IconSprite。
- [ ] 实现花瓣与光尘组件的挂载、resize 和卸载清理。
- [ ] 实现 useMotionPulse，保持原型 20% 上升、80% 衰减语义。
- [ ] 实现 reduced-motion 的 CSS 与 RAF 双重降级。
- [ ] 检查 1080、960、720、560 宽度下背景和 Shell 层级。
- [ ] 运行 motion cleanup、完整测试、lint 和 build。

## 风险

- CSS 层叠顺序改变视觉。
- 全局 `.card`、`.live`、`.sub` 污染旧页面。
- 随机粒子导致测试不稳定。
- SVG gradient ID 重复。
- RAF、interval、resize listener 泄漏。
- backdrop-filter 降级时卡片可读性不足。

## 验收标准

- tokens 与 02 原型一致，无新增主题值。
- AppShell 中可真实观察背景、z-index、sticky 和 glass 效果。
- 动画卸载后无持续 RAF/interval。
- reduced-motion 生效。
- 不修改页面结构。
- 不修改后端。
- 不引入第三方动画库。

---

# Sprint 4：TodayView

## 目标

优先完成产品核心页面：用户状态感知、今日观察、微任务、任务进度、呼吸节律和今日节奏。先以 Demo Mode fixture 实现完整视觉和本地状态，不伪装真实后端闭环。

## 修改文件

- `frontend/src/layouts/AppShell.vue`
- `frontend/src/contracts/today.ts`
- `frontend/src/contracts/uiDataSource.ts`
- `frontend/src/styles/index.css`
- `frontend/src/styles/layout.css`

## 新增文件

```text
frontend/src/views/TodayView.vue
frontend/src/components/today/TodayHero.vue
frontend/src/components/today/TaskProgress.vue
frontend/src/components/today/ObservationCard.vue
frontend/src/components/today/DailyCheckCard.vue
frontend/src/components/today/MoodSelector.vue
frontend/src/components/today/AvailableTimeSelector.vue
frontend/src/components/today/TaskList.vue
frontend/src/components/today/TaskCard.vue
frontend/src/components/today/BreathCard.vue
frontend/src/components/today/RhythmTimeline.vue
frontend/src/composables/useDailyTasks.ts
frontend/src/composables/useBreathCycle.ts
frontend/src/data/adapters.ts
frontend/src/data/fixtures/today.fixture.ts
frontend/src/styles/today.css
frontend/src/today-view.test.ts
frontend/src/today-motion.test.ts
frontend/src/today-contract-validation.test.ts
```

## Today Contract

Contract 至少表达：

- 页面 loading/error/unavailable/demo 状态；
- 用户显示名和日期标签；
- Hero 状态摘要；
- 今日任务总数和完成数；
- Observation 摘要、指标和建议；
- 当前 mood 和 available time；
- 任务 ID、recommendation ID 可选值、展示字段和 UI 状态；
- 来源展示模型；
- 今日节奏；
- 是否允许真实提交任务动作。

Contract 不得包含后端 `RecommendationResponse`。

## Fixture 使用

`today.fixture.ts` 提供：

- 原型中的睡眠、用眼、情绪和考试周期；
- 三条今日建议；
- 三张任务卡；
- 推荐理由；
- 替换池；
- 今日节奏；
- 完成进度。

这些字段只在 Demo Mode 使用。

## API Contract Validation（离线）

本 Sprint 同步建立 Today 的最小契约验证链：

```text
Mock RecommendationResponse DTO
        ↓
纯 Today Adapter
        ↓
Today UI Contract
        ↓
TodayView
```

约束：

- Mock DTO 必须符合当前已读取的 `src/weilv/api/schemas.py` 与 `frontend/src/api/types.ts`，不得为了让页面通过测试补造后端字段；
- Adapter 只能做字段重命名、结构整理和 unavailable 映射，不得生成第二套推荐结果；
- 测试必须直接调用纯 Adapter 并挂载 TodayView，验证允许、blocked/help-seeking/no-safe-task 和缺失 UI 字段状态；
- 测试不得调用 `fetch`、真实 FastAPI、`ApiUiDataSource` 或任何 LLM/RAG 路径；
- 本 Sprint 不接入 Production DataSource，Today 运行时仍为 Demo fixture。

## 执行任务

- [ ] 为 Today Contract 和 fixture 一致性写测试。
- [ ] 为 Mock RecommendationResponse → Adapter → Today Contract → TodayView 写离线验证测试，并断言零网络调用。
- [ ] 实现 Hero、观察卡和检查卡静态结构。
- [ ] 实现 TaskCard 本地状态机：pending、started、done、partial、skipped。
- [ ] 实现 Demo Mode replace/restore，不发送网络请求。
- [ ] 实现任务进度与 docked progress 联动。
- [ ] 实现呼吸计时和文字同步。
- [ ] 实现完成粒子时序。
- [ ] 实现检查 CTA 滚动聚焦。
- [ ] 验证所有本地状态均标记为 demo/local。
- [ ] 运行 Today 测试、完整测试、lint 和 build。

## 风险

- 三张 fixture 任务误用同一个 recommendation ID。
- 本地完成状态被描述为已写入 Feedback/Memory。
- Mood 选择直接修改 fixture 常量或 props。
- 完成动画与 Vue DOM 更新不同步。
- 呼吸计时器切页后继续运行。

## 验收标准

- Today 页面与 02 原型结构一致。
- 三张任务卡覆盖全部原型状态。
- Demo Mode 不发真实推荐或反馈请求。
- Today Contract validation 覆盖当前真实 DTO 可表达字段和 unavailable 缺口，测试期间不启动或调用后端。
- 不显示“薇薇会记住”类真实持久化承诺，除非 API 确认成功。
- 每个动画实例可卸载。
- Today 完成后再进入 Assistant Sprint。

---

# Sprint 5：AssistantView

## 目标

在 Today 完成后迁移辅助问答页。Assistant 保持辅助角色，不持有全局任务真相，也不在前端实现 Agentic 决策。

## 修改文件

- `frontend/src/layouts/AppShell.vue`
- `frontend/src/contracts/assistant.ts`
- `frontend/src/contracts/uiDataSource.ts`
- `frontend/src/api/types.ts`，仅补充与现有后端 schema 一致的 Agentic response DTO 类型；不得添加客户端调用
- `frontend/src/data/adapters.ts`
- `frontend/src/styles/index.css`

## 新增文件

```text
frontend/src/views/AssistantView.vue
frontend/src/components/assistant/AssistantHero.vue
frontend/src/components/assistant/QuickPromptList.vue
frontend/src/components/assistant/ConversationLog.vue
frontend/src/components/assistant/UserMessage.vue
frontend/src/components/assistant/AgentPipeline.vue
frontend/src/components/assistant/PipelineRail.vue
frontend/src/components/assistant/PipelineStage.vue
frontend/src/components/assistant/ProblemAnalysisStage.vue
frontend/src/components/assistant/KnowledgeRetrievalStage.vue
frontend/src/components/assistant/KnowledgeChunk.vue
frontend/src/components/assistant/AnswerCard.vue
frontend/src/components/assistant/SuggestedMiniTask.vue
frontend/src/components/assistant/SafetyNotice.vue
frontend/src/components/assistant/EvidenceList.vue
frontend/src/components/assistant/ChatComposer.vue
frontend/src/composables/useAssistantFlow.ts
frontend/src/data/fixtures/assistant.fixture.ts
frontend/src/styles/assistant.css
frontend/src/assistant-view.test.ts
frontend/src/assistant-flow.test.ts
frontend/src/assistant-contract-validation.test.ts
```

## Assistant Contract

Contract 至少表达：

- 会话 loading/error/demo 状态；
- 用户消息；
- 管线阶段 pending/active/done/unavailable；
- 问题拆解显示项；
- 知识片段显示项；
- 最终回答；
- 建议任务；
- Safety 状态；
- 来源；
- 数据是否为真实 trace。

## Fixture 使用

Demo Mode fixture 提供：

- 三个快捷问题；
- Q1/Q2 拆解；
- chunk 文本和相关度；
- 最终回答和建议任务；
- 安全分流示例；
- 来源；
- 演示延迟。

Fixture 阶段必须显示 demo 标识，不得描述为真实后端执行轨迹。

## API Contract Validation（离线）

本 Sprint 建立 Assistant 的最小契约验证链：

```text
Mock AgenticRecommendationResponse DTO
        ↓
纯 Assistant Adapter
        ↓
Assistant UI Contract
        ↓
AssistantView
```

约束：

- DTO 类型只允许忠实描述当前 `AgenticRecommendationResponse` schema；本 Sprint 不增加 endpoint client，不发送请求；
- 验证最终任务、解释、Safety 状态、来源以及可公开 diagnostics 的映射；
- 后端未提供的实时阶段、chunk 内容、相关度和阶段耗时必须映射为 unavailable，不得由 Adapter 伪造；
- 测试不得调用 `fetch`、FastAPI、Agent Graph、RAG 或 `ApiUiDataSource`；
- AssistantView 只接收 Contract，测试中不得直接把 DTO 作为 props 或 composable 状态传入。

## 执行任务

- [ ] 为 Assistant Contract、管线状态和安全分支写测试。
- [ ] 为 Mock AgenticRecommendationResponse → Adapter → Assistant Contract → AssistantView 写离线验证测试，并断言零网络调用。
- [ ] 实现 Hero、快捷问题、消息列表和输入区。
- [ ] 实现结构化管线组件，不使用 innerHTML。
- [ ] 实现演示阶段计时，并在卸载时清理。
- [ ] 实现 SafetyNotice，输入只接受结构化状态。
- [ ] 禁止关键词正则决定 blocked/help-seeking。
- [ ] 实现最新消息滚动，避免抢夺用户已上滚位置。
- [ ] 运行 Assistant 测试、完整测试、lint 和 build。

## 风险

- 模拟阶段被误认为真实 Agent trace。
- 模型文本使用 v-html 引入 XSS。
- Assistant 推荐任务覆盖 Today 的正式任务状态。
- 多次提交产生乱序。
- 前端正则绕过 Safety。

## 验收标准

- 所有模型文本以普通文本或受控结构渲染。
- Safety 只接受后端/fixture 的结构化 status。
- Assistant 不成为应用默认页。
- Assistant 不管理全局任务进度。
- Demo 阶段和真实阶段有 Contract 标志区分。
- Production 无 trace 时显示通用 loading/unavailable，不展示模拟拆解或分数。
- Assistant Contract validation 证明真实 DTO 的缺口会显式降级为 unavailable，而不是由 fixture 或前端推演补齐。

---

# Sprint 6：ProfileView 与 Onboarding

## 目标

迁移画像、偏好、完成规律、记忆卡和五步引导；保持 Memory consent 和现有 Questionnaire 约束优先于原型演示文案。

## 修改文件

- `frontend/src/layouts/AppShell.vue`
- `frontend/src/contracts/profile.ts`
- `frontend/src/contracts/onboarding.ts`
- `frontend/src/contracts/uiDataSource.ts`
- `frontend/src/data/adapters.ts`
- `frontend/src/styles/index.css`

## 新增文件

```text
frontend/src/views/ProfileView.vue
frontend/src/components/profile/ProfileHeader.vue
frontend/src/components/profile/PreferenceCard.vue
frontend/src/components/profile/CompletionPatternCard.vue
frontend/src/components/profile/CompletionRing.vue
frontend/src/components/profile/MemoryCard.vue
frontend/src/components/profile/MemoryList.vue
frontend/src/components/profile/MemoryItem.vue
frontend/src/components/onboarding/OnboardingFlow.vue
frontend/src/components/onboarding/OnboardingProgress.vue
frontend/src/components/onboarding/OnboardingStep.vue
frontend/src/components/onboarding/ProfileGenerationStage.vue
frontend/src/composables/useOnboarding.ts
frontend/src/composables/useProfilePresentation.ts
frontend/src/data/fixtures/profile.fixture.ts
frontend/src/data/fixtures/onboarding.fixture.ts
frontend/src/styles/profile.css
frontend/src/styles/onboarding.css
frontend/src/profile-view.test.ts
frontend/src/onboarding-flow.test.ts
frontend/src/profile-contract-validation.test.ts
```

## Fixture 使用

Profile fixture：

- 时间偏好；
- 任务偏好；
- 92% 完成率；
- 四条记忆；
- consent 提示。

Onboarding fixture：

- 原型固定五步；
- 原型学段、睡眠、主要问题、任务时长和时段；
- 生成画像摘要。

## API Contract Validation（离线）

本 Sprint 建立 Profile/Onboarding 的最小契约验证链：

```text
Mock ProfileResponse / QuestionnaireResponse / QuestionnaireSchemaResponse DTO
        ↓
纯 Profile Adapter
        ↓
Profile / Onboarding UI Contract
        ↓
ProfileView / OnboardingFlow
```

约束：

- Mock DTO 必须与当前后端 schema 和既有前端 DTO 类型一致；只补齐类型差异，不接真实接口；
- 验证 `target_stage`、`memory_enabled`、问卷 schema、answers 和 completion state 的映射；
- Memory 列表、删除能力、偏好统计和完成率必须映射为 unavailable，不得从 fixture 混入 Production Contract；
- 测试覆盖 consent 缺失与 `memory_enabled=false`，不得触发 Memory 写入或删除；
- 测试不得调用 `fetch`、FastAPI、Memory、Questionnaire 写接口或 `ApiUiDataSource`。

## 执行任务

- [ ] 为 Profile/Onboarding Contract 写测试。
- [ ] 为 Mock Profile/Questionnaire DTO → Adapter → Contract → View 写离线验证测试，并断言零网络与零 Memory 写入。
- [ ] 实现四张画像卡和圆环动画。
- [ ] 实现记忆撕除的 Demo 本地状态。
- [ ] 实现五步引导、上一步、下一步、跳过和重播。
- [ ] 约束 Demo localStorage 只记录演示完成状态。
- [ ] 为 Production Mode 定义 memory consent 缺失状态。
- [ ] 为现 Questionnaire 七题与原型五步不一致定义 unavailable/contract mismatch 状态。
- [ ] 运行相关测试、完整测试、lint 和 build。

## 风险

- Demo 删除被表述为真实删除。
- localStorage 被当成服务端问卷状态。
- 原型选项直接提交现 Questionnaire 导致 422。
- 默认开启 Memory。
- 把不允许持久化的健康字段写入 Memory。

## 验收标准

- Demo 删除只影响 fixture 状态。
- Production 没有 Memory API 时不展示模拟记忆。
- Production 没有明确 consent 时 memory_enabled 保持 false。
- 不将原型 fixture 答案提交给现 Questionnaire API。
- 圆环、步骤、撕除动画均可清理和重播。
- 不修改 Memory 核心文件。
- Profile Contract validation 覆盖 consent、问卷状态和 unavailable 缺口，不展示模拟 Memory 数据。

---

# Sprint 7：WeeklyView

## 目标

最后迁移长期变化页面，保持其作为反馈闭环的结果展示，而不是先于 Today/反馈能力建设。

## 修改文件

- `frontend/src/layouts/AppShell.vue`
- `frontend/src/contracts/weekly.ts`
- `frontend/src/contracts/uiDataSource.ts`
- `frontend/src/styles/index.css`

## 新增文件

```text
frontend/src/views/WeeklyView.vue
frontend/src/components/weekly/WeeklyHeader.vue
frontend/src/components/weekly/WeeklyMinutesChart.vue
frontend/src/components/weekly/AdjustmentTimeline.vue
frontend/src/components/weekly/WeeklyInsightCard.vue
frontend/src/composables/useWeeklyChart.ts
frontend/src/data/fixtures/weekly.fixture.ts
frontend/src/styles/weekly.css
frontend/src/weekly-view.test.ts
frontend/src/weekly-chart.test.ts
```

## Fixture 使用

Weekly fixture 提供：

- 周一至周日分钟数；
- 调整轨迹；
- 完成、跳过和调整标签；
- 本周洞察。

## 执行任务

- [ ] 为 Weekly Contract、7 天/不足 7 天/空数据写测试。
- [ ] 记录 Weekly 当前无 Backend DTO，禁止为通过 Contract validation 伪造生产 DTO；B5 提供已批准 schema 后再补同类离线验证。
- [ ] 数据驱动实现 SVG path、area、point 和 label。
- [ ] 实现调整时间线和洞察卡。
- [ ] 确保重进页面不重复插入 SVG 节点。
- [ ] 为 Production unavailable 状态写测试。
- [ ] 运行 Weekly 测试、完整测试、lint 和 build。

## 风险

- 固定 SVG 坐标只适用于 fixture。
- 图表重复进入时重复节点。
- 模拟历史被误认为真实数据。
- 移动端标签溢出。

## 验收标准

- Demo Mode 与原型图表一致。
- Production 无接口时显示 unavailable，不显示 fixture。
- SVG 完全由 Vue template/computed 数据生成。
- Weekly 不直接查询 Elasticsearch。
- 页面开发顺序没有早于 Today、Assistant、Profile。
- Weekly 的 Production 缺口保持 unavailable，不以 fixture 冒充 API Contract validation。

---

# Sprint 8：DataSource 与现有 API 接入

## 目标

实现显式 Demo/Production 模式和两套 DataSource，只接入当前后端已经存在的能力。

## 修改文件

- `frontend/src/api/client.ts`
- `frontend/src/api/types.ts`
- `frontend/src/data/adapters.ts`
- `frontend/src/env.d.ts`
- `frontend/src/contracts/uiDataSource.ts`
- `frontend/src/composables/useRecommendationFlow.ts`
- `frontend/src/composables/useFeedbackFlow.ts`
- `frontend/src/composables/useQuestionnaire.ts`
- `frontend/src/composables/useUserProfile.ts`
- `frontend/src/views/TodayView.vue`
- `frontend/src/views/AssistantView.vue`
- `frontend/src/views/ProfileView.vue`
- `frontend/src/views/WeeklyView.vue`

## 新增文件

```text
frontend/src/config/uiMode.ts
frontend/src/data/createUiDataSource.ts
frontend/src/data/apiUiDataSource.ts
frontend/src/data/fixtureUiDataSource.ts
frontend/src/composables/useUiDataSource.ts
frontend/src/composables/useAgenticRecommendation.ts
frontend/.env.example
frontend/src/ui-mode.test.ts
frontend/src/data-adapters.test.ts
frontend/src/api/agentic-client.test.ts
```

## 现有 API 可接入范围

### Today

可接入：

- 单条 selected task；
- title、instruction、estimated minutes；
- explanation；
- sources/context_sources；
- personalization 是否使用；
- blocked/help-seeking/no-safe-task。

不可接入：

- 三任务日清单；
- 睡眠、用眼、心情统计；
- 今日节奏；
- 替换/恢复；
- 总体日进度。

### Assistant

可接入：

- Agentic 最终状态；
- 最终任务和解释；
- sources/context_sources；
- Safety 状态；
- 可公开的粗粒度 diagnostics。

不可接入：

- 实时阶段；
- factors 正文；
- chunk content；
- relevance score；
- 阶段耗时。

### Profile/Onboarding

可接入：

- target_stage；
- memory_enabled；
- questionnaire schema；
- questionnaire state/answers/completion_state。

不可接入：

- Memory 列表与删除；
- 时间/任务偏好统计；
- 完成率。

### Weekly

- 当前无公开查询接口；Production 必须 unavailable。

## Feedback 门禁

现 Feedback API 要求 completion_status、usefulness、difficulty、reason。原型任务按钮只提供 completion status。

在产品或接口决策完成前：

- Demo Mode 保留完整原型按钮；
- Production 点击完成只进入本地 pending-feedback 状态，不能显示已同步；
- 不调用 Feedback API；
- 不自动填 `neutral`、`suitable` 或空 reason 来伪造完整反馈。

## 执行任务

- [ ] 为环境变量缺失、非法、demo、production 四种情况写测试。
- [ ] 实现严格 uiMode 解析，不提供隐式 demo 默认值。
- [ ] 实现 FixtureUiDataSource，返回全部 Contract。
- [ ] 实现 ApiUiDataSource，只映射现有 API 字段。
- [ ] 扩展并完成 Sprint 4～6 已建立的纯 adapters，接入 ApiUiDataSource，并验证 View 不接触 DTO。
- [ ] 为 API failure 写测试，确认不会调用 fixture provider。
- [ ] 增加 Agentic endpoint 客户端和 DTO 类型。
- [ ] 将后端不可提供的数据映射为 unavailable，而不是演示值。
- [ ] 保持现有错误净化和 secret boundary。
- [ ] 运行完整测试、lint 和 build。

## 风险

- API 失败隐式调用 fixture。
- View 导入 `api/types.ts`。
- 公开 diagnostics 泄露内部 ID。
- Production 构建未配置模式。
- 普通 Recommendation 与 Agentic endpoint 混用。
- Feedback 提交虚假默认值。

## 验收标准

- 所有 View 只导入 contracts。
- Fixture 和 API 实现同一个 UiDataSource。
- Demo 只 fixture，Production 只 API。
- API 失败只显示错误/重试。
- Production 无数据时显示 unavailable。
- 不显示 Memory ID、rule ID、guard reason code。
- 不修改 Python 核心文件。

---

## 4. Backend 扩展总原则

以下规则适用于所有 Backend Ticket，优先级高于单个接口需求。

### 允许

新增后端接口只能：

1. 聚合已有数据；
2. 暴露已有状态；
3. 提供查询适配层；
4. 调用现有、已冻结的公开函数；
5. 对返回字段做最小、可审计的展示 DTO 转换；
6. 对用户数据继续执行现有所有权隔离和 consent 检查。

### 禁止

新增后端接口不得：

1. 新增第二套推荐逻辑；
2. 新增第二套 Memory 写入流程；
3. 绕过 Safety 规则；
4. 建立前端专用 Prompt 生成链；
5. 为 UI 重新调用 LLM 生成数据；
6. 修改任务白名单、排序权重或个性化 delta；
7. 将 fixture 写入 Elasticsearch；
8. 为凑齐 UI 字段推断用户健康状态；
9. 向前端暴露 embedding、raw query、raw chat、内部 memory retrieval_text 或审计密钥；
10. 让前端直接查询 ES。

### 后端变更边界

未经单独授权，不得修改：

- `src/weilv/basic_rag.py`
- `src/weilv/personal_rag.py`
- `src/weilv/agentic_rag.py`
- `src/weilv/agent_graph.py`
- `src/weilv/user_memory.py`
- `src/weilv/personal_memory_retrieval.py`
- `src/weilv/feedback_loop.py`
- `src/weilv/safety_rules.py`
- `src/weilv/output_guard.py`

允许候选修改仅限：

- `src/weilv/api/schemas.py`
- `src/weilv/api/app.py`
- 新增 `src/weilv/api/*_queries.py` 或展示适配模块；
- 新增 API 单元/集成测试。

---

## 5. Backend Interface Tickets

这些 Ticket 不属于前端 Sprint 的隐含工作。没有单独授权时，编码 Agent 必须保留 Production unavailable 状态。

### Backend Ticket B1：今日面板查询

需要：

- 用户今日状态摘要；
- 睡眠、用眼、情绪；
- 三条独立任务及各自 recommendation ID；
- 今日任务状态和进度；
- 今日节奏时间；
- 推荐理由和来源。

允许候选文件：

- Modify: `src/weilv/api/schemas.py`
- Modify: `src/weilv/api/app.py`
- Create: `src/weilv/api/today_queries.py`
- Test: `tests/test_today_api.py`
- Test: `tests/integration/test_today_api_integration.py`

关键门禁：三任务如何产生不是查询适配问题，会影响推荐语义。未形成单独产品规格前，不得通过重复调用 RAG 或构造不同 query 来凑齐三条任务。

### Backend Ticket B2：任务动作事件

需要记录：

- started；
- completed；
- partially_completed；
- skipped；
- replaced；
- restored。

动作事件不等于完整 Feedback。

允许候选文件：

- Modify: `src/weilv/api/schemas.py`
- Modify: `src/weilv/api/app.py`
- Create: `src/weilv/api/task_events.py`
- Test: `tests/test_task_events_api.py`

约束：

- 不修改 `feedback_loop.py`；
- 不自动产生 task_feedback Memory；
- usefulness/difficulty 只能由用户明确提交；
- 不把本地 UI 状态写成个性化结论。

### Backend Ticket B3：Agentic 可观察过程

需要：

- 阶段开始/完成；
- 拆解问题正文；
- 可展示知识片段；
- 来源和可展示相关度；
- Safety 终止；
- 最终回答。

当前约束下的结论：

- 现有最终响应只能支持最终结果；
- 真实实时 trace 需要 Agentic 可观察 seam；
- 未授权修改冻结 Agentic 核心前，不得实现前端专用伪 trace endpoint；
- 不允许为 UI 再调用一次 LLM 生成拆解或片段说明。

未授权时 Production 方案：显示通用“理解问题/检索/生成”等待状态，但不显示虚构的拆解正文、chunk 内容、分数或实际阶段完成事件。

### Backend Ticket B4：Memory 查询与删除适配

需要：

- 用户 Memory 列表；
- 用户友好摘要；
- 删除操作；
- 所有权隔离；
- 删除结果。

允许候选文件：

- Modify: `src/weilv/api/schemas.py`
- Modify: `src/weilv/api/app.py`
- Create: `src/weilv/api/memory_queries.py`
- Test: `tests/test_memory_api.py`
- Test: `tests/integration/test_memory_api_integration.py`

约束：

- 不修改 `user_memory.py`；
- 删除适配调用现有 `forget_memory()`；
- 不返回 embedding、retrieval_text、raw query 或内部审计字段；
- 不建立第二套 Memory 写入路径。

### Backend Ticket B5：周度只读聚合

需要：

- 日期范围；
- 每日完成分钟数；
- 任务动作历史；
- 推荐调整轨迹；
- 完成/跳过/替换统计；
- 可审计的周度洞察来源。

允许候选文件：

- Modify: `src/weilv/api/schemas.py`
- Modify: `src/weilv/api/app.py`
- Create: `src/weilv/api/weekly_queries.py`
- Test: `tests/test_weekly_api.py`
- Test: `tests/integration/test_weekly_api_integration.py`

约束：

- 只读聚合 interaction logs 和正式任务元数据；
- 不修改 Feedback Loop；
- 不调用 LLM 为 UI 生成洞察；
- 洞察若无确定性来源，则返回统计事实而非原型固定结论。

### Backend/UX Ticket B6：Onboarding 与 Memory consent

必须先明确：

- 五步原型如何承载现七题 Questionnaire；
- 新用户在哪里明确设置 `memory_enabled`；
- 原型睡眠和主要问题字段是否持久化；
- 禁止持久化字段如何处理；
- 跳过引导是否保持 Memory 关闭。

未明确前：

- Demo 使用固定五步 fixture；
- Production 使用现 Questionnaire schema；
- Memory 默认 false；
- 不提交 fixture 答案；
- 不添加未经批准的额外 consent UI。

---

## Visual Regression Gate

最终验收必须存在可重复执行的视觉对比机制。工具不在本计划中强制指定，但所选机制必须能够在固定浏览器、固定 viewport、固定缩放、固定字体加载完成状态和确定性 Demo fixture 下重复生成基准图与候选图，并保留差异结果。单次人工目测、临时截图或“看起来一致”不构成通过。

### 必测 viewport

- 桌面：1080px；
- 平板：960px；
- 小屏：720px；
- 手机：560px。

viewport 高度由执行时固定并写入 release checklist；同一基线与候选对比不得改变高度、设备像素比或浏览器版本。

### 必测页面

- Today 初始状态；
- Assistant 初始状态；
- Profile 初始状态；
- Weekly 初始状态；
- Onboarding Step 1。

### 必测状态

- 四页面导航切换后的稳定状态；
- Task 完成动画的关键帧或可重复时序检查点；
- Safety 状态；
- Memory consent 状态；
- `prefers-reduced-motion: reduce` 状态。

### 执行规则

- 02 原型是唯一基准来源；不得用其他 prototype、重新设计稿或主观修图替换基准；
- 动画截图必须使用固定 seed、固定时间点或等价的确定性控制，不能靠随机等待；
- 基准更新必须记录原因、受影响 selector 和人工批准，不得以“消除差异”为由自动覆盖；
- 每个页面 Sprint 可先产生临时快照，Sprint 10 必须运行完整矩阵并保存可审查的差异产物；
- 允许按仓库现有测试能力选择实现工具，不得只为此门禁引入未经批准的 UI 框架、状态库或路由库。

---

# Sprint 9：正式 Integration Switch

## 目标

把 `App.vue` 正式切换到 Contract/DataSource 驱动的四页面应用，完成显式 DataSource 模式切换与集成测试。保留旧组件和旧 CSS 源码作为可回滚 backup，本 Sprint 不做大规模删除或清理。

## 前置门禁

每个缺失接口必须满足以下之一：

1. 已按独立 Backend Ticket 实现并测试；
2. 产品批准对应模块仅在 Demo Mode 展示；
3. 产品批准 Production Mode 使用 unavailable 状态。

不得通过硬编码绕过门禁。

此外，Sprint 4～6 的离线 API Contract Validation 必须通过；否则不得开始正式切换。

## 修改文件

- `frontend/src/App.vue`
- `frontend/src/main.ts`
- `frontend/src/data/createUiDataSource.ts`
- `frontend/src/data/apiUiDataSource.ts`
- `frontend/src/data/fixtureUiDataSource.ts`
- `frontend/src/composables/useUiDataSource.ts`
- `frontend/src/views/TodayView.vue`
- `frontend/src/views/AssistantView.vue`
- `frontend/src/views/ProfileView.vue`
- `frontend/src/views/WeeklyView.vue`
- `frontend/src/App.test.ts`
- `frontend/src/recommendation-flow.test.ts`
- `frontend/src/profile-flow.test.ts`
- `frontend/src/questionnaire-flow.test.ts`
- `frontend/src/feedback-flow.test.ts`
- `frontend/src/secret-boundary.test.ts`，仅在扫描路径需要扩展时
- `frontend/vite.config.ts`，仅在测试配置确有需要时

## 新增文件

```text
frontend/src/ui-integration.test.ts
frontend/src/ui-data-mode.test.ts
frontend/src/production-no-fixture.test.ts
docs/ui-migration/records/sprint-09.md
```

## 执行任务

- [ ] 先写 AppShell 正式切换后的四页面集成测试。
- [ ] App.vue 切换为 Contract/DataSource 驱动的四 View。
- [ ] 默认页保持 Today；Assistant 不持有或覆盖 Today 主任务状态。
- [ ] 显式接入 Demo fixture-only 与 Production API-only 模式。
- [ ] 增加 Production 不使用 fixture 的测试。
- [ ] 增加 API failure 不 fallback fixture 的测试。
- [ ] 保留全部旧功能组件与旧 `style.css` 源码作为 source-level rollback backup。
- [ ] main.ts 保持单一样式入口。
- [ ] 更新原流程测试，使其通过新 UI 操作但继续验证原 HTTP 契约。
- [ ] 验证旧源码不进入新运行路径；不得添加运行时“新 UI 失败后切回旧 UI”的逻辑。
- [ ] 运行集成测试、原流程测试、完整前端测试、lint 和 build。

## 风险

- 旧功能在视觉切换时丢失。
- Demo 环境变量进入 Production。
- 新旧 CSS 重复加载。
- 旧流程测试被删除而不是迁移。
- Production unavailable 被 fixture 掩盖。
- “保留旧代码”被误实现为运行时 fallback，制造第二条应用路径。
- 切换同时清理旧代码导致 commit 过大且难以回滚。

## 验收标准

- `App.vue` 已正式挂载四 View，默认页是 Today。
- Today、Assistant、Profile、Weekly 的导航与 Contract 数据链集成测试通过。
- Demo/Production 模式显式，Production API 失败只显示错误状态。
- View 不导入 `api/types.ts`，UI Contract 仍是页面唯一数据依赖。
- 旧组件与旧 CSS 文件仍保留在仓库，但不进入新运行路径或生产 bundle 的主动入口。
- 不存在任何运行时旧 UI fallback 或 fixture fallback。
- 本 Sprint 不删除旧组件，不大规模清理旧 CSS。
- 原 HTTP 契约测试、完整前端测试、lint 和 build 通过。
- 未修改任何冻结 AI 核心文件。

---

# Sprint 10：Cleanup & Release

## 目标

在 Sprint 9 正式切换稳定并通过人工检查点后，删除确认无引用的旧组件、清理旧 CSS，运行完整 Visual Regression Gate 和发布检查。清理与发布单独提交，避免与正式切换混在一次 commit。

## 修改文件

- `frontend/src/styles/index.css`
- `frontend/src/style.css`，仅在确认不再作为兼容入口后清理或删除
- `frontend/src/App.test.ts`
- `frontend/src/secret-boundary.test.ts`，仅在扫描路径需要扩展时
- `frontend/vite.config.ts`，仅在可重复视觉对比机制确有测试配置需要时
- Sprint 9 后仍引用旧组件的相关测试，按新 UI 入口迁移，不得删除测试意图

## 新增文件

```text
frontend/src/accessibility.test.ts
docs/ui-migration/records/sprint-10.md
docs/ui-migration/release-checklist.md
```

视觉回归脚本、配置、基准与差异产物的具体文件名由所选机制决定；它们必须位于仓库可识别位置并写入 release checklist，不允许只存在于个人临时目录。

## 候选删除文件

以下仅是基于当前旧入口的审查候选，不是预授权删除清单：

- `frontend/src/components/ColdStartQuestionnaire.vue`
- `frontend/src/components/EvidenceList.vue`
- `frontend/src/components/FeedbackForm.vue`
- `frontend/src/components/FeedbackResult.vue`
- `frontend/src/components/RecommendationForm.vue`
- `frontend/src/components/RecommendationResult.vue`
- `frontend/src/components/SafetyResult.vue`
- `frontend/src/components/ServiceStatus.vue`
- `frontend/src/components/UserProfileSettings.vue`

每个文件只有在 `rg` 引用检查、TypeScript/build、相关流程测试和生产入口检查都证明无引用后才可删除。仍承担 API、Feedback、Safety 或 Questionnaire 行为的文件必须保留，或先由等价新路径覆盖并通过对应测试。不得批量删除整个目录。

## 执行任务

- [ ] 再次读取 02 原型所有待验收区域，并完成 Sprint 10 迁移记录。
- [ ] 为每个旧组件和旧 CSS selector 建立引用清单，逐项确认保留、迁移或删除。
- [ ] 删除仅限确认无引用且已被新路径完整覆盖的旧组件。
- [ ] 清理旧 CSS；每条删除规则必须能追溯到无引用 selector 或已迁移规则。
- [ ] 增加 reduced-motion、keyboard focus、timer/RAF/observer/listener cleanup 测试。
- [ ] 建立并运行可重复的 Visual Regression Gate 完整矩阵。
- [ ] 对差异逐项记录对应 HTML selector；未经批准不得更新基准。
- [ ] 运行完整前端测试、lint、build 和 secret boundary。
- [ ] 完成 release checklist，并记录模式配置、接口缺口、unavailable 状态与后端 Ticket 状态。
- [ ] 将 Cleanup & Release 作为独立于 Sprint 9 的单一职责 commit。

## 风险

- 静态引用检查漏掉动态使用，导致旧功能被误删。
- 旧 CSS selector 与新组件共享，清理后产生视觉回归。
- 通过自动更新截图掩盖真实视觉漂移。
- 随机粒子、动画时序或字体加载导致视觉测试不稳定。
- 为通过发布门禁临时引入未经批准依赖。
- Cleanup commit 混入业务或后端逻辑修改。

## 验收标准

### 工程

- `npm test` 全部通过。
- `npm run lint` 通过。
- `npm run build` 成功。
- 无 TypeScript error。
- 无悬空 timer、RAF、IntersectionObserver 或 event listener。
- 无模型密钥或后端内部字段进入前端。
- 删除的每个旧文件都有无引用证据和替代路径测试；仍被引用的旧文件未删除。
- Sprint 9 与 Sprint 10 是两个独立、可审查、可回滚的提交。

### 架构

- View 不导入 `api/types.ts`。
- UI Contract 是页面唯一数据依赖。
- Demo/Production 模式显式。
- API 失败不 fallback fixture。
- 不存在第二套推荐、Memory 或 Feedback 逻辑。
- 未引入 Pinia、Router、组件库或动画库。

### 产品顺序

- 默认页为 Today。
- Today 承载主任务和进度。
- Assistant 不覆盖 Today 任务状态。
- Profile 展示长期个性化信息。
- Weekly 只展示已有历史聚合。

### 视觉

- 02 原型是唯一对比基线。
- 四页面、Onboarding、导航、背景、任务状态和核心动效一致。
- 1080、960、720、560 宽度无页面级横向溢出。
- reduced-motion 保持内容可读和交互可用。
- 可重复视觉对比机制覆盖规定的五个页面入口与五类状态，基准、候选和差异产物可审查。

### 数据

- Demo Mode 只 fixture，不写后端。
- Production Mode 只 API，不展示模拟数据。
- Production Safety 状态只来自后端；Demo Safety 状态只来自确定性 fixture；前端不得自行判定。
- 每个真实任务使用自身 recommendation ID。
- 没有 consent 时 Memory 保持关闭。
- 不伪造 Feedback 字段。
- 不可用模块显示明确状态。
- release checklist 完整记录 Production 接口缺口，未用 fixture 或前端生成内容掩盖。

---

## 6. Fixture 使用总表

| 模块 | Demo Mode Fixture | Production Mode | 移除/缩减条件 |
|---|---|---|---|
| Shell | 用户名、日期、进度、Toast | API/本地日期；失败状态 | Today 面板接口完整后 |
| Today Hero | 睡眠、考试周期、状态总结 | 当前大部分 unavailable | B1 |
| Observation | 睡眠、用眼、情绪、建议 | unavailable | B1 |
| 三任务清单 | 三任务与独立状态 | 当前最多显示单条真实推荐 | B1 |
| 替换池 | 原型替代任务 | unavailable | B1/B2 |
| 今日节奏 | 三个提醒时间 | unavailable | B1 |
| Assistant stages | 拆解、chunk、分数、演示延迟 | 通用 loading + 最终真实结果 | B3 |
| Assistant final | fixture 最终回答 | 现 Agentic 最终响应 | Sprint 8 可缩减 |
| Profile stats | 时间偏好、任务偏好、完成率 | unavailable | B4/B5 |
| Memory list | 四条记忆与本地撕除 | unavailable | B4 |
| Onboarding | 原型固定五步 | 现 Profile/Questionnaire，缺口显式 | B6 |
| Weekly | 图表、轨迹、洞察 | unavailable | B5 |

---

## 7. 每个 Sprint 的统一执行纪律

每个 Sprint 按以下顺序执行：

- [ ] 读取本计划中当前 Sprint 的全部内容。
- [ ] 读取《02-sakura-spring Vue 工程化迁移评估报告》对应章节；无法读取则停止，不得猜测。
- [ ] 读取 `ui-prototypes/02-sakura-spring.html` 对应 HTML、CSS 和脚本区域，不读取其他 prototype 作为设计输入。
- [ ] 在 `docs/ui-migration/records/sprint-XX.md` 按固定六字段记录每个迁移对象，并在编码前填完前五项。
- [ ] 检查工作树，保留用户已有修改。
- [ ] 写该 Sprint 的失败测试。
- [ ] 运行目标测试并确认失败原因正确。
- [ ] 实现满足 Contract 的最小改动。
- [ ] 运行目标测试。
- [ ] 运行完整 `npm test`。
- [ ] 运行 `npm run lint`。
- [ ] 运行 `npm run build`。
- [ ] 检查未修改冻结后端文件。
- [ ] 检查 View 未导入 FastAPI DTO。
- [ ] 检查 Demo/Production 未发生隐式降级。
- [ ] 检查没有根据截图重设计、补充视觉或改变原型交互逻辑。
- [ ] 在迁移记录的 `Test coverage` 中填写实际命令、结果和尚未覆盖项。
- [ ] 提交单一职责 commit。
- [ ] 进入下一 Sprint 前设置人工验收点。

## 8. 最终 Definition of Done

只有同时满足以下条件，UI 迁移才可称为完成：

1. 02 原型四页面和五步 Onboarding 完成 Vue 结构迁移。
2. 极光、花瓣、光尘、噪点、玻璃和核心动效未被削减。
3. Contract/DataSource seam 生效，View 不依赖后端 DTO。
4. Today、Assistant、Profile 的 Mock Backend DTO → Adapter → UI Contract → View 离线验证通过，且验证过程零真实网络调用。
5. Demo 和 Production 严格隔离。
6. API 失败不展示 fixture。
7. Today 是默认页和产品中心。
8. Assistant 不持有主任务状态或复制 Agentic 逻辑。
9. Profile 不绕过 consent，不模拟真实 Memory。
10. Weekly 不伪造用户历史；无 Backend DTO 时保持 unavailable。
11. Basic RAG、Personal RAG、Agentic RAG、Agent Graph、Memory、Feedback Loop、Safety、Output Guard 和协同排序核心文件零修改。
12. 无未经批准的新依赖。
13. Sprint 1～10 均有完整迁移记录，且 selector、原始行为、组件、Contract 和测试可追溯。
14. Sprint 9 正式切换与 Sprint 10 清理发布分属两个独立提交，切换阶段未大规模删除旧代码。
15. 可重复视觉对比覆盖 1080、960、720、560，以及规定页面、状态和 reduced-motion。
16. 全部测试、lint、build、secret boundary 和视觉回归通过。
