# Sprint 3 Migration Record — 冻结视觉系统迁移与真实 AppShell 挂载

冻结基线：`ui-prototypes/02-sakura-spring.html`（唯一视觉与交互验收基准）
本记录在实现前建立（Prototype Reading Rule），验收时补齐测试与视觉验证结果。

---

## 1. Body / background

```text
Prototype:      02-sakura-spring.html <style> body 规则（49-58 行）+ .bg 统一背景层（62-101 行）
HTML selector:  body；.bg / .blob.b1..b4 / .bg-grid / #petalField / #dust / .bg-noise
Original behavior:
  - body：min-height 100vh、overflow-x hidden、清晨天空四段渐变 172deg、background-attachment fixed；
  - .bg：position fixed、inset 0、z-index 0、overflow hidden、pointer-events none；
  - 层序（DOM 顺序）：blobs → bg-grid → petalField → dust → bg-noise；
  - 4 个 blob：vw/vh 尺度、blur(110px)、radial-gradient(closest-side)、blobIn 2.6s 入场 +
    blobFloat 24s alternate 循环、b2/b3/b4 双 animation-delay；
  - bg-grid：64px 双向线性网格、上半屏 radial mask 渐隐、gridPulse 16s；
  - bg-noise：SVG feTurbulence 噪点、opacity 0.035。
Vue component:  components/effects/AuroraBackground.vue（组合 PetalField / DustField）
CSS owner:      styles/base.css（body 画布）、styles/aurora.css（背景层）、
                styles/animations.css（blobIn/blobFloat/gridPulse）
Contract dependency: 无（纯视觉层，aria-hidden）
Test coverage:  visual-system.test.ts「AuroraBackground renders the full background stack」；
                sprint3-visual-mount.test.ts「AppShell mounts … both modes」
Visual validation: 4 viewport 截图对比（见 §11）
```

## 2. Aurora blobs

```text
Prototype:      .blob / .blob.b1..b4（69-75 行）
HTML selector:  .blob.b1 .blob.b2 .blob.b3 .blob.b4
Original behavior: 数量 4、blur 110px、radial-gradient 与透明度原值、
                   入场/漂浮动画 timing 与 delay 原值
Vue component:  AuroraBackground.vue（静态 div，无 JS）
CSS owner:      styles/aurora.css
Contract dependency: 无
Test coverage:  findAll('.blob') 长度 4（AppShell 与 AuroraBackground 双侧）
Visual validation: 截图对比 aurora 色晕
```

## 3. Grid / Noise

```text
Prototype:      .bg-grid（78-88 行）、.bg-noise（98-101 行）
HTML selector:  .bg-grid .bg-noise
Original behavior: 网格 64px、mask 渐隐、gridPulse；噪点 data-URI、opacity 0.035
Vue component:  AuroraBackground.vue
CSS owner:      styles/aurora.css
Contract dependency: 无
Test coverage:  find('.bg-grid') / find('.bg-noise') 存在性
Visual validation: 截图
```

## 4. Petal field

```text
Prototype:      petals() IIFE（1215-1267 行）、#petalField / .petal（63-66 行）
HTML selector:  #petalField .petal
Original behavior: N=26；depth 随机决定 size(10~26)/blur(0|1.5)/opacity(0.45~0.95)/vy(26~72)；
                   初始 y 分布 (rand*1.6-0.6)*vh；S 曲线 sx = x + sin(t·freq+phase)·amp；
                   呼吸缩放 sc = scaleBase·(1+0.22·sin(t·freq·1.6+phase))；
                   自旋 CSS petalSpin（dur = (5+rand*6).toFixed(1) 秒，一位小数）；
                   视口回收：y > vh+60 → y=-60、x 重随机；dt 钳制 0.05s
Vue component:  components/effects/PetalField.vue（v-for 渲染 + useDecorativeField RAF）
CSS owner:      styles/aurora.css（#petalField/.petal）、styles/animations.css（petalSpin）
Contract dependency: composables/useDecorativeField.ts
Test coverage:  26 片、path d 原值、初始 transform 就位、一位小数时长（本 Sprint 新增）
Visual validation: 截图（deterministic seed 说明见 §11）
```

