import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'

import App from './App.vue'
import * as api from './api/client'

/* ------------------------------------------------------------------
   Sprint 4+：App 默认运行态 = Shell + TodayView（fixture demo，无 API）。
   Sprint 9.1：?legacy=1 已移除 —— 不存在第二条 runtime UI path。
   ------------------------------------------------------------------ */

/* 完成任务会触发 TaskCompletionFx 的真实 RAF/timeout（最长 780ms delay）；
   不 unmount 会让定时器活过环境 teardown，偶发 unhandled error。
   autoUnmount 触发组件 onUnmounted → useMotionPulse.dispose() 清理。 */
enableAutoUnmount(afterEach)

describe('App shell runtime (default)', () => {
  it('mounts the frozen shell navigation with TodayView as the active page', async () => {
    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.find('nav.navbar').exists()).toBe(true)
    expect(wrapper.get('[data-view="today"]').classes()).toContain('active')
    expect(wrapper.get('.hero').exists()).toBe(true)
    expect(wrapper.get('.hero-tag').text()).toBe('✦ 健康微行动 · 期中考试周 · 第 2 天')
    expect(wrapper.findAll('.task-card')).toHaveLength(3)
  })

  it('renders Assistant and the migrated Profile view', async () => {
    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.get('[data-view="assistant"] .ask-wrap').exists()).toBe(true)
    expect(wrapper.get('[data-testid="demo-badge"]').text()).toContain('演示模式 · 固定模板，不会请求真实 Agentic RAG')
    expect(wrapper.get('[data-view="profile"] [data-testid="profile-view"]').exists()).toBe(true)
    expect(wrapper.findAll('[data-view="profile"] [data-profile-section]')).toHaveLength(4)
  })

  it('never touches the API in the demo runtime', async () => {
    const health = vi.spyOn(api, 'healthCheck').mockResolvedValue({ status: 'ok' })
    mount(App)
    await flushPromises()

    expect(health).not.toHaveBeenCalled()
  })

  it('opens and focuses the matching Today task from an Assistant suggestion', async () => {
    vi.useFakeTimers()
    try {
      vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
      /* attachTo：jsdom 只对已连接文档的元素生效 focus()；
         未连接的 test-utils 树里 focus 是 no-op。 */
      const wrapper = mount(App, { attachTo: document.body })
      await wrapper.get('nav .tab[data-view="assistant"]').trigger('click')
      await wrapper.get('[data-prompt="exam"]').trigger('click')
      await vi.advanceTimersByTimeAsync(4050)
      await flushPromises()

      expect(wrapper.get('[data-testid="docked-progress"] .tb-num').text()).toBe('0 / 3')
      const target = wrapper.get('[data-task-id="today-task-move-neck-stretch"]')
      Object.defineProperty(target.element, 'scrollIntoView', {
        configurable: true,
        value: vi.fn(),
      })

      await wrapper.get('[data-testid="suggested-mini-task"] button').trigger('click')
      await flushPromises()

      expect(wrapper.get('[data-view="today"]').classes()).toContain('active')
      expect(document.activeElement).toBe(target.element)
    } finally {
      vi.useRealTimers()
    }
  })

  it('syncs the docked topbar progress from the Today local state', async () => {
    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.get('[data-testid="docked-progress"] .tb-num').text()).toBe('0 / 3')
    const card = wrapper.findAll('.task-card')[0]!
    await card.get('[data-act="start"]').trigger('click')
    /* 越过 450ms 同位换钮冷却：冷却时钟为 performance.now，
       vitest fake timers 默认不接管它，需要单独 mock 并手动推进 */
    const startedAt = performance.now()
    const nowSpy = vi.spyOn(performance, 'now').mockImplementation(() => startedAt + 500)
    try {
      await card.get('[data-act="done"]').trigger('click')

      expect(card.classes()).toContain('done')
      expect(wrapper.get('.progress-num').text()).toContain('1')
      expect(wrapper.get('[data-testid="docked-progress"] .tb-num').text()).toBe('1 / 3')
    } finally {
      nowSpy.mockRestore()
    }
  })
})

describe('Sprint 9.1 legacy runtime removal', () => {
  it('ignores ?legacy=1 and always mounts the four-view application with Today default', async () => {
    window.history.pushState({}, '', '/?legacy=1')
    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.find('nav.navbar').exists()).toBe(true)
    expect(wrapper.get('[data-view="today"]').classes()).toContain('active')
    expect(wrapper.find('[data-testid="questionnaire"]').exists()).toBe(false)
    expect(wrapper.findAll('.task-card')).toHaveLength(3)
  })

  it('no longer imports or branches on the legacy console from the runtime entry', () => {
    const appSource = readFileSync(join(process.cwd(), 'src', 'App.vue'), 'utf8')
    expect(appSource).not.toMatch(/URLSearchParams/)
    expect(appSource).not.toMatch(/location\.search/)
    expect(appSource).not.toMatch(/legacy/i)
    expect(appSource).not.toContain('LegacyConsole')
  })

  it('retains the old source files in the repository without mounting them', () => {
    expect(existsSync(join(process.cwd(), 'src', 'views', 'LegacyConsole.vue'))).toBe(true)
  })
})
