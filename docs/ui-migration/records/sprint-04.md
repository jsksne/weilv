# Sprint 4 Migration Record — Today 页面工程化迁移

冻结基线：`ui-prototypes/02-sakura-spring.html`（唯一视觉与交互验收基准）
本记录在实现前建立（Prototype Reading Rule），验收时补齐测试与视觉验证结果。

范围（本 Sprint Prompt 约束）：仅 Today UI / Today local interaction state /
Today fixture / Today Contract / Today visual fidelity。
不做 Assistant / Profile / Weekly / Production API wiring / Backend extensions。
v3 计划中 Sprint 4 的 Mock DTO → Adapter 离线验证链不在本 Prompt 允许创建的
文件清单内（`data/adapters.ts` 未被允许），Today 运行态保持 fixture-driven Demo。

TDD seams（本 Sprint 测试只写在这些公共边界上）：
1. `useDailyTasks(fixture, options)` 返回的 controller 公开 API；
2. `useBreathCycle()` 返回的 `label / count` 只读状态；
3. `today.fixture.ts` 与 `contracts/today.ts` 的一致性；
4. `TodayView` 挂载后的公开 DOM（原型 selector + data-testid）与交互结果。

---

## 1. Hero（问候 + 今日进度行）

```text
Prototype:      02-sakura-spring.html #view-today .hero（865-879 行）
HTML selector:  .hero / .hero-arc / .hero-tag / .hero h1 em / .hero p b /
                .progress-row / .progress-num#progNum / .progress-track /
                .progress-fill#progFill / .progress-note#progNote /
                .progress-cta / #btnCheck / .hero-hint
Original behavior:
  - 结构：hero-arc 极光弧带（aria-hidden）→ hero-tag（✦ 春日极光 · 期中考试周 · 第 2 天）
    → h1「早上好，<em>小满</em>」→ 状态说明 p（两行，含 <b> 强调与 <br>）
    → progress-row（纯文字，无卡片边框，位于观察卡上方）；
  - progress-row 内含右端 progress-cta：btnCheck「✦ 开始今日检查」+ hero-hint
    「约 30 秒 · 从此刻的心情开始」；
  - 进度数字 innerHTML `${done}<small>/ 3</small>`；fill 宽度 done/3*100%，
    transition width 0.9s ease-decay；note 随 done 取 heroNotes[min(done,3)]；
  - .hero 根有 stagger 类，子元素五级延迟入场（0.05s 步进）。
Vue component:  components/today/TodayHero.vue（含进度行与 CTA）
Contract:       TodayContract.heroTag / greeting / summaryLines / progressNotes.hero
Fixture:        data/fixtures/today.fixture.ts（文案逐字来自冻结 HTML）
Test:           today-view.test.ts（结构渲染 + 进度文本/宽度随完成数变化）
Visual validation: 4 viewport 截图对比（docs/ui-migration/visual/sprint-04-fidelity.md）
```

## 2. Hero 进度行 ↔ 吸附顶栏进度（单一状态源）

```text
Prototype:      updateProgress()（1408-1420 行）+ .topbar（104-126 行）
HTML selector:  #progNum / #progFill / #progNote / #topbar / #tbNum / #tbFill / #tbNote
Original behavior:
  - done = taskStates 中 done|partial 的数量（唯一计数源）；
  - 同一 done 同时写入 hero 进度行与吸附顶栏；
  - hero note 与顶栏 note 是两套文案（heroNotes / notes），索引均为 min(done,3)；
  - topbar 仅在 body.tb-dock（progress-row 滚出视口）时可见；navbar 下移到 54px。
Vue component:  今日状态源 = useDailyTasks（App.vue 创建一次，传入 TodayView 与
                DockedTaskProgress）；hero 行在 TodayHero，吸附顶栏在既有
                shell/DockedTaskProgress.vue
Contract:       ShellTaskProgress（docked note）；TodayContract.progressNotes
Fixture:        progressNotes.hero / progressNotes.docked 四段文案
Test:           today-daily-tasks.test.ts「progress sync」（done 后 hero/docked
                note 同步取对应文案数组）；today-view.test.ts DOM 双侧断言
Visual validation: 完成一个任务后 hero 1/3 与顶栏 1/3 同屏截图
工程化差异:     DockedTaskProgress 在 Sprint 2R 中渲染「hero 进度行 + 顶栏」两组件合体，
                且行位于 view 顶部；冻结原型的进度行属于 hero 内部（含 CTA）。
                Sprint 4 将进度行还给 TodayHero，DockedTaskProgress 收敛为
                「仅顶栏 + 观测哨兵（sentinel prop）」，语义与原型
                `.view.active .progress-row` 查询一致。
```

