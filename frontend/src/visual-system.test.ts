import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { enableAutoUnmount, mount } from '@vue/test-utils'

import AssistantOrb from './components/effects/AssistantOrb.vue'
import AuroraBackground from './components/effects/AuroraBackground.vue'
import DustField from './components/effects/DustField.vue'
import PetalField from './components/effects/PetalField.vue'
import TaskCompletionFx from './components/effects/TaskCompletionFx.vue'
import { useDecorativeField } from './composables/useDecorativeField'
import { useMotionPulse } from './composables/useMotionPulse'

/* ------------------------------------------------------------------
   视觉系统测试
   1. CSS 入口（Sprint 3 起正式激活冻结 Shell 资产，legacy 兼容保留在最前）
   2. tokens 可加载（关键令牌逐字校验 + 与原型全量声明比对）
   3. effects 组件可 mount（结构与原型一致）
   4. reduced-motion 逻辑存在（CSS + composable 双侧降级）
   5. 无明显生命周期泄漏（RAF / timeout 卸载即清理）
   ------------------------------------------------------------------ */

/* 每个 case 结束自动卸载挂载的组件，避免装饰循环跨测试存活 */
enableAutoUnmount(afterEach)

const srcDir = dirname(fileURLToPath(import.meta.url))
const stylesDir = join(srcDir, 'styles')
const prototypeFile = join(srcDir, '..', '..', 'ui-prototypes', '02-sakura-spring.html')

const STYLE_FILES = [
  'reset',
  'tokens',
  'base',
  'typography',
  'glass',
  'aurora',
  'effects',
  'animations',
  'navigation',
  'layout',
  'today',
  'assistant',
  'profile',
  'weekly',
  'onboarding',
  'accessibility',
] as const

function readStyle(name: string): string {
  return readFileSync(join(stylesDir, `${name}.css`), 'utf8')
}

/* ---------- 声明级解析：供与原型全量比对 ---------- */

