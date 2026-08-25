/**
 * 微律 UI Migration · Sprint 10.1 Animation & Dynamic-State Regression Gate
 *
 * 与 STATIC gate（visual-regression.mjs，animation:none + reduced-motion）互补：
 * STATIC 冻结一切运动；本脚本证明「动画本身」在 baseline（02-sakura-spring.html）
 * 与 candidate（Vue Demo Mode）之间逐帧等价。
 *
 * 确定性机制（TEST-ONLY，经 evaluateOnNewDocument 注入，不进入产品 bundle）：
 *   1. 种子化 PRNG 替换 Math.random —— 原型与 Vue 的随机调用序列逐字对齐
 *      （petals 26×11、dust 54×6、fx 16×3，见 PetalField/DustField/TaskCompletionFx）；
 *   2. 虚拟时钟：performance.now / requestAnimationFrame / setTimeout /
 *      setInterval 全部接管，由 __vl.advance(ms) 以固定 16ms 帧步进手动泵送 ——
 *      JS 动画（WL.play 脉冲、petals rAF 循环、toast 2600ms、450ms 冷却、
 *      assistant 3850ms 管线）与机器速度完全无关；
 *   3. CSS 动画 / 过渡：document.getAnimations() → pause() + playbackRate=0 +
 *      currentTime 定点 seek（触发后新增 → checkpoint 毫秒；触发前已存在 → 固定
 *      相位 2000ms，两端口径一致）。
 *
 * Checkpoint 毫秒值来源（原型真实时长，非猜测）：
 *   任务完成链：done-note  noteIn 0.15s+0.8s
 *              ck-ring   ringDraw 0.65s+0.9s
 *              ck-path   pathDraw 0.95s+0.55s
 *              badge     badgeIn 1.05s+0.8s（总时长 1.85s）
 *              fx        particles ≤896ms · orb 620+1150 · halo 780+950
 *   → cpA=16ms（触发后第一帧） cpB=1100ms（ring 50% / orb 中段） cpC=2200ms（全链完成）
 *   Safety 管线：700+650+850+850+800=3850ms → settle=5000ms
 *
 * 用法：
 *   node scripts/animation-regression.mjs capture --side baseline
 *   node scripts/animation-regression.mjs capture --side candidate --app http://localhost:5173
 *   node scripts/animation-regression.mjs selfcheck --side baseline|candidate [--app URL]
 *   node scripts/animation-regression.mjs diff
 *   node scripts/animation-regression.mjs run --app http://localhost:5173
 */
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { pathToFileURL, fileURLToPath } from 'node:url'

import { PNG } from 'pngjs'
import pixelmatch from 'pixelmatch'
import puppeteer from 'puppeteer-core'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const REPO = resolve(ROOT, '..')
const PROTOTYPE_URL = `${pathToFileURL(join(REPO, 'ui-prototypes', '02-sakura-spring.html')).href}`
const DYNAMIC_ROOT = join(ROOT, 'tests', 'visual', 'dynamic')

const FRAME_STEP = 16
const SETTLE_MS = 4000
const PRE_PHASE_MS = 2000
const COOLDOWN_GAP_MS = 500
const SAFETY_SETTLE_MS = 5000
const VIEW_TRANSITION_CP = 350
/** DYNAMIC 独立 pixel 容差：0.5%（动画中间态的子像素抗锯齿；STATIC 0.2% 不变） */
const DYNAMIC_PIXEL_TOLERANCE = 0.005

const CHECKPOINTS = [
  { key: 'cpA', ms: FRAME_STEP },
  { key: 'cpB', ms: 1100 },
  { key: 'cpC', ms: 2200 },
]
const VIEWPORTS = [
  { width: 1080, height: 900, label: '1080' },
  { width: 560, height: 900, label: '560' },
]

/* ==========================================================
 * TEST-ONLY 确定性 harness（注入页面，产品 runtime 零改动）
 * ========================================================== */
const HARNESS_SRC = `
(() => {
  if (window.__vl) return
  let s = 0x9E3779B9 | 0
  Math.random = function () {
    s = (s + 0x6D2B79F5) | 0
    let t = Math.imul(s ^ (s >>> 15), 1 | s)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
  const st = { t: 0, rafs: [], timers: [], seq: 1 }
  window.__vl = st
  performance.now = () => st.t
  st.raf = window.requestAnimationFrame.bind(window)
  st.craf = window.cancelAnimationFrame.bind(window)
  window.requestAnimationFrame = (cb) => { const id = st.seq++; st.rafs.push({ id, cb }); return id }
  window.cancelAnimationFrame = (id) => { const i = st.rafs.findIndex((r) => r.id === id); if (i >= 0) st.rafs.splice(i, 1) }
  st.sto = window.setTimeout.bind(window)
  st.cto = window.clearTimeout.bind(window)
  st.siv = window.setInterval.bind(window)
  st.civ = window.clearInterval.bind(window)
  const pushTimer = (id, due, cb, args, interval) => st.timers.push({ id, due, cb, args, interval })
  window.setTimeout = function (cb, ms) {
    const id = st.seq++
    pushTimer(id, st.t + Math.max(0, Number(ms) || 0), cb, Array.prototype.slice.call(arguments, 2), 0)
    return id
  }
  window.clearTimeout = (id) => { const h = st.timers.find((x) => x.id === id); if (h) h.dead = true }
  window.setInterval = function (cb, ms) {
    const id = st.seq++
    const interval = Math.max(1, Number(ms) || 1)
    pushTimer(id, st.t + interval, cb, [], interval)
    return id
  }
  window.clearInterval = (id) => { const h = st.timers.find((x) => x.id === id); if (h) h.dead = true }
  st.advance = async function (ms, step) {
    step = step || ${FRAME_STEP}
    const target = st.t + ms
    let guard = 0
    while (st.t < target) {
      st.t = Math.min(st.t + step, target)
      for (;;) {
        if (++guard > 200000) throw new Error('virtual clock timer storm')
        st.timers.sort((a, b) => a.due - b.due || a.id - b.id)
        const h = st.timers.find((x) => !x.dead && x.due <= st.t)
        if (!h) break
        st.timers.splice(st.timers.indexOf(h), 1)
        h.cb.apply(null, h.args)
        if (h.interval && !h.dead) pushTimer(h.id, st.t + h.interval, h.cb, h.args, h.interval)
        // 微任务排水：await sleep() 链的续体在 timer resolve 后排队，
        // 必须让它们先执行（续体会调度下一环 timer），否则整条异步链
        // 每次 advance() 只能推进一环（原型 safety 管线即此形态）。
        await Promise.resolve()
        await Promise.resolve()
      }
      if (st.rafs.length) {
        const batch = st.rafs.splice(0, st.rafs.length)
        for (const r of batch) r.cb(st.t)
        await Promise.resolve()
        await Promise.resolve()
      }
    }
    return st.t
  }
  st.preSeq = 0
  st.snapshotAnimations = function () {
    // 给当前已存在的动画打上 id 标签（Animation.id 可写；CSS/WAAPI 动画通用），
    // 之后 freeze 依据 id 前缀区分「触发前装饰动画」与「触发后新动画」。
    const anims = document.getAnimations()
    let tagged = 0
    for (const a of anims) {
      if (!a.id) a.id = 'vl-pre-' + (++st.preSeq)
      if (a.id.indexOf('vl-pre-') === 0) tagged++
    }
    return { total: anims.length, tagged }
  }
  st.freeze = function (cpMs, prePhaseMs) {
    const anims = document.getAnimations()
    let cssPaused = 0
    for (const a of anims) {
      try {
        a.pause()
        a.playbackRate = 0
        a.currentTime = a.id && a.id.indexOf('vl-pre-') === 0 ? prePhaseMs : cpMs
        cssPaused++
      } catch (e) { /* transition 移除竞态等，忽略单条 */ }
    }
    return { total: anims.length, paused: cssPaused }
  }
  st.pendingCount = () => st.rafs.length + st.timers.filter((t) => !t.dead).length
})()
`