## 3. 微律观察卡

```text
Prototype:      .observe-card（881-895 行）
HTML selector:  .observe-card / .obs-head h3 / .live / .obs-main em / .obs-sub /
                .obs-stats / .ob-stat / .os-k / .os-delta.up .warn / .sug-row /
                .sug-item / .sg-ic(.night)
Original behavior: 顶部 3px 粉条、obs-main 渐变强调 em、三个指标卡
                （昨夜睡眠/连续用眼/此刻情绪 + up/warn 变化说明）、
                两条今日建议（i-flower / i-moon night 图标）
Vue component:  components/today/ObservationCard.vue
Contract:       TodayContract.observation（main 三段 / summary / stats / suggestions）
Fixture:        文案逐字冻结
Test:           today-view.test.ts 结构断言
Visual validation: 截图对比
```

## 4. 心情卡（DailyCheck：心情 + 可用时间）

```text
Prototype:      .mood-card（899-919 行）+ moodRow/timeChips 交互（1499-1519 行）
HTML selector:  .section-title / .mood-card / .mood-head / .live / .mood-row /
                .moods#moodRow / .mood(.on) / .face / .chips#timeChips /
                .chip(.on) / .mood-note / .lbl
Original behavior:
  - section-title「现在的心情 / 心情会轻轻影响推荐」在卡片上方；
  - 4 心情钮（还不错/平静[默认 on]/有点累/有点低落），点击单选切换 .on，
    WL.play 700ms scale(1+0.1v) rotate(-3v) 脉冲；
  - 选「有点低落」(data-v=low)：toast「🌷 收到 · 薇薇把任务都换成了最轻的」，
    且当 data-idx=1 的任务为 pending 时，仅改写该卡 name/desc/why
    （domain/meta/色调类不变），换回其他心情不回写；
  - 3 时间 chip（10/25[默认 on]/40 分钟以上），单选 + 650ms scale(1+0.09v) 脉冲；
  - mood-note「已计入：… <br>怎么选都可以…」。
Vue component:  components/today/DailyCheckCard.vue（组合 MoodSelector +
                AvailableTimeSelector，不新增 DOM 层级）
Contract:       TodayContract.moods / defaultMood / timeOptions /
                defaultTimeMinutes / moodNote / lowMoodSwap
Fixture:        选项与默认值冻结自原型（calm / 25）
Test:           today-daily-tasks.test.ts（mood/time selection + low 换卡语义 +
                started 任务不被换）；today-view.test.ts（.on 类切换）
Visual validation: 截图对比
说明:           「薇薇把任务都换成了最轻的」只是冻结视觉文案，本 Sprint 不写
                Memory / Recommendation / API。
```

## 5. 今日微任务：三张任务卡

```text
Prototype:      .task-list#taskList + 三张 .task-card（921-964 行）
HTML selector:  .section-title / .task-list / .task-card(.t-eye .t-move .t-sleep) /
                .task-top / .task-domain / .task-meta / .task-name / .task-desc /
                .task-why / .why-icon / .task-actions / .task-state /
                .ck-ring .ck-path / .task-badge / .badge-txt
Original behavior:
  - 三卡：窗边远眺 20 秒（t-eye 用眼健康）/ 颈肩小伸展（t-move 颈肩放松）/
    花瓣呼吸 4-7-8（t-sleep 睡前准备）；文案、meta、why 逐字冻结；
  - 左侧 4px 色条随 t-* 类变色，done 后变紫；
  - task-state 右上角 44px 勾选 SVG（ck-ring/ck-path 描边动画，done 时序
    0.65s/0.95s 延迟）；task-badge 完成后浮现（done 1.05s / partial 0.4s）。
Vue component:  components/today/TaskList.vue（section-title + .task-list）+
                components/today/TaskCard.vue
Contract:       TodayContract.tasks（id/tone/domain/meta/name/description/why/whyIcon）
Fixture:        三任务内容冻结；id 使用唯一字符串（today-task-eye 等）
Test:           today-view.test.ts 结构断言；today-contract-validation.test.ts
                唯一 id
Visual validation: 4 viewport 截图对比
```

