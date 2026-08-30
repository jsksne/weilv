import { nextTick } from 'vue'
import { enableAutoUnmount, mount } from '@vue/test-utils'

import AppShell from './layouts/AppShell.vue'
import DustField from './components/effects/DustField.vue'
import PetalField from './components/effects/PetalField.vue'
import TaskCompletionFx from './components/effects/TaskCompletionFx.vue'
import { shellFixture } from './data/fixtures/shell.fixture'

/* ------------------------------------------------------------------
   Sprint 3：冻结视觉系统在真实 AppShell 的挂载与两项 FUTURE 修复
   ------------------------------------------------------------------ */

enableAutoUnmount(afterEach)

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

describe('Sprint 3 AppShell visual mount', () => {
  it('mounts the full frozen background stack inside the real AppShell (shell mode)', () => {
    const wrapper = mount(AppShell, {
      props: { shell: shellFixture },
      slots: { today: '<p data-testid="today-view">Today</p>' },
    })

    const bg = wrapper.find('.bg')
    expect(bg.exists()).toBe(true)
    expect(bg.attributes('aria-hidden')).toBe('true')
    expect(wrapper.findAll('.blob')).toHaveLength(4)
    expect(wrapper.findAll('.petal')).toHaveLength(26)
    expect(wrapper.findAll('.dust')).toHaveLength(54)
    expect(wrapper.find('.bg-grid').exists()).toBe(true)
    expect(wrapper.find('.bg-noise').exists()).toBe(true)
    /* 原型 .bg 是 body 的第一个子元素，内容层（navbar/shell）必须位于其后 */
    expect(wrapper.element.firstElementChild?.classList.contains('bg')).toBe(true)
    /* IconSprite 随 Shell 挂载 */
    expect(wrapper.findAll('symbol').map(symbol => symbol.attributes('id'))).toEqual([
      'i-flower',
      'i-moon',
      'i-clock',
      'i-leaf',
      'i-target',
      'i-book',
    ])
  })

  it('keeps the frozen background layer mounted for the legacy runtime too', () => {
    const wrapper = mount(AppShell, {
      slots: { default: '<form data-testid="legacy-form"><button>旧业务</button></form>' },
    })

    expect(wrapper.find('.bg').exists()).toBe(true)
    expect(wrapper.findAll('.blob')).toHaveLength(4)
    /* legacy 静态内容由包装层抬到背景层之上（原型内容层级 z-index 1 约定） */
    const content = wrapper.find('.shell-content')
    expect(content.exists()).toBe(true)
    expect(content.find('[data-testid="legacy-form"]').exists()).toBe(true)
  })
})

describe('Sprint 3 FUTURE-S3-02: petal spin duration keeps one decimal', () => {
  it('rounds every spin duration to one decimal in the frozen 5.0~11.0 range', () => {
    const randomSpy = vi.spyOn(Math, 'random')

    for (const seed of [0, 0.123456789, 0.3333333333, 0.5, 0.7777777, 0.999999]) {
      randomSpy.mockReturnValue(seed)
      const wrapper = mount(PetalField)
      const svgs = wrapper.findAll('.petal svg')
      expect(svgs).toHaveLength(26)
      for (const svg of svgs) {
        const match = (svg.attributes('style') ?? '').match(/petalSpin ([\d.]+)s/)
        expect(match).not.toBeNull()
        const seconds = Number(match![1])
        /* 一位小数：×10 后必为整数；原型分布 5.0 ~ 11.0 秒 */
        expect(Number.isInteger(seconds * 10)).toBe(true)
        expect(seconds).toBeGreaterThanOrEqual(5)
        expect(seconds).toBeLessThanOrEqual(11)
      }
      wrapper.unmount()
      vi.clearAllMocks()
    }
    randomSpy.mockRestore()
  })

  it('does not change the underlying 5 + random * 6 distribution', () => {
    const randomSpy = vi.spyOn(Math, 'random').mockReturnValue(0.4999999)
    const wrapper = mount(PetalField)
    const style = wrapper.find('.petal svg').attributes('style') ?? ''
    /* (5 + 0.4999999 * 6).toFixed(1) === '8.0'，而非长尾浮点 */
    expect(style).toContain('petalSpin 8s')
    randomSpy.mockRestore()
  })
})

describe('Sprint 3 FUTURE-S3-01: TaskCompletionFx resets mid-flight on reduced motion', () => {
  it('start → reduce ON → FX cleared and idle → reduce OFF → play works again', async () => {
    const mql = stubMatchMedia(false)
    const rafSpy = vi.spyOn(window, 'requestAnimationFrame')
    const wrapper = mount(TaskCompletionFx)

    wrapper.vm.play(2000, 160)
    await new Promise(resolve => setTimeout(resolve, 5))
    expect(document.body.querySelectorAll('.fx-p')).toHaveLength(16)
    expect(rafSpy.mock.calls.length).toBeGreaterThan(0)

    /* 播放途中系统切到 prefers-reduced-motion：取消动画、清空瞬态 FX、复位 running */
    mql.dispatchChange(true)
    await nextTick()
    expect(document.body.querySelectorAll('.fx-p')).toHaveLength(0)
    expect(document.body.querySelector('.fx-orb')).toBeNull()
    expect(document.body.querySelector('.fx-halo')).toBeNull()
    const rafAtReset = rafSpy.mock.calls.length
    await new Promise(resolve => setTimeout(resolve, 40))
    expect(rafSpy.mock.calls.length).toBe(rafAtReset)

    /* 恢复 motion 后组件仍然可用：play() 重新生效 */
    mql.dispatchChange(false)
    await nextTick()
    wrapper.vm.play(2000, 160)
    await new Promise(resolve => setTimeout(resolve, 5))
    expect(document.body.querySelectorAll('.fx-p')).toHaveLength(16)
    expect(rafSpy.mock.calls.length).toBeGreaterThan(rafAtReset)
  })

  it('teleports all transient layers to body and anchors particles to the supplied center', async () => {
    const wrapper = mount(TaskCompletionFx)

    wrapper.vm.play(200, 160)
    await nextTick()

    const particles = [...document.body.querySelectorAll<HTMLElement>('.fx-p')]
    expect(particles).toHaveLength(16)
    expect(particles.every(particle => particle.parentElement === document.body)).toBe(true)

    const first = particles[0]!
    const left = Number.parseFloat(first.style.left)
    const top = Number.parseFloat(first.style.top)
    const width = Number.parseFloat(first.style.width)
    const height = Number.parseFloat(first.style.height)
    expect(left + width / 2).toBeCloseTo(200, 4)
    expect(top + height / 2).toBeCloseTo(160, 4)

    await new Promise(resolve => setTimeout(resolve, 800))
    expect(document.body.querySelector('.fx-orb')?.parentElement).toBe(document.body)
    expect(document.body.querySelector('.fx-halo')?.parentElement).toBe(document.body)

    wrapper.unmount()
  })
})

describe('Sprint 3 decorative field counts under the shell fixture', () => {
  it('keeps the frozen particle counts (26 petals / 54 dust) from mounted components', () => {
    const petals = mount(PetalField)
    expect(petals.findAll('.petal')).toHaveLength(26)
    const dust = mount(DustField)
    expect(dust.findAll('.dust')).toHaveLength(54)
  })
})
