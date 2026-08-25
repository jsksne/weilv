# 微律 UI Migration — Release Checklist

## 基线

- **baseline commit:** `8db1af0`（fix: remove legacy runtime path）
- **final commit:** `chore: complete weilv ui migration release`
- **唯一视觉基线:** `ui-prototypes/02-sakura-spring.html`

## 构建 / 质量

- frontend tests: 31 文件全部通过（含 accessibility 7 例、secret-boundary、visual 无关）
- backend relevant tests: `test_api / test_task_events / test_weekly / test_memory / test_questionnaire` 通过
- lint: `npm run lint`（eslint .）通过
- build: `vue-tsc -b && vite build` 成功；TypeScript errors = 0
- backend diff: 0；unauthorized AI core diff: 0

## Runtime Smoke

- Demo: PASS（automated + 浏览器实测 Today/Assistant/Profile/Weekly/Onboarding）
- Production: `RUNTIME_PRODUCTION_BLOCKED_BY_ENVIRONMENT`（本地无 ES/后端）；自动测试覆盖数据链（sprint9-integration）

## Visual Regression（机制与参数）

- 脚本: `frontend/scripts/visual-regression.mjs`
- Browser: Chromium headless（ms-playwright chromium-1234 `chrome.exe`）
- Viewports: 1080/960/720/560；**固定高 900**；deviceScaleFactor=1；zoom=1
- Font 状态: `document.fonts.ready` + `waitUntil: networkidle0`
- Animation determinism: 注入 `animation:none;transition:none` + `prefers-reduced-motion: reduce`（CDP）→ 无随机种子需求
- Diff: `pixelmatch` threshold 0.1；pass 阈值 diffRatio ≤ 0.2%

### Visual Matrix

| Page | 1080 | 960 | 720 | 560 |
|---|---|---|---|---|
| onboarding-step1 | PASS | PASS | PASS | PASS |
| today | PASS | PASS | PASS | PASS |
| assistant | PASS | PASS | PASS | PASS |
| profile | PASS | PASS | PASS | PASS |
| weekly | PASS | PASS | PASS | PASS |

（详见 `frontend/tests/visual/diff/manifest.json`；无横向页面级溢出；560 无整体 scale-down。）

## 页面级横向溢出 / 响应式

- 1080/960/720/560 均无页面级横向溢出。
- 560 保持原有响应逻辑（非整体 scale-down）。

## B3 / 已知限制

- **B3 deferred**：Production Assistant 仅真实最终回答 + sources + Safety；无 fake trace/decomposition/chunk/score/timing。
- **USER_IDENTITY_SEAM**：Production 身份 = 显式 VITE_USER_ID（可替换 seam）；非完整多用户认证。
- **LOCAL_DAY_BOUNDARY_LIMITATION**：Weekly 为 UTC date 边界；前端不重新解释为本地自然日。
- **TODAY_QUERY_DEFAULT 审计（PASS）**：仅固定产品意图 query + current_context/activity_context='unknown'；target_stage 来自真实 Profile；无硬编码睡眠/健康/activity/safety/时间/偏好。
- **Production 仍 unavailable 字段**：Today sleep/vision/mood stats、rhythm、replace pool、low-mood swap；Profile time/task preference、completion %；Weekly AI insight；Assistant live trace。

## Cleanup（删除/保留记录）

**Deleted:** 无（全量引用扫描证明无死文件；`env.d.ts` 为构建必需）。

**Retained:**
| file | reason |
|---|---|
| `views/LegacyConsole.vue` + 7 legacy components + 4 legacy composables | test harness：新 UI 不承担旧业务入口（7 题问卷/Feedback 表单/Profile 编辑/手动推荐表单）；四个 flow 测试直接挂载验证 HTTP/business 契约 |
| `components/EvidenceList.vue` | runtime 共享（新 Assistant） |
| `styles/style.css` | 视觉级联必需（index.css 最先导入；visual-system.test.ts 锁定） |
| `styles/index.css` 及全部冻结样式 | 唯一 style entry |

**Runtime legacy path:** NONE（App 无 URLSearchParams/location.search/legacy 分支）。

## 边界审计

- Secret boundary: PASS（无 API/DashScope/ES keys、无 embedding/raw_query/retrieval_text/audit secret 于生产源码）。
- Views import api/types / fixture: 0。
- Accessibility: PASS（nav aria-label、按钮名称、表单 label、disabled 显式、错误非仅颜色、reduced-motion 可读可交互）。
- Reduced motion: PASS（内容不依赖动画完成；无无限动画干扰测试）。
- Demo fixture-only / Production API-only: PASS；Production fixture fallback: 0；runtime 自动模式切换: 0。

## 集成 Gate 复核

- B1 Top3、B2 events、B4 Memory、B5 Weekly、B6 Onboarding+consent：PASS（Sprint 9 集成 + 本 Sprint 回归测试维持）。

## Sprint 10.1 Animation Regression Gate（追加）

- 脚本: `frontend/scripts/animation-regression.mjs`（STATIC gate 原样保留）；产物 `frontend/tests/visual/dynamic/manifest.json`
- 确定性: 种子化 PRNG + 虚拟时钟（16ms 帧步进）+ `getAnimations().pause()/currentTime` 定点 seek；selfcheck 双侧双跑 0px
- Motion config: normal = no-preference；reduced = CDP reduce（reduce 场景真实等待 ≥ 最大 animation-delay 后 freeze 终态）
- Checkpoint: cpA=16ms / cpB=1100ms / cpC=2200ms（原型真实时长推导）；safety settle 5000ms；view transition 350ms；viewport 1080+560；DYNAMIC 容差 0.5%
- 结果: **12 pass / 4 FAIL** —— 4 FAIL 均为真实保真度差异（ANIMATION_REGRESSION_FOUND，仅报告未修复）:
  1. onboarding 欢迎 toast（`toastIn @ .toast`）Vue 未实现（task-1080/cpA full 0.199%；任务卡区域 0px）
  2. safety 会话栈: greeting `<br><br>` 文案标记、q-bubble 句号、safety-card `p+p` 6→0px、滚动锚点（safety/1080+560）
  3. motion-contract today 计数 104 vs 103（= toast −1 + viewIn fill-mode 白名单 −1）
- 验证: npm test 235/235、lint 0 error、build 成功、backend/src-weilv diff = 0、零产品文件修改（static gate 像素输出不变）
- 详见 `docs/ui-migration/records/sprint-10.md` §Sprint 10.1
