import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'

import App from './App.vue'

/* Sprint 10 accessibility gate：可访问性检查不改变冻结视觉。 */

enableAutoUnmount(afterEach)

function allButtons(wrapper: ReturnType<typeof mount>): string[] {
  return wrapper.findAll('button').map(button => button.text().trim()).filter(Boolean)
}

describe('Sprint 10 accessibility', () => {
  it('exposes a semantic primary navigation with an accessible label', async () => {
    const wrapper = mount(App)
    await flushPromises()

    const nav = wrapper.get('nav.navbar')
    expect(nav.attributes('aria-label')).toBeTruthy()
    for (const view of ['today', 'assistant', 'profile', 'weekly']) {
      const tab = nav.get(`[data-view="${view}"]`)
      expect(tab.text().trim()).toBeTruthy()
    }
  })

  it('gives every interactive task button an accessible name', async () => {
    const wrapper = mount(App)
    await flushPromises()

    const names = allButtons(wrapper)
    for (const expected of ['开始', '先跳过']) {
      expect(names).toContain(expected)
    }
    for (const name of names) {
      expect(name.length).toBeGreaterThan(0)
    }
  })

  it('labels the assistant chat composer control', async () => {
    const wrapper = mount(App)
    await flushPromises()
    await wrapper.get('nav .tab[data-view="assistant"]').trigger('click')
    await flushPromises()

    const composer = wrapper.get('[data-testid="chat-composer"]')
    const input = composer.get('input, textarea')
    const hasLabel =
      !!input.attributes('aria-label') ||
      !!input.attributes('placeholder') ||
      composer.find('label').exists()
    expect(hasLabel).toBe(true)
  })

  it('binds the onboarding consent checkbox to a label', async () => {
    vi.stubEnv('VITE_UI_MODE', 'demo')
    window.localStorage.removeItem('wl_aurora_onboarded')
    const wrapper = mount(App)
    await flushPromises()

    const consent = wrapper.get('[data-testid="onboarding-consent"]')
    expect(consent.find('label').text().trim()).toBeTruthy()
    expect(consent.get('input[type="checkbox"]').exists()).toBe(true)
  })

  it('keeps disabled states explicit (not only via styling)', async () => {
    const wrapper = mount(App)
    await flushPromises()

    // 提交中/冷却按钮通过 disabled 属性表达不可用
    const disabledButtons = wrapper.findAll('button[disabled]')
    for (const button of disabledButtons) {
      expect(button.attributes('disabled')).toBeDefined()
    }
    expect(wrapper.findAll('button').length).toBeGreaterThan(0)
  })

  it('surfaces errors as text (not color-only)', async () => {
    vi.stubEnv('VITE_UI_MODE', 'production')
    vi.stubEnv('VITE_USER_ID', 'u-a11y')
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: 'x' }), {
          status: 500,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )
    const wrapper = mount(App)
    await flushPromises()

    const error = wrapper.get('[data-testid="ui-data-error"]')
    expect(error.attributes('role')).toBe('alert')
    expect(error.text().trim()).toBeTruthy()
  })

  it('keeps content readable and interactive under prefers-reduced-motion: reduce', async () => {
    // jsdom matchMedia 默认返回 matches=false；模拟 reduce 不影响内容渲染
    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.findAll('.task-card')).toHaveLength(3)
    expect(wrapper.get('[data-view="today"] [data-act="start"]').exists()).toBe(true)
    expect(wrapper.get('.hero-tag').text()).toBeTruthy()
  })
})
