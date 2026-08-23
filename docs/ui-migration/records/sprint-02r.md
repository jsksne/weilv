# Sprint 2R Migration Record

唯一依据：`ui-prototypes/02-sakura-spring.html`。本记录在实现代码修改前建立，所有选择器和行为均来自原型真实 HTML/CSS/JS。

## AppShell

Prototype: `ui-prototypes/02-sakura-spring.html`

HTML selector: `main.shell`, `.view`, `.view.active`（861-1111 行）

Original behavior: 原型以一个 `.shell` 作为主内容容器，四个 `.view` 同时存在但只有 `.view.active` 显示；非活动视图为 `display: none`，活动视图以 `viewIn` 上浮渐入。视图切换由 `switchView()` 移除旧 active、给目标视图加 active，并滚动到页面顶部。

Vue component: `frontend/src/layouts/AppShell.vue`

Contract dependency: `ShellContract.navigation`、`ShellContract.progress`、`ViewId`；四个 named slot 只承载未来 View 内容，default slot 保留 legacy 内容。

Test coverage: `frontend/src/app-shell.test.ts`（2 passed）验证 default legacy slot、四个 named slot 和 legacy mode 不强制渲染新页面；`frontend/src/shell-components.test.ts` 另验证 view switching 与 scroll-to-top。

## Navigation

Prototype: `ui-prototypes/02-sakura-spring.html`

HTML selector: `.navbar`, `.nav-pill`, `.tabs`, `.tab`, `.nav-right`（832-859 行）；`tabs.forEach(... switchView(...))`（1323-1325 行）

Original behavior: 顶部导航为 sticky glass pill，包含品牌、四个 tab、日期和头像；tab click 根据 `data-view` 切换 active 状态和对应 view，默认 active 为 today；resize 时重新计算 glider。

Vue component: `frontend/src/components/shell/AppNavigation.vue` + `frontend/src/composables/useAppNavigation.ts`

Contract dependency: `ShellNavigationItem[]`、`ViewId`、用户显示名和日期标签；不读取 API DTO，不持有业务状态。

Test coverage: `frontend/src/shell-components.test.ts`（navigation 3 cases passed）验证默认 today、tab click、active state、resize 重算和 listener cleanup；font loadingdone 使用同一安全重算路径。

## Glider

Prototype: `ui-prototypes/02-sakura-spring.html`

HTML selector: `.tab-glider#glider`（847-853 行）

Original behavior: `moveGlider(tab)` 将 glider width 设为 tab 的 `offsetWidth`，将 transform 设为 `translateX(tab.offsetLeft - 4px)`；CSS 用 `var(--ease-decay)` 过渡 width 和 transform；load、resize、switchView 都会重算。

Vue component: `AppNavigation.vue` + `useAppNavigation.ts`

Contract dependency: 当前 active `ViewId` 和注册的 tab DOM 尺寸；不依赖后端数据。

Test coverage: `frontend/src/shell-components.test.ts`（glider resize case passed）验证 `offsetWidth`、`offsetLeft - 4px`、resize 重算；`useAppNavigation.ts` 注册并清理 `document.fonts.loadingdone`。

## Docked Progress

Prototype: `ui-prototypes/02-sakura-spring.html`

HTML selector: `.progress-row`（870-878 行）；`.topbar-wrap`, `.topbar#topbar`, `.tb-num`, `.tb-fill`, `.tb-note`（821-829 行）

Original behavior: 今日页的进度行初始可见；scroll handler 用 passive listener + requestAnimationFrame，在 active view 的 `.progress-row` 的 bottom 小于 0 后给 body 加 `tb-dock`，显示 fixed glass topbar 并把 navbar top 调到 54px。`updateProgress()` 同步数字、fill 和 note。

Vue component: `frontend/src/components/shell/DockedTaskProgress.vue` + `frontend/src/composables/useDockedProgress.ts`

Contract dependency: `ShellTaskProgress` 的 completed、total、note；IntersectionObserver 只负责可视性，进度值不来自推荐 API。

