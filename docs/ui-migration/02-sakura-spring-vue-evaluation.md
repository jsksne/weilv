# 《02-sakura-spring Vue 工程化迁移评估报告》

> 评估对象：`ui-prototypes/02-sakura-spring.html`

> 迁移目标：当前 Vue 3 + TypeScript + Composition API 前端工程

> 报告用途：作为微律 UI 迁移唯一视觉基线的工程评估依据。

---

# 一、评估结论

## 总体判断

`02-sakura-spring.html` 可以迁移至现有 Vue 3 工程。

但必须严格区分：

1. 视觉与交互迁移；
2. 后端真实数据接入。

二者不能混为一谈。

---

## 可直接迁移部分

以下内容具备明确迁移路径：

- 四个主视图：
  - 今日
  - 问问薇薇
  - 我的画像
  - 周度变化
- 首次使用五步引导；
- 春日极光视觉系统：
  - Aurora blobs；
  - 背景网格；
  - 花瓣粒子；
  - 光尘；
  - 噪点纹理。
- 玻璃质感系统；
- CSS 动画系统；
- 页面切换动画；
- 任务完成动画；
- AI Orb 动效；
- 呼吸节律动画。

---

## 暂不能真实闭环部分

当前后端能力不足以支撑：

- 今日三任务系统；
- 睡眠/用眼/情绪状态展示；
- 实时 Agentic Pipeline；
- Memory 列表展示；
- 周度统计；
- 推荐调整轨迹。

这些必须：

1. 使用明确 fixture；
2. 或等待新增 API；
3. 不允许前端伪造真实数据。

---

# 二、唯一视觉基线

## 强制规则

唯一视觉来源：`ui-prototypes/02-sakura-spring.html`

禁止：

- 使用其他 prototype；
- 使用旧版设计；
- 自行重新设计；
- 调整颜色体系；
- 修改动画语言。

---

# 三、原型结构分析

原型为单 HTML SPA，包含：

```text
AppShell
├── AuroraBackground
├── Navigation
├── TodayView
├── AssistantView
├── ProfileView
├── WeeklyView
└── OnboardingFlow
```

---

# 四、Vue 迁移原则

## 核心原则

```text
HTML Prototype
        ↓
Vue Components
        ↓
UI ViewModel
        ↓
API Adapter
```

禁止：

```text
Vue Component
        ↓
直接绑定 FastAPI DTO
```

原因：原型需要的数据结构（三任务、周统计、Memory 展示）与当前 API 不一致，必须增加 ViewModel 层隔离。

---

# 五、推荐目录结构

```text
frontend/src/
├── api/
│   ├── client.ts
│   └── types.ts
├── models/
│   └── ui.ts
├── data/
│   ├── adapters.ts
│   ├── fixtures/
│   └── datasource.ts
├── layouts/
│   └── AppShell.vue
├── views/
│   ├── TodayView.vue
│   ├── AssistantView.vue
│   ├── ProfileView.vue
│   └── WeeklyView.vue
├── components/
├── composables/
└── styles/
```

---

# 六、数据模式设计

必须存在：

```text
UiDataSource
├── FixtureUiDataSource
└── ApiUiDataSource
```

## Fixture 模式

用途：视觉开发、自动测试、Demo。

禁止：写入后端；冒充真实用户数据。

## API 模式

用途：生产。

规则：

- 只展示真实返回；
- API 失败显示错误；
- 不允许自动 fallback 到 fixture。

---

# 七、组件拆解原则

不要：每个 div 一个组件。

应该：按功能拆分。

例如：`TaskCard.vue` 合理，因为有状态、有动画、有生命周期；而 `SectionTitle.vue` 暂时没有必要。

---

# 八、CSS 迁移原则

必须保留：

- CSS variables；
- 渐变；
- blur；
- shadow；
- animation curve。

特别：`--ease-rise`、`--ease-decay` 禁止替换。

必须拆分：

```text
styles/
├── tokens.css
├── glass.css
├── animations.css
├── aurora.css
├── effects.css
├── navigation.css
├── today.css
├── assistant.css
├── profile.css
└── weekly.css
```

---

# 九、动画迁移原则

CSS 保留，包括：

- 极光漂移；
- 光尘闪烁；
- 花瓣旋转；
- Logo 动画；
- Orb 呼吸；
- hover；
- focus；
- transition。

Vue 管理，适合：

- 页面切换；
- Onboarding 步骤；
- Task 状态变化；
- Toast；
- 消息插入。

RAF 必须生命周期管理：原型中的 `requestAnimationFrame`、`setInterval`、`setTimeout`、listener，迁移后必须使用 `onMounted()` / `onUnmounted()` 清理。

---

# 十、页面迁移评估

## 1. TodayView

对应：`TodayView.vue`

包含：Hero 区域、今日观察、心情选择、可用时间、三任务列表、呼吸训练、今日节奏。

### 当前支持情况

| 功能 | 状态 |
|-|-|
| 单条推荐任务 | 已支持 |
| 推荐解释 | 已支持 |
| 来源展示 | 已支持 |
| Feedback | 已支持 |
| 三任务系统 | 不支持 |
| 今日状态摘要 | 不支持 |
| 睡眠数据 | 不支持 |
| 用眼数据 | 不支持 |
| 情绪历史 | 不支持 |
| 节奏时间轴 | 不支持 |

### 迁移规则

第一阶段：使用 `TodayViewModel` + fixture 完成视觉迁移。

第二阶段：接入 `Today API` 后再切换。

禁止：

- 前端生成三个真实任务；
- 共用一个 `recommendation_id`；
- 假装任务来自后端。

