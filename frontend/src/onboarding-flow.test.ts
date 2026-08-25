import { enableAutoUnmount, mount } from '@vue/test-utils'

import OnboardingFlow from './components/onboarding/OnboardingFlow.vue'
import { onboardingFixture } from './data/fixtures/onboarding.fixture'
import { useToast } from './composables/useToast'

enableAutoUnmount(afterEach)

function useReducedMotion(): void {
  vi.stubGlobal('matchMedia', () => ({
    matches: true,
    media: '(prefers-reduced-motion: reduce)',
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }))
}

describe('Sprint 6 OnboardingFlow', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  afterEach(() => {
    useToast().clear()
    vi.useRealTimers()
  })

  it('supports Next and Back across the five-step Demo flow', async () => {
    const wrapper = mount(OnboardingFlow, { props: { model: onboardingFixture } })

    expect(wrapper.findAll('[data-testid="onboarding-progress"] i')).toHaveLength(5)
    expect(wrapper.get('[data-onboarding-step="welcome"]').exists()).toBe(true)

    await wrapper.get('[data-action="onboarding-next"]').trigger('click')
    expect(wrapper.get('[data-onboarding-step="basics"]').exists()).toBe(true)

    await wrapper.get('[data-action="onboarding-back"]').trigger('click')
    expect(wrapper.get('[data-onboarding-step="welcome"]').exists()).toBe(true)
  })

  it('keeps questionnaire mismatch visible and Skip writes only the Demo completion marker', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    const wrapper = mount(OnboardingFlow, { props: { model: onboardingFixture } })

    expect(wrapper.get('[data-testid="questionnaire-contract-status"]').text()).toContain('不会提交')
    await wrapper.get('[data-action="onboarding-skip"]').trigger('click')

    expect(wrapper.emitted('complete')).toEqual([['skipped']])
    expect(window.localStorage.getItem('wl_aurora_onboarded')).toBe('1')
    expect(window.localStorage.getItem('grade')).toBeNull()
    expect(fetchSpy).not.toHaveBeenCalled()
    expect(useToast().toasts.value.map(toast => toast.message)).toEqual(['欢迎使用微律'])
  })

  it('completes all five steps, runs generation, and never submits answers', async () => {
    vi.useFakeTimers()
    useReducedMotion()
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    const wrapper = mount(OnboardingFlow, { props: { model: onboardingFixture } })

    await wrapper.get('[data-action="onboarding-next"]').trigger('click')
    await wrapper.get('[data-option="junior_high"]').trigger('click')
    expect(wrapper.get('[data-option="junior_high"]').classes()).toContain('on')

    await wrapper.get('[data-action="onboarding-next"]').trigger('click')
    expect(wrapper.get('[data-onboarding-step="issues"]').exists()).toBe(true)
    await wrapper.get('[data-option="tired_eyes"]').trigger('click')
    expect(wrapper.get('[data-option="tired_eyes"]').classes()).not.toContain('on')

    await wrapper.get('[data-action="onboarding-next"]').trigger('click')
    expect(wrapper.get('[data-onboarding-step="behavior"]').exists()).toBe(true)
    await wrapper.get('[data-action="onboarding-next"]').trigger('click')
    expect(wrapper.get('[data-onboarding-step="generation"]').exists()).toBe(true)

    await vi.advanceTimersByTimeAsync(1000)
    expect(wrapper.get('.ob-summary').text()).toContain('画像已生成')

    await wrapper.get('[data-action="onboarding-next"]').trigger('click')
    expect(wrapper.emitted('complete')).toEqual([['completed']])
    expect(window.localStorage.getItem('wl_aurora_onboarded')).toBe('1')
    expect(window.localStorage.getItem('grade')).toBeNull()
    expect(fetchSpy).not.toHaveBeenCalled()
  })
})