## 6. Task 状态机（pending / started / done / partial / skipped）

```text
Prototype:      taskStates 数组 + setTaskDone + click 分发（1399-1496 行）
HTML selector:  .task-actions 内 [data-act] 按钮组 / .done-note / .task-badge
Original behavior:
  - pending：[开始(btn-primary) 换一朵 先跳过]；
  - start → started：按钮组变 [✓ 完成啦(btn-ok) 部分完成 换一朵 先跳过]，
    卡片 translateY(-3v) 700ms 脉冲，toast「⏱ 开始啦 · 不着急」；
  - done：taskStates→done、卡片加 .done、badge「完成 · 今天的花瓣 +1」、
    按钮区替换为 done-note「🌸 已记下 · 今天的一片花瓣」、进度 +1、
    TaskCompletionFx、卡片 scale(1+0.02v) 950ms 脉冲、
    toast「✦ 已记下这次完成 · 薇薇会记住的」；
  - partial：→partial、badge「部分完成 · 也算数哦」、done-note
    「🌱 部分完成 · 已记下」、进度 +1、较轻 scale(1+0.012v) 700ms 脉冲、
    toast「🌱 部分完成也很棒 · 已记录」；
  - skip：→skipped、卡片 .skippedcard（opacity .6）、badge「跳过了 · 没关系呀」、
    按钮区变 [恢复它]、toast「🕊 跳过也没关系 · 薇薇会降低这类任务的频率」
    （冻结文案，不写 Memory）；
  - restore：→pending、移除 .skippedcard、按钮组还原初始三钮（无 toast）；
  - done/partial 为终态（setTaskDone 早退）。
Vue component:  TaskCard.vue（按钮组与终态标记渲染）+ 状态源 useDailyTasks
Contract:       TodayContract.feedbackCopy（各 toast 文案与 done-note 文案）
Fixture:        文案冻结
Test:           today-daily-tasks.test.ts（start/done/partial/skip/restore 状态与
                幂等终态）；today-view.test.ts（按钮组切换、badge、done-note）
Visual validation: 浏览器 QA 实操 + 截图
工程化差异:     原型用 innerHTML 换按钮；Vue 用 actions stage（initial/active/
                completed/restore）条件渲染，可见结果一致。
```

## 7. Replace（换一朵）

```text
Prototype:      REPLACE_POOL + replacePtr + replace 分支（1400-1404, 1475-1495 行）
HTML selector:  [data-act=replace]；卡片内容节点
Original behavior:
  - 静态池 3 项（走廊慢走 t-move / 掌心热敷闭眼 t-eye / 窗边晒太阳 t-sleep），
    模块级 replacePtr 循环取下一项（跨卡共享指针）；
  - 动画：transition(rise) 450ms translateX(-40px) rotate(-1.5deg) + opacity 0 →
    470ms 时换内容与 t-* 类 → transition(decay) 600ms 回位；
  - toast「🌸 换好了 · 新任务同样来自审核白名单」；
  - 按钮组重置为初始三钮；taskStates[idx] 不变（started 仍为 started：
    随后 low 心情因此不再换该卡——保持该语义）。
Vue component:  TaskCard.vue（displayTask 本地镜像 + out/in 两相动画）
Contract:       TodayContract.replacePool
Fixture:        池内容逐字冻结
Test:           today-daily-tasks.test.ts（循环取池 + 内容替换 + interaction
                不回退）；today-view.test.ts（换卡后 name 变化）
Visual validation: 浏览器 QA 实操
说明:           不调用推荐 API、不做 RAG、不造新推荐逻辑。
```

## 8. 450ms 同位换钮冷却

