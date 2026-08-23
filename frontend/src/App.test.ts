import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'

import App from './App.vue'
import * as api from './api/client'

/* ------------------------------------------------------------------
   Sprint 4：App 默认运行态 = Shell + TodayView（fixture demo，无 API）；
   legacy 表单流保留在 ?legacy=1 之后（Sprint 9 移除）。
   ------------------------------------------------------------------ */

/* 完成任务会触发 TaskCompletionFx 的真实 RAF/timeout（最长 780ms delay）；
   不 unmount 会让定时器活过环境 teardown，偶发 unhandled error。
   autoUnmount 触发组件 onUnmounted → useMotionPulse.dispose() 清理。 */
enableAutoUnmount(afterEach)

function openLegacy(): void {
  window.history.pushState({}, '', '/?legacy=1')
}

function resetUrl(): void {
  window.history.pushState({}, '', '/')
}

describe('App shell runtime (default)', () => {
  afterEach(resetUrl)

  it('mounts the frozen shell navigation with TodayView as the active page', async () => {
    resetUrl()
    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.find('nav.navbar').exists()).toBe(true)
    expect(wrapper.get('[data-view="today"]').classes()).toContain('active')
    expect(wrapper.get('.hero').exists()).toBe(true)
    expect(wrapper.get('.hero-tag').text()).toBe('✦ 春日极光 · 期中考试周 · 第 2 天')
    expect(wrapper.findAll('.task-card')).toHaveLength(3)
  })

  it('renders structural placeholders for unmigrated views without business data', async () => {
    resetUrl()
    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.get('[data-view-pending="assistant"]').text()).toContain('问问薇薇')
    expect(wrapper.get('[data-view-pending="profile"]').text()).toContain('我的画像')
    expect(wrapper.get('[data-view-pending="weekly"]').text()).toContain('周度变化')
    /* 未迁移页面不得出现假业务数据（无任务卡 / 无图表 / 无对话） */
    const pending = wrapper.get('[data-view-pending="assistant"]')
    expect(pending.find('.task-card').exists()).toBe(false)
    expect(pending.find('.q-bubble').exists()).toBe(false)
  })

  it('never touches the API in the demo runtime', async () => {
    resetUrl()
    const health = vi.spyOn(api, 'healthCheck').mockResolvedValue({ status: 'ok' })
    mount(App)
    await flushPromises()

    expect(health).not.toHaveBeenCalled()
  })

  it('syncs the docked topbar progress from the Today local state', async () => {
    resetUrl()
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

describe('App legacy console (gated behind ?legacy=1)', () => {
  beforeEach(openLegacy)
  afterEach(resetUrl)

  it('shows the connected state after a successful health check', async () => {
    vi.spyOn(api, 'healthCheck').mockResolvedValue({ status: 'ok' })

    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.text()).toContain('服务已连接')
  })

  it('shows a recoverable failure state instead of a blank screen', async () => {
    vi.spyOn(api, 'healthCheck').mockRejectedValue(
      new api.ApiError(0, '无法连接服务', 'network_error'),
    )

    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.text()).toContain('微律')
    expect(wrapper.text()).toContain('暂时无法连接服务')
    expect(wrapper.get('button').text()).toBe('重新连接')
  })

  it('runs health check again after clicking reconnect', async () => {
    const health = vi
      .spyOn(api, 'healthCheck')
      .mockRejectedValueOnce(new api.ApiError(0, '无法连接服务', 'network_error'))
      .mockResolvedValueOnce({ status: 'ok' })

    const wrapper = mount(App)
    await flushPromises()
    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(health).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('服务已连接')
  })
})
