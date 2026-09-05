import { afterEach } from 'vitest'
import { mount } from '@vue/test-utils'

import OnboardingFlow from './components/onboarding/OnboardingFlow.vue'
import { useOnboarding } from './composables/useOnboarding'
import { ApiUiDataSource } from './data/apiUiDataSource'
import { FixtureUiDataSource } from './data/fixtureUiDataSource'
import { createProductionOnboardingContract } from './data/adapters'
import { useToast } from './composables/useToast'
import { allowedRecommendation } from './test/recommendationFixtures'

afterEach(() => {
  vi.unstubAllGlobals()
  useToast().clear()
  vi.useRealTimers()
})

function okProfile(): Response {
  return new Response(
    JSON.stringify({
      user_id: 'u-1',
      target_stage: 'junior_high',
      memory_enabled: true,
      created_at: '2026-08-24T00:00:00+00:00',
      updated_at: '2026-08-24T00:00:00+00:00',
    }),
    { status: 200, headers: { 'Content-Type': 'application/json' } },
  )
}

function requestBody(call: unknown[]): unknown {
  return JSON.parse(String((call[1] as RequestInit).body))
}

function useReducedMotion(): void {
  vi.stubGlobal('matchMedia', () => ({
    matches: true,
    media: '(prefers-reduced-motion: reduce)',
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }))
}

describe('B6 Production onboarding contract', () => {
  it('keeps five steps and offers exactly the three supported student stages', () => {
    const model = createProductionOnboardingContract()

    expect(model.state.mode).toBe('production')
    expect(model.state.status).toBe('ready')
    expect(model.phase).toBe('ready')
    expect(model.steps).toHaveLength(5)
    expect(model.steps.map(step => step.id)).toEqual([
      'welcome',
      'basics',
      'issues',
      'behavior',
      'generation',
    ])

    const basics = model.steps.find(step => step.id === 'basics')
    const gradeGroup = basics && 'groups' in basics
      ? basics.groups?.find(group => group.id === 'grade')
      : undefined
    expect(gradeGroup?.options.map(option => option.value)).toEqual([
      'primary_upper',
      'junior_high',
      'senior_high',
    ])
  })

  it('persists only grade and memory consent; sleep/issues/duration/slot stay unavailable', () => {
    const model = createProductionOnboardingContract()

    const persisted = model.persistence.filter(report => report.status === 'persisted').map(report => report.fieldId)
    expect(persisted.sort()).toEqual(['grade', 'memory_enabled'])
    for (const field of ['sleep', 'issues', 'duration', 'slot']) {
      expect(model.persistence.find(report => report.fieldId === field)?.status).toBe('unavailable')
    }
    expect(model.questionnaire.status).toBe('unavailable')
    expect(model.consent.prompt).toBeTruthy()
  })
})