```text
Prototype:      card._actAt 判定（1443-1446 行）
HTML selector:  taskList click 分发器
Original behavior: 同一卡任意 [data-act] 点击后记录 _actAt；450ms 内的下一次
                点击直接 return（被吞掉的点击不刷新时间戳）；跨卡互不影响。
Vue component:  useDailyTasks（options.now 可注入时钟，默认 performance.now）
Test:           today-daily-tasks.test.ts「cooldown」（450ms 内忽略、之后放行、
                被忽略点击不延长冷却）
Visual validation: 浏览器 QA 连点验证
```

## 9. TaskCompletionFx 接线

```text
Prototype:      taskCompleteFx(card)（1387-1397 行）
HTML selector:  .task-state（视觉中心 cx/cy）
Original behavior: done 时取 .task-state getBoundingClientRect 中心，
                粒子汇聚(16) → 光球(+620ms) → 光环(+780ms)；参数不改。
Vue component:  复用 Sprint 3 components/effects/TaskCompletionFx.vue，
                每张 TaskCard 持有一个实例（对应原型每次完成各自生成一组 fx）
Test:           today-view.test.ts（done 后调用 play 且坐标为 .task-state 中心）
Visual validation: 浏览器 QA 实操观察粒子→光球→光环→符号浮现
说明:           不复制第二套粒子算法。
```

## 10. Toast

```text
Prototype:      toast()（1327-1334 行）+ .toast-box（679-688 行）
HTML selector:  #toastBox / .toast(.out)
Original behavior: 2600ms 后 .out，500ms 后移除；Today 全部反馈复用同一宿主。
Vue component:  复用 shell/ToastHost.vue + composables/useToast.ts；
                useToast 状态提升为模块级单例（ToastHost 与视图代码共享同一队列，
                对应原型唯一的 #toastBox），API 不变
Test:           既有 shell-components.test.ts toast 生命周期；today-view.test.ts
                交互后 toast 文案断言
Visual validation: 浏览器 QA
```

## 11. 开始今日检查（CTA 滚动聚焦）

```text
Prototype:      btnCheck 监听（1521-1530 行）+ .check-focus（296-300 行）
HTML selector:  #btnCheck / .mood-card.check-focus
Original behavior: 点击后 mood-card scrollIntoView(center)、重播 check-focus
                1.6s 光晕动画（先移除再强制 reflow 再加回，1700ms 后移除）、
                toast「✦ 从此刻的心情开始 · 30 秒完成今日检查」
Vue component:  TodayView（CTA 在 TodayHero，聚焦目标在 DailyCheckCard，
                经 defineExpose 暴露 focusCheck()）
Test:           today-view.test.ts（check-focus 类出现与移除、toast）
Visual validation: 浏览器 QA 实操
```

## 12. AI 节奏呼吸（右栏）

```text
Prototype:      breathLoop()（1532-1554 行）+ .breath-card（381-402 行）
HTML selector:  .breath-card / .breath-stage / .breath-core / .breath-halo /
                #breathCount / #breathLabel / .breath-tip
Original behavior: 9s 循环：吸气 1.8s（label「吸气 · 4 秒」，count 4→3→2→1，
                每 450ms）；呼气 7.2s（label「呼气 · 慢慢地」，count 由 RAF 逐帧
                计算 max(1, ceil(6*(1-t)))）；CSS 呼吸动画由 today.css 承载。
Vue component:  components/today/BreathCard.vue + composables/useBreathCycle.ts
Test:           today-motion.test.ts（fake timers 推进：吸气倒计时、呼气
                6→1 边界时刻、9s 循环重复）
Visual validation: 截图 + 浏览器观察文字节奏
工程化差异:     呼气倒计时改在精确边界时刻（1200ms 步进）调度 timeout，显示序列
                与 RAF 采样完全一致；全部 timer 经 composable 登记，卸载即清理。
```

## 13. 今日节奏（右栏）

```text
Prototype:      .rhythm-card（978-984 行）
HTML selector:  .rhythm-card / .rhythm-item(.now) / .rhythm-time / .rhythm-dot /
                .rhythm-txt
Original behavior: 3 项（17:30 窗边远眺[now] / 18:10 颈肩小伸展 / 21:40 花瓣呼吸）
Vue component:  components/today/RhythmTimeline.vue
Contract:       TodayContract.rhythm
Fixture:        内容冻结
Test:           today-view.test.ts 结构断言
Visual validation: 截图对比
```

## 14. Shell 接线与未迁移页占位

