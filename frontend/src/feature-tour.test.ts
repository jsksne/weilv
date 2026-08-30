import { afterEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import FeatureTour from './components/tour/FeatureTour.vue'

afterEach(() => {
  window.localStorage.clear()
  vi.useRealTimers()
  document.body.innerHTML = ''
})

function mountTour() {
  const navigate = vi.fn()
  const wrapper = mount(FeatureTour, { props: { navigate } })
  return { wrapper, navigate }
}

describe('FeatureTour（新手教程）', () => {
  it('runs once, marks the local flag on finish, and emits done', async () => {
    vi.useFakeTimers()
    document.body.innerHTML = `
      <section class="view active" data-view="today">
        <div data-testid="hero-progress"></div>
      </section>
    `
    const { wrapper } = mountTour()
    expect(wrapper.find('[data-testid="feature-tour"]').exists()).toBe(false)

    wrapper.vm.start()
    await flushPromises()
    await vi.advanceTimersByTimeAsync(400)

    expect(wrapper.find('[data-testid="feature-tour"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('今日 · 进度')
    expect(window.localStorage.getItem('weilv-tour-done')).toBeNull()

    await wrapper.get('[data-action="tour-skip"]').trigger('click')
    expect(wrapper.find('[data-testid="feature-tour"]').exists()).toBe(false)
    expect(window.localStorage.getItem('weilv-tour-done')).toBe('1')
    expect(wrapper.emitted('done')).toHaveLength(1)
  })

  it('does not auto-report done before the user finishes', async () => {
    vi.useFakeTimers()
    document.body.innerHTML = `
      <section class="view active" data-view="today">
        <div data-testid="hero-progress"></div>
      </section>
    `
    const { wrapper } = mountTour()
    wrapper.vm.start()
    await flushPromises()
    await vi.advanceTimersByTimeAsync(400)

    expect(wrapper.emitted('done')).toBeUndefined()
    expect(wrapper.find('[data-testid="feature-tour"]').exists()).toBe(true)
  })

  it('navigates to the step view when the target lives on another page', async () => {
    vi.useFakeTimers()
    document.body.innerHTML = `
      <section class="view active" data-view="today">
        <div data-testid="hero-progress"></div>
      </section>
      <section class="view" data-view="assistant">
        <div class="ask-hero"></div>
      </section>
    `
    const { wrapper, navigate } = mountTour()
    wrapper.vm.start()
    await flushPromises()
    await vi.advanceTimersByTimeAsync(400)
    expect(navigate).not.toHaveBeenCalled()

    /* 走到 assistant 第一步（index 6）：目标在另一页，应触发切页回调。 */
    for (let i = 0; i < 6; i += 1) {
      await wrapper.get('[data-action="tour-next"]').trigger('click')
      await vi.advanceTimersByTimeAsync(400)
    }
    expect(navigate).toHaveBeenCalledWith('assistant')
  })
})
