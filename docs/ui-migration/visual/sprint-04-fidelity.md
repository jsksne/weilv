# Sprint 4 视觉差异 Ledger — Today

对比对象：`ui-prototypes/02-sakura-spring.html`（冻结原型）vs Vue `TodayView`（`http://localhost:5174/`）。
截图：`visual/prototype-{1080,960,720,560}.png` 与 `visual/vue-{1080,960,720,560}.png`
（Chrome DevTools MCP，devicePixelRatio=1，等 fonts loaded + 入场动画沉降 ≥3s 后截取）。

## 定量几何对比（1080×900，getBoundingClientRect，单位 px）

| Area | Prototype | Vue | 差异 |
| --- | --- | --- | --- |
| nav-pill | x20 y14 w1040 h64，radius 999px，blur(20px) | 同 | 0 |
| tabs 文案 | 今日 / 问问薇薇 / 我的画像 / 周度变化 | 同 | 0 |
| 日期标签 | 4 月 22 日 · 星期日 | 同 | 0 |
| hero | x22 y104 w1036 h344 | 同 | 0 |
| hero-tag | ✦ 春日极光 · 期中考试周 · 第 2 天 | 同 | 0 |
| h1 | Noto Serif SC 50px/900/65px | 同 | 0 |
| progress-row | x22 y357 w1036 h65 | 同 | 0 |
| observe-card | x22 y448 w1036 h369，radius 24px，pad 26/30 | 同 | 0 |
| today-grid cols | 686px 330px (gap 20px) | 同 | 0 |
| mood-card | x22 y893 w686 h333 | 同 | 0 |
| task-card[0] | x22 y1298 w686 h291，radius 24px | 同 | 0 |
| breath-card | x728 y825 w330 h352 | 同 | 0 |
| body 渐变 | 172deg #f8f3fb→#fde9f1→#f9e2ee→#eee5fa | 同 | 0 |
| 横向溢出 | 0 | 0（修复前 1238px，已修） | 0 |

响应式断点：960/720/560 下两侧 today-grid 均转单列，行为一致；各视口横向溢出均为 0。

## QA 发现并已修复的差异

| Area | Difference | Fixed | Remaining |
| --- | --- | --- | --- |
| 吸附顶栏/完成特效定位 | `.view.active` 的 `viewIn` 动画 fill:both 永久保留 translateY(0) 终态，使 `.view` 成为 fixed 后代（.topbar、fx 粒子）的包含块 → 1080 视口横向溢出 1238px、完成特效相对 .view 错位。原型不受影响（topbar-wrap 挂 body、fx append body）。 | layout.css：fill 改 `backwards`（终态回归自然值，与原型视觉零差异） | 无 |
| Today 整体宽度 | legacy `style.css` 裸元素选择器 `main{width:min(40rem,…)}=640px` 命中 `main.shell`（冻结 `.shell` 只声明 max-width），1080 下内容被压成 640px 居中列（hero 596 vs 1036、grid 292/330 vs 686/330）。 | layout.css：`.shell` 显式 `width:auto`（class 特异性覆盖，legacy 流程不受影响） | 无 |
| 视图顶部间距 | legacy `section{margin-top:2rem}` 命中 `section.view` → hero y136 vs 原型 104（+32px）。 | layout.css：`.view` 显式 `margin-top:0` | 无 |
| 任务卡间距 | legacy `article{margin-top:2rem}` 命中 TaskCard 根元素 `<article>` → 每卡 +32px（task0 y1330 vs 1298，grid 高 +96）。 | today.css：`.task-card` 显式 `margin-top:0` | 无 |
| 按钮内边距 | 排查 legacy `button{padding:.5rem .75rem}` 泄漏：.tab/.chip/.mood/.btn 均有自身 padding（7/16、7/16、12/4/10、11/24），无泄漏。 | 无需修复 | 无 |

> **fidelity 测试白名单**：上表 4 项修复对应的声明差异在
> `frontend/src/visual-system.test.ts` 全量声明比对中以精确 key 豁免——
> ① `.view.active` viewIn fill `both → backwards`（一对 key 替换）；
> ② `.shell{width:auto}` / `.view{margin-top:0}` / `.task-card{margin-top:0}`
> （legacy 泄漏复位，原型无对应声明的新增声明）。除此之外，任何 frozen
> declaration 的无声漂移（缺失或新增）仍会使测试失败。

## 已知不可修差异（粒子随机性）

- TaskCompletionFx 粒子初始角度/距离含 `Math.random()`，逐帧位置不要求像素相同（Sprint 计划明示豁免）。
- 原型 fx 元素 append 到 `document.body`，Vue 为组件内 fixed 渲染 — 定位基准（视口坐标 cx/cy）与 z-index（95/96/97）一致，修复包含块后视觉等价（TaskCompletionFx.vue 头注已记录此工程化差异）。
- 原型导航无 `.glider` 元素（active 样式直接写 `.tab.active`）；Vue Sprint 2R 用 glider 元素实现同视觉的滑动指示，视觉等价。

## 结论

四个视口下 Vue Today 与冻结原型几何/样式逐项一致；QA 发现的 4 项泄漏/定位缺陷全部修复，无遗留差异。