```text
Prototype:      switchView + 导航（1307-1325 行）
HTML selector:  .navbar / .nav-pill / .logo / .tabs / .tab-glider / .tab.active /
                .nav-date / .avatar
Original behavior: 今日为默认 active 视图；logo 点击回今日。
Vue component:  App.vue 切换为 shell 运行态（named slots）：
                #today = TodayView；assistant/profile/weekly 为最小
                placeholder/unavailable 结构态（无业务数据）；
                legacy 表单流保留于 ?legacy=1 查询参数后（Sprint 9 移除），
                既有 flow 测试经该入口继续覆盖旧功能
Test:           App.test.ts 重写（shell 默认 + legacy 门控）；app-shell.test.ts
                既有断言不变
Visual validation: 导航胶囊 / Today active / glider / 日期 / avatar 与冻结
                HTML 截图对比
```

## 15. CSS 激活边界

```text
Sprint 4 后:    today.css ACTIVE（index.css 于 layout.css 之后、accessibility.css
                之前导入，符合原型源顺序）
仍不激活:       assistant.css / profile.css / weekly.css / onboarding.css
Test:           visual-system.test.ts / contract-boundary.test.ts 更新对应断言
```

---

## 验收结果（实现后回填）

### 浏览器 QA 发现与修复（Chrome DevTools MCP，1080/960/720/560）

1. **fixed 定位失效 → 1080 视口横向溢出 1238px、完成特效错位**
   `.view.active` 的 `viewIn` 动画 `fill: both` 永久保留 `translateY(0)` 终态，
   transformed 祖先成为 `.topbar`（吸附顶栏）与 TaskCompletionFx 粒子等
   `position: fixed` 后代的包含块 → 相对 `.view` 而非视口定位。
   原型无此问题（topbar-wrap 挂 body 下、fx append body）。
   修复：layout.css fill 改 `backwards`（终态=自然态，视觉零差异）。
   验证：修复后各视口 scrollWidth==clientWidth；fx 粒子相对视口正确汇聚。
2. **legacy style.css 裸元素选择器泄漏（三个）**
   - `main{width:min(40rem,…)}=640px` 命中 `main.shell`（冻结 `.shell` 只声明
     max-width 未声明 width）→ 1080 下 Today 全部内容压成 640px 居中列
     （hero 596 vs 原型 1036；grid 292/330 vs 686/330）；
   - `section{margin-top:2rem}` 命中 `section.view` → 视图顶部 +32px；
   - `article{margin-top:2rem}` 命中 TaskCard 根 `<article>` → 每卡 +32px。
   修复：layout.css `.shell{width:auto}`、`.view{margin-top:0}`，
   today.css `.task-card{margin-top:0}`（class 特异性覆盖元素选择器；
   legacy 流程不经 .shell/.view/.task-card，不受影响）。
   验证：修复后 1080 下 hero/progress/observe/grid/mood/task0/breath 与原型
   getBoundingClientRect 逐项 0 差；task0 y=1298、grid h=1377 完全一致。

### 交互 QA 实操记录（全部通过）

- 开始 → 按钮组 [✓ 完成啦/部分完成/换一朵/先跳过] + toast ✓
- 完成啦 → done 类、done-note、badge、进度 0→1、16 粒子 FX、
  hero 1/3 与 docked 1/3 同步、toast ✓
- 部分完成 → partial 类、进度 +1（累计 2/3）、done-note、按钮区终态 ✓
- 先跳过 → .skippedcard + 恢复它；恢复 → 初始三钮还原 ✓
- 换一朵 → REPLACE_POOL 池内下一项（走廊慢走），状态归 pending，toast ✓
- 450ms 冷却 → start 后 0ms 连点 done 被吞 ✓
- 心情单选（默认 平静）+ 时间 chips（默认 25 分钟）+ 已计入信息保留 ✓
- 导航四页切换、未迁移页结构性占位（无业务数据）、回 Today ✓

### 截图存档

`%TEMP%\sprint4-visual/`：prototype-{1080,960,720,560}.png、
vue-{1080,960,720,560}.png（devicePixelRatio=1，fonts loaded + 沉降≥3s）。
差异台账：docs/ui-migration/visual/sprint-04-fidelity.md。