describe('B6 ApiUiDataSource.submitOnboarding', () => {
  it('writes grade + explicit consent to the Profile API (and only that)', async () => {
    const fetchMock = vi.fn().mockResolvedValue(okProfile())
    vi.stubGlobal('fetch', fetchMock)
    const source = new ApiUiDataSource({ userId: 'u-1' })

    const result = await source.submitOnboarding({ grade: 'junior_high', memoryEnabled: true })

    expect(result.status).toBe('completed')
    const [url, init] = fetchMock.mock.calls[0]!
    expect(String(url)).toContain('/api/v1/users/u-1/profile')
    expect((init as RequestInit).method).toBe('PUT')
    expect(requestBody(fetchMock.mock.calls[0]!)).toEqual({
      target_stage: 'junior_high',
      memory_enabled: true,
    })
    // 不发送旧 7 题问卷 answers、不写 sleep/issues。
    expect(JSON.stringify(init)).not.toContain('questionnaire')
    expect(JSON.stringify(init)).not.toContain('sleep')
    expect(JSON.stringify(init)).not.toContain('issues')
    expect(JSON.stringify(result)).not.toContain('sleep')
  })

  it('keeps memory_enabled false when consent was not granted', async () => {
    const fetchMock = vi.fn().mockResolvedValue(okProfile())
    vi.stubGlobal('fetch', fetchMock)
    const source = new ApiUiDataSource({ userId: 'u-1' })

    await source.submitOnboarding({ grade: 'senior_high', memoryEnabled: false })

    expect(requestBody(fetchMock.mock.calls[0]!)).toEqual({
      target_stage: 'senior_high',
      memory_enabled: false,
    })
  })

  it('rejects an unsupported grade without fabricating a mapping and without any call', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const source = new ApiUiDataSource({ userId: 'u-1' })

    const result = await source.submitOnboarding({ grade: 'university', memoryEnabled: true })

    expect(result.status).toBe('unsupported')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('does not fall back to fixture on API failure', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify({ detail: 'dependency_service_unavailable' }), {
          status: 503,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    vi.stubGlobal('fetch', fetchMock)
    const source = new ApiUiDataSource({ userId: 'u-1' })

    const result = await source.submitOnboarding({ grade: 'junior_high', memoryEnabled: false })

    expect(result.status).toBe('error')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(JSON.stringify(result)).not.toContain('demo')
  })

  it('starts a fresh Profile request after onboarding while an older request is still pending', async () => {
    let resolveStaleProfile!: (response: Response) => void
    const staleProfile = new Promise<Response>(resolve => {
      resolveStaleProfile = resolve
    })
    let profileGetCount = 0
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      const url = String(input)
      const method = init?.method ?? 'GET'
      if (url.includes('/profile') && method === 'GET') {
        profileGetCount += 1
        if (profileGetCount === 1) return staleProfile
        return Promise.resolve(okProfile())
      }
      if (url.includes('/profile') && method === 'PUT') return Promise.resolve(okProfile())
      if (url.includes('/recommendations')) {
        return Promise.resolve(new Response(JSON.stringify(allowedRecommendation), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }))
      }
      return Promise.reject(new Error(`unmocked url: ${url}`))
    })
    vi.stubGlobal('fetch', fetchMock)
    const source = new ApiUiDataSource({ userId: 'u-1' })

    const originalLoad = source.getToday()
    await vi.waitFor(() => expect(profileGetCount).toBe(1))
    await source.submitOnboarding({ grade: 'junior_high', memoryEnabled: true })
    const refreshedLoad = source.getToday()
    /* F4 读回引入了额外的 /today 异步步骤；等新 Profile 请求真正发出后再数。 */
    await vi.waitFor(() => expect(profileGetCount).toBe(2))
    const countBeforeStaleRequestSettles = profileGetCount

    resolveStaleProfile(okProfile())
    await Promise.all([originalLoad, refreshedLoad])
    expect(profileGetCount).toBe(2)
  })
})

describe('B6 Demo onboarding stays offline', () => {
  it('fixture submitOnboarding resolves without calling the real API', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    const result = await new FixtureUiDataSource().submitOnboarding({
      grade: 'junior_high',
      memoryEnabled: true,
    })

    expect(result.status).toBe('completed')
    expect(fetchMock).not.toHaveBeenCalled()
  })
})

describe('B6 useOnboarding submission', () => {
  it('submits grade + consent default false; explicit consent can be set', async () => {
    const submit = vi.fn().mockResolvedValue({ status: 'completed', persistence: [] })
    const flow = useOnboarding(createProductionOnboardingContract(), submit)

    flow.setAnswer('grade', 'junior_high')
    await flow.submit()

    expect(submit).toHaveBeenCalledWith({ grade: 'junior_high', memoryEnabled: false })
    expect(flow.phase.value).toBe('completed')
    expect(flow.status.value).toBe('completed')

    flow.setConsent(true)
    flow.setAnswer('grade', 'senior_high')
    await flow.submit()
    expect(submit).toHaveBeenLastCalledWith({ grade: 'senior_high', memoryEnabled: true })
  })

  it('skip never calls submit, so Memory stays off', async () => {
    const submit = vi.fn()
    const flow = useOnboarding(createProductionOnboardingContract(), submit)

    flow.skip()

    expect(submit).not.toHaveBeenCalled()
    expect(flow.status.value).toBe('skipped')
    expect(flow.consent.value).toBe(false)
  })

  it('surfaces submit error without marking completed', async () => {
    const submit = vi.fn().mockResolvedValue({ status: 'error', message: 'boom', persistence: [] })
    const flow = useOnboarding(createProductionOnboardingContract(), submit)

    await flow.submit()

    expect(flow.phase.value).toBe('error')
    expect(flow.submitMessage.value).toBe('boom')
    expect(flow.status.value).toBe('active')
  })
})