## 5. Dust field

```text
Prototype:      makeDust() IIFE（1270-1281 行）、#dust / .dust（90-96 行）
HTML selector:  #dust .dust
Original behavior: 54 粒；五色 #ffd9e2/#e6d5f9/#cdeee6/#ffe9db/#ffffff；
                   size 0.8~3px、--d 2.8~6.8s、--delay 0~4s、--o 0.35~0.85、
                   box-shadow 0 0 (size*2) 同色；CSS dustTwinkle 非对称脉冲
Vue component:  components/effects/DustField.vue（纯 CSS 动画，无 JS 计时器）
CSS owner:      styles/aurora.css（#dust/.dust）、styles/animations.css（dustTwinkle）
Contract dependency: 无
Test coverage:  54 粒、--d/--delay/--o/box-shadow 存在性
Visual validation: 截图
```

## 6. Navbar visual / Logo / Glider

```text
Prototype:      .navbar（129-133 行）、.nav-pill（134-142 行）、.logo/.logo-flower（143-147 行）、
                .tabs（148 行）、.tab-glider（150-156 行）、.tab（157-163 行）、
                .nav-right/.nav-date/.avatar（164-173 行）
HTML selector:  .navbar .nav-pill .logo .logo-flower .tabs .tab-glider .tab .nav-right .avatar
Original behavior: navbar sticky top 14px z-50；nav-pill 玻璃（blur 20px + border + outline +
                   双层阴影）；logo flowerSway 6s 摇摆；glider 依赖 var(--grad-aurora)、
                   transform/width 过渡 0.55s var(--ease-decay)；tab active 白字 +
                   text-shadow；avatar 渐变圆 + hover scale(1.1) rotate(-6deg)
Vue component:  components/shell/AppNavigation.vue + BrandLogo.vue（Sprint 2R 已建，行为已测）
CSS owner:      styles/navigation.css（本 Sprint 正式激活）
Contract dependency: contracts/ui.ts ShellNavigationItem
Test coverage:  shell-components.test.ts（Sprint 2R 导航行为）；
                本 Sprint 激活 CSS 后由截图验证视觉
Visual validation: 截图（glider 渐变/阴影、tab active、logo）
```

## 7. Docked progress visual

```text
Prototype:      .topbar-wrap/.topbar/.tb-label/.tb-num/.tb-track/.tb-fill/.tb-note（104-126 行）
HTML selector:  .topbar-wrap .topbar .tb-label .tb-num .tb-track .tb-fill .tb-note
Original behavior: topbar fixed top 8px、min(640px, 100vw-28px)、高 40px、玻璃 blur 18px、
                   隐藏态 translateX(160%)/opacity 0/visibility hidden；
                   body.tb-dock 时滑入；fill 三段渐变 + glow、width 过渡 0.9s ease-decay
Vue component:  components/shell/DockedTaskProgress.vue（Sprint 2R.1 逻辑已正确，observer 不改）
CSS owner:      styles/navigation.css（本 Sprint 正式激活）
Contract dependency: contracts/ui.ts ShellTaskProgress
Test coverage:  shell-components.test.ts（吸附逻辑）；视觉由截图验证
Visual validation: 截图（本 Sprint shell fixture 下 docked 态人工核对）
```

## 8. Glass system

```text
Prototype:      .card（181-186 行）+ 玻璃表面 .topbar/.nav-pill（如上）
HTML selector:  .card .topbar .nav-pill
Original behavior: .card 白 0.8 底、1px 边、24px 圆角、柔影；
                   玻璃声明 backdrop-filter 与 -webkit-backdrop-filter 成对保留（4 处/前缀 3 处）
Vue component:  —（类名由内容组件使用；页面 Sprint 接管）
CSS owner:      styles/glass.css、styles/navigation.css
Contract dependency: 无
Test coverage:  visual-system.test.ts backdrop-filter 计数断言
Visual validation: 截图
```