function stripCssComments(css: string): string {
  return css.replace(/\/\*[\s\S]*?\*\//g, '')
}

interface CssRule {
  selector: string
  decls: string[]
}

function parseCssRules(css: string): CssRule[] {
  const rules: CssRule[] = []
  let i = 0
  while (i < css.length) {
    while (i < css.length && /\s/.test(css[i]!)) i += 1
    if (i >= css.length) break
    if (css[i] === '@') {
      let headEnd = i
      while (headEnd < css.length && css[headEnd] !== '{' && css[headEnd] !== ';') headEnd += 1
      if (css[headEnd] === ';') {
        i = headEnd + 1
        continue
      }
      const head = css.slice(i, headEnd).trim()
      let depth = 1
      let bodyEnd = headEnd + 1
      while (bodyEnd < css.length && depth > 0) {
        if (css[bodyEnd] === '{') depth += 1
        else if (css[bodyEnd] === '}') depth -= 1
        bodyEnd += 1
      }
      const body = css.slice(headEnd + 1, bodyEnd - 1)
      if (head.startsWith('@keyframes')) {
        rules.push({ selector: head, decls: [body] })
      } else if (head.startsWith('@media')) {
        for (const inner of parseCssRules(body)) {
          rules.push({ selector: `${head} ${inner.selector}`, decls: inner.decls })
        }
      }
      i = bodyEnd
    } else {
      let open = i
      while (open < css.length && css[open] !== '{') open += 1
      if (open >= css.length) break
      const selector = css.slice(i, open).trim()
      let depth = 1
      let close = open + 1
      while (close < css.length && depth > 0) {
        if (css[close] === '{') depth += 1
        else if (css[close] === '}') depth -= 1
        close += 1
      }
      const decls = css
        .slice(open + 1, close - 1)
        .split(';')
        .map(decl => decl.trim())
        .filter(Boolean)
      rules.push({ selector, decls })
      i = close
    }
  }
  return rules
}

function collectDeclarationCounts(css: string): Map<string, number> {
  const counts = new Map<string, number>()
  const squash = (text: string): string => text.replace(/\s+/g, '')
  for (const rule of parseCssRules(stripCssComments(css))) {
    for (const decl of rule.decls) {
      const key = `${squash(rule.selector)}{${squash(decl)}`
      counts.set(key, (counts.get(key) ?? 0) + 1)
    }
  }
  return counts
}

function prototypeCss(): string {
  const html = readFileSync(prototypeFile, 'utf8')
  const match = html.match(/<style>([\s\S]*?)<\/style>/)
  if (!match) throw new Error('prototype <style> block not found')
  return match[1]!
}

/* ---------- 1. CSS 入口 ---------- */

describe('visual system: css entrypoint', () => {
  it('activates the frozen shell assets in an explicit cascade order, legacy first', () => {
    const entry = readFileSync(join(stylesDir, 'index.css'), 'utf8')
    expect(entry).toContain("@import '../style.css'")

    /* 冻结 Shell 资产按原型 <style> 源顺序激活；legacy 必须最先导入，
       否则其 body{font/color/background} 会盖掉冻结视觉（同特异性后者胜）。
       Sprint 7：Today、Assistant、Profile、Weekly 与 Onboarding 页面正式激活 */
    const activated = [
      'reset',
      'tokens',
      'typography',
      'base',
      'glass',
      'animations',
      'aurora',
      'effects',
      'navigation',
      'layout',
      'today',
      'assistant',
      'profile',
      'weekly',
      'onboarding',
      'accessibility',
    ] as const
    const imports = [...entry.matchAll(/@import '\.\/([a-z-]+)\.css'/g)].map(m => m[1])
    expect(imports).toEqual([...activated])
    expect(entry.indexOf("@import '../style.css'")).toBeLessThan(entry.indexOf("@import './reset.css'"))
  })

  it('keeps the Weekly CSS activation explicit in the entrypoint', () => {
    const entry = readFileSync(join(stylesDir, 'index.css'), 'utf8')
    expect(entry).toContain("@import './today.css'")
    expect(entry).toContain("@import './profile.css'")
    expect(entry).toContain("@import './onboarding.css'")
    expect(entry).toContain("@import './weekly.css'")
  })

  it('every split file exists on disk and is non-empty', () => {
    for (const name of STYLE_FILES) {
      expect(readStyle(name).length).toBeGreaterThan(0)
    }
  })
})

/* ---------- 2. tokens 与全量声明保真 ---------- */

describe('visual system: tokens and fidelity', () => {
  it('keeps the critical tokens byte-identical to the prototype', () => {
    const tokens = readStyle('tokens')
    expect(tokens).toContain(
      '--grad-aurora: linear-gradient(100deg, #ffa8bd 0%, #f78fb0 42%, #b9a7ea 100%)',
    )
    expect(tokens).toContain('--ease-rise: cubic-bezier(0.55, 0.055, 0.675, 0.19)')
    expect(tokens).toContain('--ease-decay: cubic-bezier(0.16, 1, 0.3, 1)')
    expect(tokens).toContain("--disp: 'Noto Serif SC', 'Songti SC', 'STSong', 'SimSun', serif")
    expect(tokens).toContain("--sans: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif")
    expect(tokens).toContain('--ink: #594452')
    expect(tokens).toContain('--pink-deep: #f27ba4')
    expect(tokens).toContain('--teal-ink: #46958a')
  })

  it('migrates every prototype declaration with nothing lost or redesigned', () => {
    const prototypeCounts = collectDeclarationCounts(prototypeCss())
    const migratedCounts = collectDeclarationCounts(STYLE_FILES.map(readStyle).join('\n'))

    /* 计划内等价拆分：原型 960px 断点中的合并选择器 `.today-grid, .week-grid`
       拆入 today.css / weekly.css 各一条（声明与断点完全一致）。 */
    const splitMediaRule = '@media(max-width:960px).today-grid,.week-grid{grid-template-columns:1fr'
    const splitParts = [
      '@media(max-width:960px).today-grid{grid-template-columns:1fr',
      '@media(max-width:960px).week-grid{grid-template-columns:1fr',
    ]
    /* 计划内收口：dotPop / valIn 在原型中由脚本运行时注入 <style>，此处为静态资产。 */
    const runtimeKeyframes = ['@keyframesdotPop{', '@keyframesvalIn{']

    /* Sprint 7 additions: data-driven SVG text/points, empty and unavailable
       states, plus the mobile overflow guard. These have no frozen prototype
       declaration to compare against. */
    const weeklySprintExtras = [
      '.chart-point{',
      '.chart-value{',
      '.chart-day{',
      '.weekly-empty{',
      '.weekly-status-card{',
      '.weekly-status-cardstrong{',
      '.tl-body{min-width:0',
      '.tl-body{overflow-wrap:anywhere',
      '@media(max-width:560px)',
    ]

    /* 计划内工程化差异（精确白名单，仅此一对）：`.view.active` 的 viewIn
       fill `both → backwards`。fill:both 在动画结束后永久保留 translateY(0)
       终态，使 `.view` 成为 fixed 后代（.topbar、fx 粒子）的包含块，引发
       1080 视口横向溢出与完成特效错位；backwards 终态回归自然值，与原型
       视觉零差异。原因记录于 docs/ui-migration/visual/sprint-04-fidelity.md。 */
    const viewFillPrototype = '.view.active{animation:viewIn0.7svar(--ease-decay)both'
    const viewFillMigrated = '.view.active{animation:viewIn0.7svar(--ease-decay)backwards'

    /* 计划内 legacy 泄漏复位（精确白名单，原型无对应声明）：legacy
       style.css 的裸元素选择器 main{width:min(40rem,…)}/section{margin-top:2rem}/
       article{margin-top:2rem} 命中冻结页的 main.shell / section.view /
       article.task-card，需 class 级显式复位（layout.css / today.css），
       legacy 流程不受影响。原因记录于 sprint-04-fidelity.md「QA 发现并已修复的差异」。 */
    const legacyLeakOverrides = [
      '.shell{width:auto',
      '.view{margin-top:0',
      '.task-card{margin-top:0',
    ]

    const missing: string[] = []
    for (const [key, count] of prototypeCounts) {
      if (key === splitMediaRule) continue
      if (key === viewFillPrototype) continue
      if ((migratedCounts.get(key) ?? 0) < count) missing.push(key)
    }

    const extra: string[] = []
    for (const [key, count] of migratedCounts) {
      if (splitParts.includes(key)) continue
      if (runtimeKeyframes.some(prefix => key.startsWith(prefix))) continue
      if (key === viewFillMigrated) continue
      if (legacyLeakOverrides.includes(key)) continue
      if (weeklySprintExtras.some(prefix => key.startsWith(prefix))) continue
      if ((prototypeCounts.get(key) ?? 0) < count) extra.push(key)
    }

    expect(missing).toEqual([])
    expect(extra).toEqual([])
  })

  it('keeps every backdrop-filter declaration (with its -webkit- prefix where the prototype had one)', () => {
    const migrated = STYLE_FILES.map(readStyle).join('\n')
    expect(migrated.match(/[^-]backdrop-filter:/g)).toHaveLength(4)
    expect(migrated.match(/-webkit-backdrop-filter:/g)).toHaveLength(3)
  })

  it('freezes animations under prefers-reduced-motion', () => {
    expect(readStyle('accessibility')).toContain('@media (prefers-reduced-motion: reduce)')
    expect(readStyle('accessibility')).toContain('animation-duration: 0.01s !important')
  })
})

/* ---------- 3. effects 组件可 mount ---------- */

describe('visual system: effect components mount', () => {
  it('AuroraBackground renders the full background stack from the prototype', () => {
    const wrapper = mount(AuroraBackground)
    const root = wrapper.find('.bg')
    expect(root.exists()).toBe(true)
    expect(root.attributes('aria-hidden')).toBe('true')
    expect(wrapper.findAll('.blob')).toHaveLength(4)
    expect(wrapper.find('.blob.b1').exists()).toBe(true)
    expect(wrapper.find('.blob.b4').exists()).toBe(true)
    expect(wrapper.find('.bg-grid').exists()).toBe(true)
    expect(wrapper.find('#petalField').exists()).toBe(true)
    expect(wrapper.find('#dust').exists()).toBe(true)
    expect(wrapper.find('.bg-noise').exists()).toBe(true)
  })

  it('PetalField spawns 26 petals with per-petal gradient and spin', () => {
    const wrapper = mount(PetalField)
    const petals = wrapper.findAll('.petal')
    expect(petals).toHaveLength(26)
    const firstPetal = petals[0]!
    expect(firstPetal.find('svg').exists()).toBe(true)
    expect(firstPetal.find('path').attributes('d')).toBe('M20 2 C31 8 33 20 20 38 C7 20 9 8 20 2 Z')
    const svgStyle = firstPetal.find('svg').attributes('style') ?? ''
    expect(svgStyle).toContain('petalSpin')
    expect(firstPetal.find('linearGradient').exists()).toBe(true)
    /* mount 后应立即就位（带初始 transform），而非停留在 (0,0) */
    expect(firstPetal.attributes('style')).toContain('translate(')
  })

  it('DustField spawns 54 twinkling particles with prototype custom properties', () => {
    const wrapper = mount(DustField)
    const dust = wrapper.findAll('.dust')
    expect(dust).toHaveLength(54)
    const style = dust[0]!.attributes('style') ?? ''
    expect(style).toContain('--d:')
    expect(style).toContain('--delay:')
    expect(style).toContain('--o:')
    expect(style).toContain('box-shadow')
  })

  it('AssistantOrb renders breathing core with two counter-rotating petal rings', () => {
    const wrapper = mount(AssistantOrb)
    expect(wrapper.find('.orb').exists()).toBe(true)
    const rings = wrapper.findAll('.orb-ring')
    expect(rings).toHaveLength(2)
    expect(rings[1]!.classes()).toContain('r2')
    expect(wrapper.find('.orb-core').exists()).toBe(true)
    expect(wrapper.findAll('.op')).toHaveLength(2)
  })

  it('TaskCompletionFx renders nothing until played', () => {
    const wrapper = mount(TaskCompletionFx)
    expect(wrapper.find('.fx-p').exists()).toBe(false)
    expect(wrapper.find('.fx-orb').exists()).toBe(false)
    expect(wrapper.find('.fx-halo').exists()).toBe(false)
  })
})

/* ---------- 4. reduced-motion 双侧降级 ---------- */

type MediaListener = (event: { matches: boolean }) => void

function stubMatchMedia(initialMatches: boolean) {
  const listeners = new Set<MediaListener>()
  const state = { matches: initialMatches }
  const mql = {
    get matches() {
      return state.matches
    },
    media: '(prefers-reduced-motion: reduce)',
    addEventListener: (_type: string, listener: MediaListener) => listeners.add(listener),
    removeEventListener: (_type: string, listener: MediaListener) => listeners.delete(listener),
    addListener: (listener: MediaListener) => listeners.add(listener),
    removeListener: (listener: MediaListener) => listeners.delete(listener),
    dispatchChange(matches: boolean) {
      state.matches = matches
      for (const listener of listeners) listener({ matches })
    },
  }
  vi.stubGlobal('matchMedia', () => mql)
  return mql
}

describe('visual system: reduced motion', () => {
  it('useMotionPulse completes plays synchronously without scheduling any frame', () => {
    stubMatchMedia(true)
    const rafSpy = vi.spyOn(window, 'requestAnimationFrame')
    const { play, pulse } = useMotionPulse()

    const updates: Array<[number, number]> = []
    let done = 0
    play(600, (value, progress) => updates.push([value, progress]), () => {
      done += 1
    })

    expect(done).toBe(1)
    expect(updates).toHaveLength(1)
    /* 直接以脉冲终值回调（pulse(1) ≈ 0.011 的长尾残余，视觉上即静止） */
    expect(updates[0]![1]).toBe(1)
    expect(updates[0]![0]).toBeCloseTo(pulse(1), 12)
    expect(rafSpy).not.toHaveBeenCalled()
  })

  it('useDecorativeField reports reduce and refuses to start loops', () => {
    stubMatchMedia(true)
    const { reducedMotion, startLoop } = useDecorativeField()
    expect(reducedMotion.value).toBe(true)

    const frames: number[] = []
    const stop = startLoop(dt => frames.push(dt))
    stop()
    expect(frames).toEqual([])
  })

  it('useDecorativeField stops running loops the moment reduce switches on', () => {
    const mql = stubMatchMedia(false)
    const rafSpy = vi.spyOn(window, 'requestAnimationFrame')
    const cancelSpy = vi.spyOn(window, 'cancelAnimationFrame')
    const { reducedMotion, startLoop } = useDecorativeField()

    const frames: number[] = []
    const stop = startLoop(dt => frames.push(dt))
    expect(rafSpy).toHaveBeenCalled()

    mql.dispatchChange(true)
    expect(reducedMotion.value).toBe(true)
    expect(cancelSpy).toHaveBeenCalled()
    stop()
  })

  it('PetalField under reduce renders a static petal layer with no RAF loop', () => {
    stubMatchMedia(true)
    const rafSpy = vi.spyOn(window, 'requestAnimationFrame')
    const wrapper = mount(PetalField)
    expect(wrapper.findAll('.petal')).toHaveLength(26)
    expect(rafSpy).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('TaskCompletionFx under reduce skips the effect entirely', () => {
    stubMatchMedia(true)
    const rafSpy = vi.spyOn(window, 'requestAnimationFrame')
    const wrapper = mount(TaskCompletionFx)
    wrapper.vm.play(120, 80)
    expect(wrapper.find('.fx-p').exists()).toBe(false)
    expect(rafSpy).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})

/* ---------- 5. 生命周期泄漏 ---------- */

describe('visual system: lifecycle cleanup', () => {
  it('PetalField stops its RAF loop on unmount', async () => {
    const rafSpy = vi.spyOn(window, 'requestAnimationFrame')
    const cancelSpy = vi.spyOn(window, 'cancelAnimationFrame')

    const wrapper = mount(PetalField)
    await new Promise(resolve => setTimeout(resolve, 40))
    expect(rafSpy.mock.calls.length).toBeGreaterThan(0)

    wrapper.unmount()
    const countAtUnmount = rafSpy.mock.calls.length
    expect(cancelSpy).toHaveBeenCalled()

    /* 卸载后即使再等若干帧，也不应出现新的调度 */
    await new Promise(resolve => setTimeout(resolve, 60))
    expect(rafSpy.mock.calls.length).toBe(countAtUnmount)
  })

  it('TaskCompletionFx cancels its frames and timers on unmount mid-effect', async () => {
    const rafSpy = vi.spyOn(window, 'requestAnimationFrame')
    const cancelSpy = vi.spyOn(window, 'cancelAnimationFrame')
    const clearTimeoutSpy = vi.spyOn(globalThis, 'clearTimeout')

    const wrapper = mount(TaskCompletionFx)
    wrapper.vm.play(200, 160)
    await new Promise(resolve => setTimeout(resolve, 5))

    expect(wrapper.findAll('.fx-p')).toHaveLength(16)
    const rafScheduled = rafSpy.mock.calls.length
    expect(rafScheduled).toBeGreaterThan(0)

    wrapper.unmount()
    expect(cancelSpy).toHaveBeenCalled()
    expect(clearTimeoutSpy).toHaveBeenCalled()

    const rafAtUnmount = rafSpy.mock.calls.length
    await new Promise(resolve => setTimeout(resolve, 60))
    expect(rafSpy.mock.calls.length).toBe(rafAtUnmount)
  })

  it('useMotionPulse cancels outstanding plays when the component scope disposes', async () => {
    const cancelSpy = vi.spyOn(window, 'cancelAnimationFrame')
    let exposedPlay: ((duration: number, onUpdate: (v: number, t: number) => void) => void) | null = null

    const host = mount({
      setup() {
        const { play } = useMotionPulse()
        exposedPlay = (duration, onUpdate) => {
          play(duration, onUpdate)
        }
        return () => null
      },
    })

    let updates = 0
    exposedPlay!(1000, () => {
      updates += 1
    })
    await new Promise(resolve => setTimeout(resolve, 30))
    expect(updates).toBeGreaterThan(0)

    const updatesAtUnmount = updates
    host.unmount()
    expect(cancelSpy).toHaveBeenCalled()
    await new Promise(resolve => setTimeout(resolve, 50))
    expect(updates).toBe(updatesAtUnmount)
  })
})

/* ---------- 脉冲数学与原型逐字等价 ---------- */

describe('visual system: pulse math parity with prototype WL', () => {
  it('matches rise / decay / pulse values', () => {
    const { rise, decay, pulse } = useMotionPulse()
    /* WL.rise(t) = t^3 */
    expect(rise(0.5)).toBeCloseTo(0.125, 12)
    /* WL.decay(t) = Math.exp(-4.5 * t) */
    expect(decay(0.5)).toBeCloseTo(Math.exp(-2.25), 12)
    /* 上升段 0→20%，衰减段 20%→100% */
    expect(pulse(0)).toBe(0)
    expect(pulse(-1)).toBe(0)
    expect(pulse(0.1)).toBeCloseTo(0.125, 12)
    expect(pulse(0.2)).toBeCloseTo(1, 12)
    expect(pulse(0.6)).toBeCloseTo(Math.exp(-4.5 * 0.5), 12)
    expect(pulse(1)).toBeCloseTo(Math.exp(-4.5), 12)
  })
})