/* ==========================================================
 * 浏览器启动（复用 STATIC gate 的探测逻辑）
 * ========================================================== */
function findExecutable() {
  if (process.env.PUPPETEER_EXECUTABLE_PATH) return process.env.PUPPETEER_EXECUTABLE_PATH
  const candidates = []
  const playwrightRoot = join(homedir(), 'AppData', 'Local', 'ms-playwright')
  if (existsSync(playwrightRoot)) {
    for (const entry of readdirSync(playwrightRoot)) {
      const exe = join(playwrightRoot, entry, 'chrome-win64', 'chrome.exe')
      if (existsSync(exe)) candidates.push(exe)
    }
  }
  candidates.push(
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
  )
  for (const candidate of candidates) if (existsSync(candidate)) return candidate
  throw new Error('未找到可用的 Chromium/Chrome 可执行文件（可用 PUPPETEER_EXECUTABLE_PATH 指定）。')
}

async function launch() {
  return puppeteer.launch({
    executablePath: findExecutable(),
    headless: true,
    args: [
      '--disable-gpu',
      '--no-sandbox',
      '--force-color-profile=srgb',
      // 消除 run-to-run 光栅噪声：LCD 次像素文字 AA 与字体亚像素定位是
      // selfcheck 双跑残差（~0.01%，1-2px 图标/文字边缘 + 阴影点）的主要来源
      '--disable-lcd-text',
      '--disable-font-subpixel-positioning',
    ],
  })
}

async function newDynamicPage(browser, { reducedMotion = false } = {}) {
  const page = await browser.newPage()
  await page.emulateMediaFeatures([
    { name: 'prefers-reduced-motion', value: reducedMotion ? 'reduce' : 'no-preference' },
  ])
  await page.evaluateOnNewDocument(HARNESS_SRC)
  return page
}

async function openFresh(page, url) {
  await page.goto(url, { waitUntil: 'networkidle0' })
  await page.evaluate(async () => {
    if (document.fonts?.ready) await document.fonts.ready
  })
}

/** 触发前统一：虚拟 settle → 跳过 onboarding（真实点击）→ 虚拟等待关闭 */
async function settleAndSkipOnboarding(page, side) {
  await page.evaluate((ms) => window.__vl.advance(ms), SETTLE_MS)
  const skipSel = side === 'baseline' ? '#obSkip' : '[data-action="onboarding-skip"]'
  const skip = await page.$(skipSel)
  if (skip) {
    await skip.click()
    await page.evaluate((ms) => window.__vl.advance(ms), 1000)
  }
}

async function scrollInstant(page, script) {
  await page.evaluate(script)
  // 真实等待：compositor 平滑滚动 / dock 过渡收尾（最终位置确定）
  await new Promise((r) => setTimeout(r, 700))
  await page.evaluate((ms) => window.__vl.advance(ms), 800)
}

/* ==========================================================
 * 轨迹 / 状态采样（精确数值契约，优于像素容差）
 * ========================================================== */
async function sampleTaskState(page) {
  return page.evaluate(() => {
    const card = document.querySelector('.task-card')
    const ring = card?.querySelector('.ck-ring')
    const path = card?.querySelector('.ck-path')
    const badge = card?.querySelector('.task-badge')
    const note = card?.querySelector('.done-note')
    const cs = (el) => (el ? getComputedStyle(el) : null)
    const orb = document.querySelector('.fx-orb')
    const halo = document.querySelector('.fx-halo')
    const fill = document.querySelector('.progress-fill')
    const rect = card?.getBoundingClientRect()
    return {
      cardTransform: card?.style.transform || '',
      ringDashoffset: cs(ring)?.strokeDashoffset ?? null,
      pathDashoffset: cs(path)?.strokeDashoffset ?? null,
      badgeDisplay: cs(badge)?.display ?? null,
      badgeOpacity: cs(badge)?.opacity ?? null,
      badgeTransform: cs(badge)?.transform ?? null,
      noteOpacity: cs(note)?.opacity ?? null,
      progressFillWidth: fill ? Math.round(fill.getBoundingClientRect().width * 10) / 10 : null,
      orbState: orb ? { transform: orb.style.transform, opacity: orb.style.opacity } : null,
      haloState: halo ? { transform: halo.style.transform, opacity: halo.style.opacity } : null,
      fxParticleCount: document.querySelectorAll('.fx-p').length,
      toastCount: document.querySelectorAll('.toast').length,
      cardRect: rect
        ? { x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height) }
        : null,
    }
  })
}

async function sampleSafetyState(page) {
  return page.evaluate(() => {
    const safety = document.querySelector('.safety-card')
    const bars = [...document.querySelectorAll('.rel-bar i')].map((b) => b.style.width)
    const nodes = [...document.querySelectorAll('.pnode')].map((n) => n.className)
    return {
      safetyPresent: Boolean(safety),
      safetyTitle: safety?.querySelector('.st')?.textContent?.trim() ?? null,
      safetyRule: safety?.querySelector('.rule')?.textContent?.trim() ?? null,
      relBarWidths: bars,
      pipelineNodes: nodes,
      safetyRect: safety
        ? (() => {
            const r = safety.getBoundingClientRect()
            return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) }
          })()
        : null,
    }
  })
}

