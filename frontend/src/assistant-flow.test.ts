import { enableAutoUnmount, mount } from '@vue/test-utils'
import { nextTick } from 'vue'

import AssistantView from './views/AssistantView.vue'
import { assistantFixture } from './data/fixtures/assistant.fixture'

enableAutoUnmount(afterEach)

async function advance(ms: number): Promise<void> {
  await vi.advanceTimersByTimeAsync(ms)
  await nextTick()
}

describe('Assistant demo flow', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('runs the fixture pipeline in order and keeps the demo flag visible', async () => {
    const wrapper = mount(AssistantView, { props: { model: assistantFixture } })

    expect(wrapper.get('[data-testid="demo-badge"]').text()).toContain('演示模式 · 固定模板，不会请求真实 Agentic RAG')
    expect(wrapper.attributes('data-trace-real')).toBe('false')

    await wrapper.get('[data-prompt="exam"]').trigger('click')
    expect(wrapper.get('[data-testid="user-message"]').text()).toBe('考试周好累，只有 10 分钟')
    expect(wrapper.get('[data-stage="analysis"]').classes()).toContain('pending')

    await advance(700)
    expect(wrapper.get('[data-stage-card="analysis"]').exists()).toBe(true)
    expect(wrapper.get('[data-stage="analysis"]').classes()).toContain('active')

    await advance(750)
    expect(wrapper.get('[data-stage-card="analysis"]').text()).toContain('已拆解 2 个方向')
    expect(wrapper.get('[data-stage="retrieval"]').classes()).toContain('active')
    expect(wrapper.find('[data-stage-card="retrieval"]').exists()).toBe(false)

    await advance(850)
    expect(wrapper.get('[data-stage-card="retrieval"]').exists()).toBe(true)

    await advance(850)
    expect(wrapper.get('[data-stage="answer"]').classes()).toContain('active')
    expect(wrapper.find('[data-testid="answer-card"]').exists()).toBe(false)

    await advance(900)
    expect(wrapper.get('[data-testid="answer-card"]').text()).toContain('10 分钟')
    expect(wrapper.get('[data-testid="suggested-mini-task"] button').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-stage="answer"]').classes()).toContain('done')
  })

  it('ignores a second submit while the first run is busy', async () => {
    const wrapper = mount(AssistantView, { props: { model: assistantFixture } })
    const prompt = wrapper.get('[data-prompt="exam"]')

    await prompt.trigger('click')
    await prompt.trigger('click')

    expect(wrapper.findAll('[data-testid="user-message"]')).toHaveLength(1)
    expect(wrapper.get('[data-testid="chat-submit"]').attributes('disabled')).toBeDefined()
    await advance(700)
    expect(wrapper.findAll('[data-stage-card="analysis"]')).toHaveLength(1)
  })

  it('sends every manual question to the fallback fixture without keyword routing', async () => {
    const wrapper = mount(AssistantView, { props: { model: assistantFixture } })

    await wrapper.get('[data-testid="chat-input"]').setValue('我脖子有点疼')
    await wrapper.get('[data-testid="chat-composer"]').trigger('submit')
    await advance(700 + 700 + 800 + 800 + 800)

    expect(wrapper.get('[data-stage-card="analysis"]').text()).toContain('我脖子有点疼')
    expect(wrapper.get('[data-testid="answer-card"]').text()).toContain('最小的事')
    expect(wrapper.find('[data-testid="safety-notice"]').exists()).toBe(false)
  })

  it('keeps the frozen greeting paragraph break and safety prompt punctuation', async () => {
    const wrapper = mount(AssistantView, { props: { model: assistantFixture } })

    expect(wrapper.findAll('.greeting-card .answer-text br')).toHaveLength(2)

    await wrapper.get('[data-prompt="neck"]').trigger('click')

    expect(wrapper.get('[data-testid="user-message"]').text()).toBe('我脖子有点疼。')
  })

  it('clears all demo timers when the view unmounts', async () => {
    const clearTimeoutSpy = vi.spyOn(globalThis, 'clearTimeout')
    const wrapper = mount(AssistantView, { props: { model: assistantFixture } })

    await wrapper.get('[data-prompt="exam"]').trigger('click')
    wrapper.unmount()

    expect(clearTimeoutSpy).toHaveBeenCalled()
  })

  it('does not yank the page when the user has scrolled up', async () => {
    Object.defineProperty(window, 'innerHeight', { configurable: true, value: 720 })
    Object.defineProperty(window, 'scrollY', { configurable: true, value: 0 })
    Object.defineProperty(document.documentElement, 'scrollHeight', { configurable: true, value: 2000 })
    Object.defineProperty(document.body, 'scrollHeight', { configurable: true, value: 2000 })

    const wrapper = mount(AssistantView, { props: { model: assistantFixture } })
    const scrollIntoView = vi.fn()
    Object.defineProperty(wrapper.get('[data-testid="latest-message"]').element, 'scrollIntoView', {
      configurable: true,
      value: scrollIntoView,
    })

    window.dispatchEvent(new Event('scroll'))

    await wrapper.get('[data-prompt="exam"]').trigger('click')
    await nextTick()

    expect(scrollIntoView).not.toHaveBeenCalled()
  })
})