---

## 2. AssistantView

对应：`AssistantView.vue`

包含：AI Orb、快捷问题、对话记录、Agent Pipeline、知识来源、安全提示。

### 当前后端支持

支持：最终回答、推荐任务、sources、context_sources、safety 状态。

### 不支持

不支持：实时 Agent 阶段、问题拆解过程、chunk 内容、rerank 分数。

### 强制规则

禁止：

```text
前端动画:
正在分析...
正在检索...
正在生成...
然后让用户认为是真实 Agent trace。
```

正确方式：

```text
请求中
   ↓
loading
   ↓
最终结果
```

或者等待未来的 Agent Event Stream API。

---

## 3. ProfileView

对应：`ProfileView.vue`

包含：用户画像、偏好、完成率、Memory。

### 当前支持

已有：`target_stage`、`memory_enabled`、`questionnaire`。

### 缺失

没有：Memory 列表、Memory 删除、完成率统计、时间偏好、任务偏好。

### 规则

没有接口时显示「暂无数据」或 Demo 状态。

禁止使用 fixture 冒充真实用户画像。

---

## 4. WeeklyView

对应：`WeeklyView.vue`

包含：周趋势、完成分钟、推荐调整、洞察。

当前没有：历史查询、周统计、趋势数据、洞察接口。

因此：

- 第一阶段：fixture only。
- 第二阶段：等待 Weekly Query API。

---

# 十一、后端接口缺口

以下接口必须单独设计，禁止前端自行补。

## B1 今日面板接口

需要：`GET /today`

返回：

```json
{
  "sleep": {},
  "emotion": {},
  "eye_strain": {},
  "tasks": [
    {
      "recommendation_id": "",
      "task": {},
      "status": ""
    }
  ]
}
```

约束：不能改变 RAG、排序、推荐逻辑。

## B2 任务动作接口

原因：任务状态（`started`、`completed`、`partial`、`skipped`、`replaced`、`restored`）不等同于 Feedback。

不能：点击完成按钮 → 自动生成 `usefulness` / `difficulty`。

## B3 Agent Trace 接口

需要支持：`analysis_started`、`retrieval_started`、`generation_started`、`completed`。

否则前端只能展示 loading。

## B4 Memory 接口

需要：`GET /memories`、`DELETE /memory/{id}`

要求：不能返回 embedding、retrieval text、内部 ID。

## B5 Weekly 接口

需要返回：历史任务、完成情况、时间趋势、洞察。

## B6 Onboarding 接口

需要明确：原型为 5 步，当前为 7 题动态问卷，必须决定二者如何映射。

---

# 十二、禁止修改的核心文件

以下文件：

- `src/weilv/basic_rag.py`
- `src/weilv/personal_rag.py`
- `src/weilv/agentic_rag.py`
- `src/weilv/agent_graph.py`
- `src/weilv/user_memory.py`
- `src/weilv/personal_memory_retrieval.py`
- `src/weilv/feedback_loop.py`
- `src/weilv/safety_rules.py`
- `src/weilv/output_guard.py`
- `src/weilv/collaborative_ranking.py`

禁止：修改算法、修改排序、修改安全规则、修改 Memory 逻辑、修改 Feedback 逻辑。

任何新增必须通过 HTTP Adapter Layer 解决。

---

# 十三、Sprint 实施顺序

## Sprint 0

目标：冻结依据。

完成：原型确认、评估报告、API 能力清点。

不写代码。

## Sprint 1

目标：建立工程骨架。

允许新增：`layouts/`、`views/`、`models/`、`data/`、`styles/`，允许新增 `AppShell.vue`。

禁止：UI 迁移、API 迁移、动画、新数据。

验收：原 46 测试通过、build 通过、App 逻辑未变化。

## Sprint 2

目标：迁移视觉系统。

完成：tokens、glass、aurora、effects、animations。

禁止切换正式入口。

## Sprint 3

目标：AppShell。

完成：导航、Tab、Toast、全局背景。

## Sprint 4

目标：Today。

使用 fixture，不接 Recommendation API。

## Sprint 5

目标：Assistant。

使用 fixture pipeline，真实 API 只接最终结果。

## Sprint 6

目标：Profile + Onboarding。

使用 fixture，等待 Memory 接口。

## Sprint 7

目标：Weekly。

使用 fixture，等待统计接口。

## Sprint 8

目标：真实 API 接入。

原则：

```text
DTO
 ↓
Adapter
 ↓
ViewModel
 ↓
Component
```

禁止 Component 直接使用 DTO。

## Sprint 9

正式切换。

要求：全测试通过、build 通过、lint 通过、无核心文件修改、无 fixture 进入生产。

---

# 十四、最终验收标准

## 工程

必须：

```bash
npm test
npm run lint
npm run build
```

全部通过。

## 数据

必须：

- API 失败不显示 fixture；
- fixture 不写后端；
- 不伪造 Agent 过程；
- 不默认开启 Memory；
- 不自动生成 Feedback 字段。

## 视觉

必须保持：颜色、字体、动画、布局、响应式。

唯一来源：`02-sakura-spring.html`。

---

# 最终结论

`02-sakura-spring` 具备迁移条件。

推荐路线：

```text
冻结视觉
   ↓
建立 Vue 骨架
   ↓
迁移视觉系统
   ↓
fixture 驱动页面
   ↓
逐步接入真实 API
   ↓
补充后端查询接口
   ↓
正式生产切换
```

迁移过程中优先保证：

1. 视觉一致性；
2. 数据真实性；
3. AI 核心逻辑不被破坏；
4. 每一步可回滚。