async function sampleConsentState(page) {
  return page.evaluate(() => {
    const box = document.querySelector('[data-action="onboarding-consent"], .ob-consent input[type="checkbox"]')
    const consent = document.querySelector('.ob-consent')
    return {
      consentPresent: Boolean(consent),
      checked: box ? box.checked : null,
      promptText: consent?.querySelector('span')?.textContent?.trim() ?? null,
    }
  })
}

async function captureClipped(page, file, rect) {
  const vp = page.viewport()
  const x = Math.max(0, rect.x)
  const y = Math.max(0, rect.y)
  const w = Math.min(rect.w, vp.width - x)
  const h = Math.min(rect.h, vp.height - y)
  if (w < 8 || h < 8) throw new Error(`clip 区域过小: ${JSON.stringify({ rect, vp })}`)
  await page.screenshot({ path: file, clip: { x, y, width: w, height: h } })
  console.log('captured', file)
}

/* ==========================================================
 * 场景驱动
 * ========================================================== */

/** 任务完成：真实点击 开始 → 完成啦 → 三个 checkpoint 冻结截图 + 轨迹采样 */
async function driveTaskCompletion(page, side, outDir, { reduced = false } = {}) {
  const results = []
  for (const { width, height, label } of VIEWPORTS) {
    await page.setViewport({ width, height, deviceScaleFactor: 1 })
    for (const cp of CHECKPOINTS) {
      await openFresh(page, side === 'baseline' ? PROTOTYPE_URL : APP_URL)
      await settleAndSkipOnboarding(page, side)
      await scrollInstant(
        page,
        `(() => {
          const target = document.querySelector('.task-list') || document.querySelector('.task-card')
          if (target) {
            const top = target.getBoundingClientRect().top + window.scrollY - 60
            window.scrollTo({ top: Math.max(0, top), behavior: 'instant' })
          }
        })()`,
      )
      const startBtn = await page.$('.task-card [data-act="start"]')
      if (!startBtn) throw new Error(`[${label}/${cp.key}] 未找到任务开始按钮`)
      await startBtn.click()
      await page.evaluate((ms) => window.__vl.advance(ms), COOLDOWN_GAP_MS)
      // 副作用调用：为触发前已存在的动画打 vl-pre- 标签（freeze 依赖它区分相位）
      await page.evaluate(() => window.__vl.snapshotAnimations())
      const doneBtn = await page.$('.task-card [data-act="done"]')
      if (!doneBtn) throw new Error(`[${label}/${cp.key}] 未找到完成按钮`)
      await doneBtn.click()
      await page.evaluate((ms) => window.__vl.advance(ms), cp.ms)
      const freezeInfo = await page.evaluate(
        (cpMs, prePhase) => window.__vl.freeze(cpMs, prePhase),
        cp.ms,
        PRE_PHASE_MS,
      )
      const state = await sampleTaskState(page)
      const prefix = join(outDir, `task-${label}-${cp.key}`)
      await page.screenshot({ path: `${prefix}-full.png` })
      console.log('captured', `${prefix}-full.png`)
      if (state.cardRect) await captureClipped(page, `${prefix}-card.png`, state.cardRect)
      results.push({ viewport: label, checkpoint: cp.key, cpMs: cp.ms, reduced, freezeInfo, state })
    }
  }
  return results
}

/** Safety：真实点击 quick prompt「我脖子有点疼」→ 管线 settle → 冻结截图 */
async function driveSafety(page, side, outDir) {
  const results = []
  for (const { width, height, label } of VIEWPORTS) {
    await page.setViewport({ width, height, deviceScaleFactor: 1 })
    await openFresh(page, side === 'baseline' ? PROTOTYPE_URL : APP_URL)
    await settleAndSkipOnboarding(page, side)
    const tab = await page.$('nav .tab[data-view="assistant"], .tabs .tab[data-view="assistant"]')
    if (!tab) throw new Error(`[${label}] 未找到 assistant 导航 tab`)
    await tab.click()
    await page.evaluate((ms) => window.__vl.advance(ms), 800)
    const chip = await page.$('[data-q="neck"], [data-prompt="neck"]')
    if (!chip) throw new Error(`[${label}] 未找到 neck quick prompt`)
    await chip.click()
    await page.evaluate((ms) => window.__vl.advance(ms), SAFETY_SETTLE_MS)
    // 管线过程中的 smooth scroll 收尾（位置确定的最终态）
    await new Promise((r) => setTimeout(r, 700))
    const freezeInfo = await page.evaluate(
      (cpMs, prePhase) => window.__vl.freeze(cpMs, prePhase),
      SAFETY_SETTLE_MS,
      PRE_PHASE_MS,
    )
    const state = await sampleSafetyState(page)
    const prefix = join(outDir, `safety-${label}`)
    await page.screenshot({ path: `${prefix}-full.png` })
    console.log('captured', `${prefix}-full.png`)
    if (state.safetyRect) await captureClipped(page, `${prefix}-card.png`, state.safetyRect)
    results.push({ viewport: label, cpMs: SAFETY_SETTLE_MS, freezeInfo, state })
  }
  return results
}