Test coverage: `frontend/src/shell-components.test.ts`（2 cases passed）验证 observer 建立、visible/docked、无 IntersectionObserver 时的 scroll fallback、disconnect 和 unmount cleanup。

## Toast

Prototype: `ui-prototypes/02-sakura-spring.html`

HTML selector: `.toast-box#toastBox`, `.toast`（1113 行，CSS 678-688 行）；`toast(msg)`（1327-1334 行）

Original behavior: toast 追加到固定底部容器；2600ms 后加 `.out`，再过 500ms 删除节点；队列按追加顺序纵向排列，容器 pointer-events 为 none。

Vue component: `frontend/src/components/shell/ToastHost.vue` + `frontend/src/composables/useToast.ts`

Contract dependency: `ShellToast.message`；只表达 shell 通知，不和 legacy 业务 toast 合并。

Test coverage: `frontend/src/shell-components.test.ts`（2 cases passed）验证 push、队列渲染、2600ms + 500ms 自动消失和 unmount 后 timer cleanup。

## BrandLogo

Prototype: `ui-prototypes/02-sakura-spring.html`

HTML selector: `.logo`, `.logo-flower`, `.logo b`, `.logo span`（834-846 行）

Original behavior: 品牌区域使用 32×32 五瓣 SVG 花朵和“微律 / 春日极光 · 健康同伴”两行文字；点击品牌调用 `switchView('today')`；花朵使用 `flowerSway` 6 秒摇摆。

Vue component: `frontend/src/components/shell/BrandLogo.vue`

Contract dependency: display name/tagline 与导航的 today action；不引入新 logo 语义或第三方 icon。

Test coverage: `frontend/src/shell-components.test.ts`（brand case passed）验证原生 SVG 五瓣路径、文案结构和 activate 事件。

## IconSprite

Prototype: `ui-prototypes/02-sakura-spring.html`

HTML selector: 隐藏 `<svg><defs><symbol id="i-flower|i-moon|i-clock|i-leaf|i-target|i-book">`（809-819 行）；使用方为 `<svg class="ic"><use href="#i-*">`。

Original behavior: 页面提供全局原生 SVG symbol sprite，调用方通过 `use href` 复用线性图标；不加载第三方图标库。

Vue component: `frontend/src/components/shell/IconSprite.vue`

Contract dependency: `ShellIconName` 仅限定冻结原型 symbol 名称；不包含业务 DTO 字段。

Test coverage: `frontend/src/shell-components.test.ts`（icon case passed）验证六个冻结 symbol、`aria-hidden` 隐藏 sprite 和原生 SVG 结构。

## PrototypeReplayControl

Prototype: `ui-prototypes/02-sakura-spring.html`

HTML selector: `#protoTag.proto-tag`（1114 行）；click handler（1844-1849 行）

Original behavior: 原型标记固定在左下角，点击后把当前 URL 的 `onboard` query 设为 `1`，用于重新体验首次引导；它不是业务数据或页面状态。

Vue component: `frontend/src/components/shell/PrototypeReplayControl.vue`

Contract dependency: 只提供 shell replay event，不接入 onboarding、API 或业务状态；行为定义不足时保持最小可监听接口。

Test coverage: `frontend/src/shell-components.test.ts`（replay case passed）验证控制存在、可访问和触发 `replay` event；不验证或扩展产品 onboarding 流程。

## Deferred from Sprint 3 Review

- `FUTURE-S3-01`: `TaskCompletionFx` 在运行中切换 `prefers-reduced-motion` 时的 running reset；本 Sprint 只记录，不修改。
- `FUTURE-S3-02`: Petal spin duration 需在 Sprint 3 再确认到冻结原型的 `(5 + Math.random() * 6).toFixed(1)` 一位小数；本 Sprint 只记录，不修改。
- `FUTURE-S3-03`: screenshot-level visual regression；本 Sprint 只保留结构和声明级回归，不提前进入视觉挂载或截图验收。