describe('B6 OnboardingFlow production submission', () => {
  it('requires both grade and sleep choices before leaving the basics step', async () => {
    const wrapper = mount(OnboardingFlow, {
      props: { model: createProductionOnboardingContract(), submit: vi.fn() },
    })

    /* 组件行为：本页未完成时不前进并显示校验提示（F9 无假默认值）。 */
    await wrapper.get('[data-action="onboarding-next"]').trigger('click')
    expect(wrapper.get('[data-onboarding-step="basics"]').exists()).toBe(true)
    expect(wrapper.find('.ob-validation').exists()).toBe(true)

    await wrapper.get('[data-option="junior_high"]').trigger('click')
    expect(wrapper.find('.ob-validation').exists()).toBe(true)

    await wrapper.get('[data-option="6_to_7"]').trigger('click')
    expect(wrapper.find('.ob-validation').exists()).toBe(false)
  })

  it('selects grade, grants consent, submits, and emits completed only on success', async () => {
    vi.useFakeTimers()
    useReducedMotion()
    const submit = vi.fn().mockResolvedValue({ status: 'completed', persistence: [] })
    const wrapper = mount(OnboardingFlow, {
      props: { model: createProductionOnboardingContract(), submit },
    })

    await wrapper.get('[data-action="onboarding-next"]').trigger('click')
    await wrapper.get('[data-option="junior_high"]').trigger('click')
    await wrapper.get('[data-option="6_to_7"]').trigger('click')
    await wrapper.get('[data-action="onboarding-next"]').trigger('click')
    await wrapper.get('[data-action="onboarding-next"]').trigger('click')
    /* behavior 步骤需要显式选择，不再吃 fixture 默认值。 */
    await wrapper.get('[data-option="3_to_5"]').trigger('click')
    await wrapper.get('[data-option="after_dinner"]').trigger('click')
    await wrapper.get('[data-action="onboarding-next"]').trigger('click')
    expect(wrapper.get('[data-onboarding-step="generation"]').exists()).toBe(true)

    await wrapper.get('[data-action="onboarding-consent"]').setValue(true)
    await wrapper.get('[data-action="onboarding-next"]').trigger('click')
    await vi.advanceTimersByTimeAsync(1000)

    expect(submit).toHaveBeenCalledWith({ grade: 'junior_high', memoryEnabled: true })
    expect(wrapper.emitted('complete')).toEqual([['completed']])
    expect(useToast().toasts.value.map(toast => toast.message)).toEqual(['欢迎使用微律'])
  })

  it('stays open and shows the message when submission fails (no completed emit)', async () => {
    vi.useFakeTimers()
    useReducedMotion()
    const submit = vi.fn().mockResolvedValue({ status: 'error', message: '保存失败', persistence: [] })
    const wrapper = mount(OnboardingFlow, {
      props: { model: createProductionOnboardingContract(), submit },
    })

    await wrapper.get('[data-action="onboarding-next"]').trigger('click')
    await wrapper.get('[data-option="junior_high"]').trigger('click')
    await wrapper.get('[data-option="6_to_7"]').trigger('click')
    await wrapper.get('[data-action="onboarding-next"]').trigger('click')
    await wrapper.get('[data-action="onboarding-next"]').trigger('click')
    await wrapper.get('[data-option="3_to_5"]').trigger('click')
    await wrapper.get('[data-option="after_dinner"]').trigger('click')
    await wrapper.get('[data-action="onboarding-next"]').trigger('click')
    await wrapper.get('[data-action="onboarding-next"]').trigger('click')
    await vi.advanceTimersByTimeAsync(1000)

    expect(wrapper.get('[data-testid="onboarding-submit-message"]').text()).toContain('保存失败')
    expect(wrapper.emitted('complete')).toBeUndefined()
    expect(useToast().toasts.value).toHaveLength(0)
  })
})