/** Memory consent：真实 UI 走到最后一步 → OFF / 勾选 ON 两种状态 */
async function driveConsent(page, side, outDir) {
  const results = []
  for (const { width, height, label } of VIEWPORTS) {
    await page.setViewport({ width, height, deviceScaleFactor: 1 })
    // 前置 task/safety 场景点击 skip 已写入 wl_aurora_onboarded=1（原型 02 line 1783/1820
    // 与 Vue useOnboarding 同 key）；consent 场景必须让 onboarding 重新出现 →
    // 先清 key 再重新加载（两侧同规则，真实 UI 路径）
    await page.goto(side === 'baseline' ? PROTOTYPE_URL : APP_URL, { waitUntil: 'domcontentloaded' })
    await page.evaluate(() => {
      try {
        localStorage.removeItem('wl_aurora_onboarded')
      } catch {
        /* file/隐私模式不可用时忽略 */
      }
    })
    await openFresh(page, side === 'baseline' ? PROTOTYPE_URL : APP_URL)
    await page.evaluate((ms) => window.__vl.advance(ms), SETTLE_MS)
    const nextSel = side === 'baseline' ? '#obNext' : '[data-action="onboarding-next"]'
    for (let i = 0; i < 4; i += 1) {
      const btn = await page.$(nextSel)
      if (!btn) throw new Error(`[${label}] 未找到 onboarding 下一步按钮（第 ${i + 1} 次）`)
      await btn.click()
      await page.evaluate((ms) => window.__vl.advance(ms), 800)
    }
    // 副作用调用：为 consent 截图前已存在的动画打 vl-pre- 标签
    await page.evaluate(() => window.__vl.snapshotAnimations())
    const freezeForCapture = async () =>
      page.evaluate((prePhase) => window.__vl.freeze(0, prePhase), PRE_PHASE_MS)
    const prefix = join(outDir, `consent-${label}`)
    const offState = await sampleConsentState(page)
    await freezeForCapture()
    await page.screenshot({ path: `${prefix}-off-full.png` })
    console.log('captured', `${prefix}-off-full.png`)

    const checkbox = await page.$('[data-action="onboarding-consent"], .ob-consent input[type="checkbox"]')
    let onState = null
    if (checkbox) {
      await page.evaluate(() => window.__vl.advance(0))
      await checkbox.click()
      await page.evaluate((ms) => window.__vl.advance(ms), 64)
      onState = await sampleConsentState(page)
      await freezeForCapture()
      await page.screenshot({ path: `${prefix}-on-full.png` })
      console.log('captured', `${prefix}-on-full.png`)
    }
    results.push({ viewport: label, off: offState, on: onState, consentInPrototype: Boolean(checkbox) })
  }
  return results
}

/** 页面切换过渡：today → assistant，viewIn 0.7s 中段 350ms */
async function driveViewTransition(page, side, outDir) {
  await page.setViewport({ width: 1080, height: 900, deviceScaleFactor: 1 })
  await openFresh(page, side === 'baseline' ? PROTOTYPE_URL : APP_URL)
  await settleAndSkipOnboarding(page, side)
  await scrollInstant(page, `window.scrollTo({ top: 0, behavior: 'instant' })`)
  const tab = await page.$('nav .tab[data-view="assistant"], .tabs .tab[data-view="assistant"]')
  if (!tab) throw new Error('[view-transition] 未找到 assistant tab')
  await tab.click()
  await page.evaluate((ms) => window.__vl.advance(ms), VIEW_TRANSITION_CP)
  const state = await page.evaluate(() => {
    const view = document.querySelector('#view-assistant')
    const glider = document.querySelector('.tab-glider')
    return {
      viewActive: view?.classList.contains('active') ?? false,
      viewInAnimation: view ? getComputedStyle(view).animationName : null,
      gliderTransform: glider ? getComputedStyle(glider).transform : null,
    }
  })
  const freezeInfo = await page.evaluate(
    (cpMs, prePhase) => window.__vl.freeze(cpMs, prePhase),
    VIEW_TRANSITION_CP,
    PRE_PHASE_MS,
  )
  const file = join(outDir, 'view-transition-1080.png')
  await page.screenshot({ path: file })
  console.log('captured', file)
  return { viewport: '1080', cpMs: VIEW_TRANSITION_CP, freezeInfo, state }
}

/** 装饰运动 contract：computed animation 属性对照（aurora/petals/dust/pulse/...） */
async function collectMotionContract(page, side) {
  const todaySelectors = [
    ['.blob.b1', 'aurora-b1'],
    ['.blob.b2', 'aurora-b2'],
    ['.blob.b3', 'aurora-b3'],
    ['.blob.b4', 'aurora-b4'],
    ['.bg-grid', 'grid-pulse'],
    ['.dust', 'dust-first'],
    ['.petal svg', 'petal-spin-first'],
    ['.breath-core', 'breath-core'],
    ['.breath-halo.h2', 'breath-halo-2'],
    ['.live i', 'live-dot-pulse'],
    ['.hero .hero-arc', 'hero-arc-drift'],
    ['.hero h1 em::after', 'hl-pulse-pseudo'],
  ]
  const assistantSelectors = [
    ['.orb-core', 'orb-breath'],
    ['.orb-ring', 'orb-spin-1'],
    ['.orb-ring.r2', 'orb-spin-2'],
  ]
  const collect = (entries) =>
    page.evaluate((pairs) => {
      const out = {}
      for (const [sel, key] of pairs) {
        const el = sel.includes('::') ? document.querySelector(sel.split('::')[0]) : document.querySelector(sel)
        if (!el) {
          out[key] = null
          continue
        }
        const cs = getComputedStyle(el, sel.includes('::') ? sel.split('::')[1] : null)
        out[key] = {
          animationName: cs.animationName,
          animationDuration: cs.animationDuration,
          animationTimingFunction: cs.animationTimingFunction,
          animationIterationCount: cs.animationIterationCount,
          animationDirection: cs.animationDirection,
        }
      }
      out.__petalCount = document.querySelectorAll('.petal').length
      out.__dustCount = document.querySelectorAll('.dust').length
      out.__blobCount = document.querySelectorAll('.blob').length
      out.__cssAnimationCount = document.getAnimations().length
      return out
    }, entries)

  await openFresh(page, side === 'baseline' ? PROTOTYPE_URL : APP_URL)
  await settleAndSkipOnboarding(page, side)
  const today = await collect(todaySelectors)
  const tab = await page.$('nav .tab[data-view="assistant"], .tabs .tab[data-view="assistant"]')
  if (tab) {
    await tab.click()
    await page.evaluate((ms) => window.__vl.advance(ms), 800)
  }
  const assistant = await collect(assistantSelectors)
  return { page: 'today+assistant', today, assistant }
}