## 9. Global animations / Motion pulse

```text
Prototype:      全部 @keyframes（petalSpin…ringSpin）+ WL 运动对象（1194-1211 行）
HTML selector:  @keyframes petalSpin/blobIn/blobFloat/gridPulse/dustTwinkle/flowerSway/viewIn/…
Original behavior: rise(t)=t³、decay(t)=exp(-4.5t)、pulse 0-20% rise / 20-100% decay；
                   play() RAF 驱动；全部关键帧缓动原值
Vue component:  composables/useMotionPulse.ts、useDecorativeField.ts
CSS owner:      styles/animations.css
Contract dependency: 无
Test coverage:  visual-system.test.ts「pulse math parity」+ reduced-motion 双侧降级用例
Visual validation: 运行时检查（无 infinite RAF 报错）
```

## 10. Reduced motion

```text
Prototype:      @media (prefers-reduced-motion: reduce)（794-796 行）
HTML selector:  *，*::before，*::after
Original behavior: animation-duration 0.01s !important、iteration-count 1、transition 0.01s
Vue component:  useMotionPulse / useDecorativeField / TaskCompletionFx（JS 停 RAF/timer）
CSS owner:      styles/accessibility.css
Contract dependency: 无
Test coverage:  CSS 冻结断言 + RAF 停止断言 + 本 Sprint 新增 TaskCompletionFx reset 用例
Visual validation: 手动检查（浏览器模拟 reduce）
```

## 11. Visual regression（FUTURE-S3-03）

```text
方法: 真实浏览器截图对比，固定 viewport 1080/960/720/560、固定 DPR 1、
      字体加载完成后截取。动画时间点约束：blobIn 2.6s 入场完成后的稳定帧；
      花瓣/光尘为随机粒子，属非确定层，截图以同 seed 说明为人工核对项。
结果: 见 SPRINT-3-REPORT.md §H（PASS / AUTOMATED_VISUAL_CAPTURE_UNAVAILABLE）
```

## 12. 本 Sprint 修复

```text
FUTURE-S3-01  TaskCompletionFx 播放中切 prefers-reduced-motion：
              useMotionPulse 已 dispose RAF/timer，但 running 与瞬态 FX DOM 未复位 →
              增加 watch(reducedMotion)：reduce 开启且 running 时 dispose()+reset()，
              组件随后可再次 play()。
FUTURE-S3-02  PetalField 自旋时长未保留原型 (5+rand*6).toFixed(1) 一位小数行为 →
              spinSeconds = Number((5 + Math.random() * 6).toFixed(1))，分布不变（5.0~11.0）。
```

## 13. import order 决策（styles/index.css）

```text
顺序: ../style.css（legacy）→ reset → tokens → typography → base → glass →
      animations → aurora → effects → navigation → layout → accessibility
依据:
  - legacy 与冻结 CSS 在 body 上有直接冲突（font-family/color/background）：
    同特异性下后导入者胜；冻结 body 视觉必须生效 → legacy 必须在前；
  - 其余 legacy 规则（main/section/form/button/…）与冻结 CSS 无同名冲突，
    不受顺序影响，旧业务保持可操作；
  - 冻结资产之间按原型 <style> 源顺序排列（reset 首行 → :root → body →
    .bg 层 → topbar/navbar → .shell/.view → 媒体查询 → reduced-motion 收尾），
    keyframes 文件（animations.css）提前集中导入不影响级联（@keyframes 无层叠冲突）。
页面 CSS（today/assistant/profile/weekly/onboarding）本 Sprint 不激活（Sprint 4-7 资产）。
```