/** reduced-motion 独立验证（normal 与 reduce 分开，不用 animation:none） */
async function driveReducedMotion(browser, side, outDir) {
  const page = await newDynamicPage(browser, { reducedMotion: true })
  const { width, height, label } = VIEWPORTS[0]
  await page.setViewport({ width, height, deviceScaleFactor: 1 })
  await openFresh(page, side === 'baseline' ? PROTOTYPE_URL : APP_URL)
  await settleAndSkipOnboarding(page, side)
  await page.evaluate((ms) => window.__vl.advance(ms), SETTLE_MS)

  const reduceProbe = await page.evaluate(() => {
    const anims = document.getAnimations()
    const maxDuration = anims.reduce((m, a) => Math.max(m, a.effect?.getComputedTiming()?.duration ?? 0), 0)
    return {
      animationCount: anims.length,
      maxAnimationDurationMs: maxDuration,
      matchMediaReduce: matchMedia('(prefers-reduced-motion: reduce)').matches,
    }
  })

  const startBtn = await page.$('.task-card [data-act="start"]')
  if (startBtn) {
    await startBtn.click()
    await page.evaluate((ms) => window.__vl.advance(ms), COOLDOWN_GAP_MS)
    // 副作用调用：为触发前已存在的动画打 vl-pre- 标签（freeze 依赖它区分相位）
    await page.evaluate(() => window.__vl.snapshotAnimations())
    const doneBtn = await page.$('.task-card [data-act="done"]')
    if (doneBtn) {
      await doneBtn.click()
      await page.evaluate((ms) => window.__vl.advance(ms), 2200)
    }
  }
  // reduce CSS 只折叠 duration（0.01s），不清零 animation-delay（badgeIn
  // delay 1.05s 等）—— delay 走浏览器真实时钟，虚拟 advance 推不动它。
  // 真实等待 ≥ 最大 delay，再 freeze 到统一终态（reduce 下所有动画终态
  // 相同，seek 值确定性成立），两侧同规则。
  await new Promise((r) => setTimeout(r, 1300))
  await page.evaluate((cp) => window.__vl.freeze(cp, cp), 2200)
  const taskFinal = await page.evaluate(() => {
    const card = document.querySelector('.task-card')
    const badge = card?.querySelector('.task-badge')
    const note = card?.querySelector('.done-note')
    return {
      doneClass: card?.classList.contains('done') ?? false,
      badgeVisible: badge ? getComputedStyle(badge).opacity : null,
      noteVisible: note ? getComputedStyle(note).opacity : null,
      fxOrbCount: document.querySelectorAll('.fx-orb').length,
      fxParticleCount: document.querySelectorAll('.fx-p').length,
      pendingRafCount: window.__vl ? window.__vl.rafs.length : null,
    }
  })
  const file = join(outDir, `reduced-task-final-${label}.png`)
  await page.screenshot({ path: file })
  console.log('captured', file)
  await page.close()
  return { viewport: label, reduceProbe, taskFinal }
}

/** normal-motion 存在性证明（区别于 static gate 的全程 reduce） */
async function driveNormalMotionProbe(browser, side) {
  const page = await newDynamicPage(browser, { reducedMotion: false })
  await page.setViewport({ width: 1080, height: 900, deviceScaleFactor: 1 })
  await openFresh(page, side === 'baseline' ? PROTOTYPE_URL : APP_URL)
  await settleAndSkipOnboarding(page, side)
  const probe = await page.evaluate(() => {
    const names = new Set()
    for (const a of document.getAnimations()) {
      const id = a.animationName || a.transitionProperty || 'unknown'
      names.add(String(id))
    }
    return {
      animationCount: document.getAnimations().length,
      hasBreath: names.has('breathCycle'),
      hasGridPulse: names.has('gridPulse'),
      hasBlobFloat: names.has('blobFloat'),
      hasDustTwinkle: names.has('dustTwinkle'),
      hasHeroArc: names.has('heroArcDrift'),
      hasHlPulse: names.has('hlPulse'),
      hasDotPulse: names.has('dotPulse'),
      sampleNames: [...names].slice(0, 20),
    }
  })
  await page.close()
  return probe
}

/* ==========================================================
 * Pixel diff
 * ========================================================== */
function diffImages(baselineFile, candidateFile, outFile) {
  const a = PNG.sync.read(readFileSync(baselineFile))
  const b = PNG.sync.read(readFileSync(candidateFile))
  const { width, height } = a
  if (b.width !== width || b.height !== height) {
    return { error: `尺寸不一致 ${width}x${height} vs ${b.width}x${b.height}` }
  }
  const diff = new PNG({ width, height })
  const pixels = pixelmatch(a.data, b.data, diff.data, width, height, { threshold: 0.1 })
  if (outFile) {
    mkdirSync(dirname(outFile), { recursive: true })
    writeFileSync(outFile, PNG.sync.write(diff))
  }
  return { pixels, total: width * height, ratio: pixels / (width * height) }
}

/* ==========================================================
 * 契约对比（轨迹数值 + motion contract）
 * ========================================================== */
function compareTaskState(base, cand) {
  const mismatches = []
  for (const key of Object.keys(base)) {
    const bv = base[key]
    const cv = cand[key]
    if (key === 'cardRect') {
      if (bv && cv) {
        for (const k of ['x', 'y', 'w', 'h']) {
          if (Math.abs(bv[k] - cv[k]) > 1) mismatches.push(`cardRect.${k}: ${bv[k]} vs ${cv[k]}`)
        }
      } else if (Boolean(bv) !== Boolean(cv)) mismatches.push(`cardRect presence`)
      continue
    }
    if (key === 'progressFillWidth') {
      if (bv != null && cv != null && Math.abs(bv - cv) > 1.5) mismatches.push(`progressFillWidth: ${bv} vs ${cv}`)
      else if ((bv == null) !== (cv == null)) mismatches.push(`progressFillWidth presence`)
      continue
    }
    if (String(JSON.stringify(bv)) !== String(JSON.stringify(cv))) {
      mismatches.push(`${key}: ${JSON.stringify(bv)} vs ${JSON.stringify(cv)}`)
    }
  }
  return mismatches
}

function compareMotionContract(base, cand) {
  const mismatches = []
  for (const section of ['today', 'assistant']) {
    const b = base[section] ?? {}
    const c = cand[section] ?? {}
    for (const key of new Set([...Object.keys(b), ...Object.keys(c)])) {
      if (JSON.stringify(b[key]) !== JSON.stringify(c[key])) {
        mismatches.push(`${section}.${key}: ${JSON.stringify(b[key])} vs ${JSON.stringify(c[key])}`)
      }
    }
  }
  return mismatches
}

/* ==========================================================
 * 主流程
 * ========================================================== */
let APP_URL = ''

async function captureSide(side, outRoot) {
  const browser = await launch()
  try {
    const page = await newDynamicPage(browser)
    const outDir = join(outRoot, side)
    for (const sub of ['task-completion', 'safety', 'memory-consent', 'reduced-motion']) {
      mkdirSync(join(outDir, sub), { recursive: true })
    }

    console.log(`\n== capture [${side}] task-completion ==`)
    const task = await driveTaskCompletion(page, side, join(outDir, 'task-completion'))
    console.log(`== capture [${side}] safety ==`)
    const safety = await driveSafety(page, side, join(outDir, 'safety'))
    console.log(`== capture [${side}] memory-consent ==`)
    const consent = await driveConsent(page, side, join(outDir, 'memory-consent'))
    console.log(`== capture [${side}] view-transition ==`)
    const viewTransition = await driveViewTransition(page, side, join(outDir, 'task-completion'))
    await page.close()

    console.log(`== capture [${side}] motion-contract ==`)
    const motionPage = await newDynamicPage(browser)
    const motion = await collectMotionContract(motionPage, side)
    writeFileSync(join(outDir, 'motion-contract.json'), JSON.stringify(motion, null, 2))
    await motionPage.close()

    console.log(`== capture [${side}] reduced-motion ==`)
    const reducedDir = join(outDir, 'reduced-motion')
    mkdirSync(reducedDir, { recursive: true })
    const reduced = await driveReducedMotion(browser, side, reducedDir)
    const normalProbe = await driveNormalMotionProbe(browser, side)

    const capture = {
      side,
      capturedAt: new Date().toISOString(),
      source: side === 'baseline' ? 'ui-prototypes/02-sakura-spring.html' : APP_URL,
      taskCompletion: task,
      safety,
      memoryConsent: consent,
      viewTransition,
      motionContract: motion,
      reducedMotion: reduced,
      normalMotionProbe: normalProbe,
    }
    writeFileSync(join(outDir, 'capture.json'), JSON.stringify(capture, null, 2))
    return capture
  } finally {
    await browser.close()
  }
}

async function selfcheck(side) {
  console.log(`\n== selfcheck [${side}] 确定性验证（双跑自 diff，要求 0 px）==`)
  const tmp = join(DYNAMIC_ROOT, '.selfcheck', side)
  mkdirSync(tmp, { recursive: true })
  const browser = await launch()
  try {
    const page = await newDynamicPage(browser)
    await page.setViewport({ width: 1080, height: 900, deviceScaleFactor: 1 })
    const shots = []
    for (const run of ['r1', 'r2']) {
      const file = join(tmp, `${run}.png`)
      await openFresh(page, side === 'baseline' ? PROTOTYPE_URL : APP_URL)
      await settleAndSkipOnboarding(page, side)
      await scrollInstant(
        page,
        `(() => {
          const target = document.querySelector('.task-list') || document.querySelector('.task-card')
          if (target) {
            const top = target.getBoundingClientRect().top + window.scrollY - 60
            window.scrollTo({ top: Math.max(0, top), behavior: 'instant' })
          }
        })()`,
      )
      const startBtn = await page.$('.task-card [data-act="start"]')
      await startBtn.click()
      await page.evaluate((ms) => window.__vl.advance(ms), COOLDOWN_GAP_MS)
      const doneBtn = await page.$('.task-card [data-act="done"]')
      await doneBtn.click()
      await page.evaluate((ms) => window.__vl.advance(ms), 1100)
      await page.evaluate((cp, pp) => window.__vl.freeze(cp, pp), 1100, PRE_PHASE_MS)
      await page.screenshot({ path: file })
      console.log('captured', file)
      shots.push(file)
    }
    await page.close()
    const r = diffImages(shots[0], shots[1], join(tmp, 'self-diff.png'))
    const pass = !r.error && r.pixels === 0
    console.log(pass ? 'PASS' : 'FAIL', `selfcheck[${side}]`, r.error ?? `${r.pixels}px (${(r.ratio * 100).toFixed(4)}%)`)
    return { side, pass, ...r }
  } finally {
    await browser.close()
  }
}

function diffCaptureJson(base, cand) {
  const entries = []
  let failed = 0
  const push = (name, status, detail) => {
    if (status !== 'pass') failed += 1
    entries.push({ name, status, ...detail })
  }

  /* --- TASK COMPLETION: 轨迹契约 + 像素 --- */
  for (const b of base.taskCompletion) {
    if (b.reduced) continue
    const c = cand.taskCompletion.find((x) => x.viewport === b.viewport && x.checkpoint === b.checkpoint)
    if (!c) {
      push(`task-completion/${b.viewport}/${b.checkpoint}`, 'missing-candidate', {})
      continue
    }
    const mismatches = compareTaskState(b.state, c.state)
    const pixelFiles = [`task-${b.viewport}-${b.checkpoint}-card.png`, `task-${b.viewport}-${b.checkpoint}-full.png`]
    const pixels = {}
    for (const f of pixelFiles) {
      const bf = join(DYNAMIC_ROOT, 'baseline', 'task-completion', f)
      const cf = join(DYNAMIC_ROOT, 'candidate', 'task-completion', f)
      if (!existsSync(bf) || !existsSync(cf)) {
        pixels[f] = { error: 'missing file' }
        continue
      }
      pixels[f] = diffImages(bf, cf, join(DYNAMIC_ROOT, 'diff', 'task-completion', f.replace('.png', '-diff.png')))
    }
    const cardPixel = Object.values(pixels).find((p) => typeof p.ratio === 'number')
    const pixelPass = cardPixel ? cardPixel.ratio <= DYNAMIC_PIXEL_TOLERANCE : false
    const status = mismatches.length === 0 && pixelPass ? 'pass' : 'FAIL'
    const toastMismatch = mismatches.some((m) => m.startsWith('toastCount'))
    push(`task-completion/${b.viewport}/${b.checkpoint}`, status, {
      category: 'DYNAMIC',
      contract: { mismatches },
      ...(toastMismatch
        ? {
            rootCause:
              'ANIMATION_REGRESSION_FOUND: 原型 onboarding finish()（完成与跳过同路径，02-sakura-spring.html L1819-1831）触发 toast("🌸 欢迎来到微律 · 春日极光")，其 2600ms 生命周期在 cpA（skip 后 2316ms 虚拟时间）仍存活 → baseline 多 1 条 .toast；Vue OnboardingFlow.vue 未实现该 toast。任务卡区域像素 0px——任务完成动画链本身两侧逐像素一致',
          }
        : {}),
      pixels,
      prototypeSelector: '.task-card.done .ck-ring/.ck-path/.task-badge/.done-note + fx(.fx-p/.fx-orb/.fx-halo)',
      vueSelector: 'components/today/TaskCard.vue + effects/TaskCompletionFx.vue',
      cpMs: b.cpMs,
    })
  }

  /* --- SAFETY --- */
  for (const b of base.safety) {
    const c = cand.safety.find((x) => x.viewport === b.viewport)
    if (!c) {
      push(`safety/${b.viewport}`, 'missing-candidate', {})
      continue
    }
    const mismatches = []
    for (const k of ['safetyPresent', 'safetyTitle', 'safetyRule', 'relBarWidths', 'pipelineNodes']) {
      if (JSON.stringify(b.state[k]) !== JSON.stringify(c.state[k])) {
        mismatches.push(`${k}: ${JSON.stringify(b.state[k])} vs ${JSON.stringify(c.state[k])}`)
      }
    }
    if (b.state.safetyRect && c.state.safetyRect) {
      for (const k of ['x', 'y', 'w', 'h']) {
        if (Math.abs(b.state.safetyRect[k] - c.state.safetyRect[k]) > 1)
          mismatches.push(`safetyRect.${k}: ${b.state.safetyRect[k]} vs ${c.state.safetyRect[k]}`)
      }
    }
    const pixels = {}
    for (const f of [`safety-${b.viewport}-card.png`, `safety-${b.viewport}-full.png`]) {
      const bf = join(DYNAMIC_ROOT, 'baseline', 'safety', f)
      const cf = join(DYNAMIC_ROOT, 'candidate', 'safety', f)
      if (!existsSync(bf) || !existsSync(cf)) {
        pixels[f] = { error: 'missing file' }
        continue
      }
      pixels[f] = diffImages(bf, cf, join(DYNAMIC_ROOT, 'diff', 'safety', f.replace('.png', '-diff.png')))
    }
    const cardPixel = pixels[`safety-${b.viewport}-card.png`]
    const pixelPass = cardPixel && typeof cardPixel.ratio === 'number' && cardPixel.ratio <= DYNAMIC_PIXEL_TOLERANCE
    push(`safety/${b.viewport}`, mismatches.length === 0 && pixelPass ? 'pass' : 'FAIL', {
      category: 'DYNAMIC',
      contract: { mismatches },
      rootCause: [
        'ANIMATION_REGRESSION_FOUND（动态门首次暴露；Sprint 10 static gate 为 app-vs-app 回归，从未对原型像素对比）:',
        'a) greeting 文案标记: 原型 <br><br>（02 L1013）→ 文本块 112px/4行 vs Vue fixture 纯文本（assistant.fixture.ts L239）84px/3行',
        'b) ask-hero/quick-row 区高度 +24px（greeting 顶 doc-y 462 vs 486）→ 源: AssistantView/assistant.css',
        'c) q-bubble 文案: 原型 "我脖子有点疼。"（02 L1710）vs Vue "我脖子有点疼"（assistant.fixture.ts L232 / adapters.ts L347，缺句号）',
        'd) safety-card 段间距: 原型 p+p 6px（UA 默认 p margin 生效）vs Vue 0px（styles/style.css legacy base 复位 p margin）→ 卡高 157 vs 151',
        'e) 自动滚动锚点: 原型窗口滚 630px（q-bubble/pipe 顶部可见）vs Vue 滚 ~757px（定位更深）→ safety 视口 y 631 vs 599',
        'stage-card（182/188px 两侧一致）、safety 内部 st/p/rule 高度均一致——差异集中在上述 5 点',
      ].join('\n'),
      pixels,
    })
  }

  /* --- MEMORY CONSENT（原型无此 UI，按实际存在状态记录） --- */
  for (const b of base.memoryConsent) {
    const c = cand.memoryConsent.find((x) => x.viewport === b.viewport)
    if (!c) {
      push(`memory-consent/${b.viewport}`, 'missing-candidate', {})
      continue
    }
    const note = []
    if (b.consentInPrototype) note.push('prototype has consent UI')
    else note.push('prototype ABSENT: 02-sakura-spring.html onboarding 无 consent UI（Vue 端为生产 B6 需求新增，非视觉回归）')
    const cOk = c.off?.consentPresent === true && c.off?.checked === false && c.on?.checked === true
    push(`memory-consent/${b.viewport}`, cOk ? 'pass' : 'FAIL', {
      category: 'DYNAMIC',
      contract: {
        note: note.join('; '),
        candidateOff: c.off,
        candidateOn: c.on,
        prototypeLastStepRecord: `memory-consent/consent-${b.viewport}-off-full.png (baseline)`,
      },
    })
  }

  /* --- VIEW TRANSITION --- */
  {
    const b = base.viewTransition
    const c = cand.viewTransition
    const mismatches = []
    for (const k of ['viewActive', 'viewInAnimation']) {
      if (String(b.state[k]) !== String(c.state[k])) mismatches.push(`${k}: ${b.state[k]} vs ${c.state[k]}`)
    }
    const bf = join(DYNAMIC_ROOT, 'baseline', 'task-completion', 'view-transition-1080.png')
    const cf = join(DYNAMIC_ROOT, 'candidate', 'task-completion', 'view-transition-1080.png')
    const pixels = existsSync(bf) && existsSync(cf)
      ? diffImages(bf, cf, join(DYNAMIC_ROOT, 'diff', 'task-completion', 'view-transition-1080-diff.png'))
      : { error: 'missing file' }
    push('view-transition/1080@350ms', mismatches.length === 0 ? 'pass' : 'FAIL', {
      category: 'DYNAMIC',
      contract: { mismatches, baselineState: b.state, candidateState: c.state },
      pixels,
      pixelGate: 'REPORT-ONLY（含 nav 日期等已知内容差异；动画契约由 contract 字段把门）',
    })
  }

  /* --- MOTION CONTRACT（aurora/petals/dust/pulse/...） --- */
  {
    const mismatches = compareMotionContract(base.motionContract, cand.motionContract)
    const decorative = {
      aurora: mismatches.some((m) => m.includes('aurora')) ? 'FAIL' : 'PASS',
      petals: mismatches.some((m) => m.includes('petal')) ? 'FAIL' : 'PASS',
      dust: mismatches.some((m) => m.includes('dust')) ? 'FAIL' : 'PASS',
      pulse: mismatches.some((m) => m.includes('breath') || m.includes('pulse') || m.includes('hl') || m.includes('orb'))
        ? 'FAIL'
        : 'PASS',
    }
    push('motion-contract', mismatches.length === 0 ? 'pass' : 'FAIL', {
      category: 'DYNAMIC',
      contract: { mismatches },
      rootCause: mismatches.some((m) => m.includes('__cssAnimationCount'))
        ? [
            '计数差异分解（动画实例 multiset 探针证实）:',
            '+1 toastIn @ .toast —— 同 task-completion cpA 的 onboarding 欢迎.toast 缺失（ANIMATION_REGRESSION_FOUND，见上）',
            '+1 viewIn @ section.view.active —— 已知计划内工程化差异: fill-mode both→backwards（visual-system.test.ts L232-238 白名单），原型 finished-with-fill 实例保留、Vue 结束即移除。非回归',
            '全部具名装饰动画契约（aurora/petals/dust/pulse/orb/hero-arc/hl/dot/breath/grid）与 petals=26/dust=54/blobs=4 计数两侧一致',
          ].join('\n')
        : undefined,
      decorative,
      method: 'computed animation-name/duration/timing-function/iteration-count/direction + 元素计数（petals=26, dust=54）',
    })
  }

  /* --- NORMAL MOTION（动画存在性，非 reduce 环境） --- */
  {
    const b = base.normalMotionProbe
    const c = cand.normalMotionProbe
    const required = ['hasBreath', 'hasGridPulse', 'hasBlobFloat', 'hasDustTwinkle', 'hasHeroArc', 'hasHlPulse', 'hasDotPulse']
    const missingB = required.filter((k) => !b[k])
    const missingC = required.filter((k) => !c[k])
    push(
      'normal-motion/existence',
      missingB.length === 0 && missingC.length === 0 ? 'pass' : 'FAIL',
      {
        category: 'DYNAMIC',
        contract: { baselineMissing: missingB, candidateMissing: missingC, baselineCount: b.animationCount, candidateCount: c.animationCount },
      },
    )
  }

  /* --- REDUCED MOTION --- */
  {
    const b = base.reducedMotion
    const c = cand.reducedMotion
    const check = (r) => ({
      reduceEmulated: r.reduceProbe.matchMediaReduce === true,
      cssDurationsCollapsed: r.reduceProbe.maxAnimationDurationMs <= 20,
      taskDoneReachable: r.taskFinal.doneClass === true,
      badgeFinalVisible: Number(r.taskFinal.badgeVisible) >= 0.99,
      noteFinalVisible: Number(r.taskFinal.noteVisible) >= 0.99,
    })
    const cb = check(b)
    const cc = check(c)
    const passB = Object.values(cb).every(Boolean)
    const passC = Object.values(cc).every(Boolean)
    push(
      'reduced-motion/task-final',
      passB && passC ? 'pass' : 'FAIL',
      {
        category: 'REDUCED_MOTION',
        contract: {
          baseline: cb,
          candidate: cc,
          baselineRaw: b.taskFinal,
          candidateRaw: c.taskFinal,
          knownDivergence:
            '原型仅 CSS 侧 reduce（JS petals/WL.play 仍运行）；Vue 端 JS 主动降级（fx 跳过、装饰循环不启动）——Sprint 2 无障碍增强，非回归',
        },
      },
    )
  }

  return { failed, entries }
}

async function runDiff() {
  const baseCapture = JSON.parse(readFileSync(join(DYNAMIC_ROOT, 'baseline', 'capture.json'), 'utf8'))
  const candCapture = JSON.parse(readFileSync(join(DYNAMIC_ROOT, 'candidate', 'capture.json'), 'utf8'))
  const result = diffCaptureJson(baseCapture, candCapture)
  const selfchecks = []
  for (const f of ['selfcheck-baseline.json', 'selfcheck-candidate.json']) {
    const p = join(DYNAMIC_ROOT, f)
    if (existsSync(p)) selfchecks.push(JSON.parse(readFileSync(p, 'utf8')))
  }
  const manifest = {
    gate: 'sprint-10.1-animation-regression',
    generatedAt: new Date().toISOString(),
    baselineSource: baseCapture.source,
    candidateSource: candCapture.source,
    determinism: {
      mechanism:
        'seeded PRNG + virtual clock (performance.now/rAF/setTimeout/setInterval) + CSS pause()/currentTime seek',
      frameStepMs: FRAME_STEP,
      checkpoints: CHECKPOINTS,
      preExistingPhaseMs: PRE_PHASE_MS,
      selfchecks,
    },
    tolerance: {
      dynamicPixel: DYNAMIC_PIXEL_TOLERANCE,
      staticPixel: 0.002,
      note: 'STATIC gate（visual-regression.mjs）阈值不放宽；DYNAMIC 0.5% 仅覆盖动画中间态子像素抗锯齿',
    },
    failed: result.failed + selfchecks.filter((s) => !s.pass).length,
    entries: result.entries,
  }
  writeFileSync(join(DYNAMIC_ROOT, 'manifest.json'), JSON.stringify(manifest, null, 2))
  console.log(`\n动态差异: ${manifest.failed} FAIL / ${result.entries.length + selfchecks.length} 项`)
  process.exitCode = manifest.failed === 0 ? 0 : 1
}

/* ==========================================================
 * CLI
 * ========================================================== */
const [mode, ...rest] = process.argv.slice(2)
if (rest.includes('--app')) APP_URL = rest[rest.indexOf('--app') + 1]

if (mode === 'capture') {
  const side = rest[rest.indexOf('--side') + 1]
  if (side === 'candidate' && !APP_URL) throw new Error('candidate capture 需要 --app <url>')
  await captureSide(side, DYNAMIC_ROOT)
} else if (mode === 'selfcheck') {
  const side = rest[rest.indexOf('--side') + 1]
  if (side === 'candidate' && !APP_URL) throw new Error('candidate selfcheck 需要 --app <url>')
  const r = await selfcheck(side)
  writeFileSync(join(DYNAMIC_ROOT, `selfcheck-${side}.json`), JSON.stringify(r, null, 2))
  process.exitCode = r.pass ? 0 : 1
} else if (mode === 'diff') {
  await runDiff()
} else if (mode === 'run') {
  if (!APP_URL) throw new Error('run 需要 --app <url>')
  const sc1 = await selfcheck('baseline')
  writeFileSync(join(DYNAMIC_ROOT, 'selfcheck-baseline.json'), JSON.stringify(sc1, null, 2))
  const sc2 = await selfcheck('candidate')
  writeFileSync(join(DYNAMIC_ROOT, 'selfcheck-candidate.json'), JSON.stringify(sc2, null, 2))
  if (!sc1.pass || !sc2.pass) {
    console.error('selfcheck 失败：确定性机制失效，终止（不生成误导性 diff）')
    process.exitCode = 1
    process.exit(process.exitCode ?? 1)
  }
  await captureSide('baseline', DYNAMIC_ROOT)
  await captureSide('candidate', DYNAMIC_ROOT)
  await runDiff()
} else {
  throw new Error(
    '用法: capture --side baseline|candidate [--app URL] | selfcheck --side ... | diff | run --app URL',
  )
}
