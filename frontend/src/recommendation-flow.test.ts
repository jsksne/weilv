import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'

import App from './App.vue'
import { ApiError } from './api/client'
import * as api from './api/client'
import RecommendationResult from './components/RecommendationResult.vue'
import SafetyResult from './components/SafetyResult.vue'
import { useRecommendationFlow } from './composables/useRecommendationFlow'
import {
  allowedRecommendation,
  nonAllowedRecommendation,
} from './test/recommendationFixtures'

function mountApp() {
  /* Sprint 4：legacy 表单流由 ?legacy=1 查询参数承载 */
  window.history.pushState({}, '', '/?legacy=1')
  vi.spyOn(api, 'healthCheck').mockResolvedValue({ status: 'ok' })
  return mount(App)
}

async function submitApp(wrapper: ReturnType<typeof mount>) {
  await wrapper.get('textarea[name="query"]').setValue('我已经写作业快一个小时了，现在有10分钟休息。')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
}

describe('useRecommendationFlow', () => {
  it('submits the exact current FastAPI request contract', async () => {
    const getRecommendation = vi.spyOn(api, 'getRecommendation').mockResolvedValue(allowedRecommendation)
    const flow = useRecommendationFlow()
    Object.assign(flow.form, {
      user_id: 'demo-user-001',
      query: '我已经写作业快一个小时了，现在有10分钟休息。',
      target_stage: 'junior_high',
      current_context: 'home',
      activity_context: 'writing',
      available_minutes: 10,
      vision_abnormal: false,
      physical_discomfort: false,
      medical_request: false,
      cannot_move: false,
      unstable_environment: false,
      sleep_being_crowded: false,
    })

    await flow.submit()

    expect(getRecommendation).toHaveBeenCalledWith({
      user_id: 'demo-user-001',
      query: '我已经写作业快一个小时了，现在有10分钟休息。',
      target_stage: 'junior_high',
      current_context: 'home',
      activity_context: 'writing',
      available_minutes: 10,
      vision_abnormal: false,
      physical_discomfort: false,
      medical_request: false,
      cannot_move: false,
      unstable_environment: false,
      sleep_being_crowded: false,
    })
  })

  it('retains the complete recommendation session response', async () => {
    vi.spyOn(api, 'getRecommendation').mockResolvedValue(allowedRecommendation)
    const flow = useRecommendationFlow()
    flow.form.query = '当前状态'

    await flow.submit()

    expect(flow.result.value?.recommendation_id).toBe('rec-001')
    expect(flow.result.value?.feedback_available).toBe(true)
  })

  it('retains the submitted request identity for the recommendation session', async () => {
    vi.spyOn(api, 'getRecommendation').mockResolvedValue(allowedRecommendation)
    const flow = useRecommendationFlow()
    flow.form.user_id = 'demo-user-001'
    flow.form.query = '当前状态'

    await flow.submit()
    flow.form.user_id = 'changed-after-submit'

    expect(flow.submittedRequest.value?.user_id).toBe('demo-user-001')
  })

  it('reset restores demo defaults and clears result and error', async () => {
    vi.spyOn(api, 'getRecommendation').mockRejectedValue(
      new ApiError(503, '服务暂时不可用', 'dependency_service_unavailable'),
    )
    const flow = useRecommendationFlow()
    flow.form.user_id = 'changed'
    flow.form.query = '当前状态'
    await flow.submit()

    flow.reset()

    expect(flow.form.user_id).toBe('demo-user-001')
    expect(flow.form.query).toBe('')
    expect(flow.result.value).toBeNull()
    expect(flow.error.value).toBeNull()
    expect(flow.submittedRequest.value).toBeNull()
  })
})

describe('Recommendation form lifecycle', () => {
  it('disables submit while a recommendation is loading', async () => {
    const warning = vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    let resolveRecommendation!: (response: typeof allowedRecommendation) => void
    vi.spyOn(api, 'getRecommendation').mockImplementation(
      () => new Promise((resolve) => (resolveRecommendation = resolve)),
    )
    const wrapper = mountApp()
    await wrapper.get('textarea[name="query"]').setValue('当前状态')

    await wrapper.get('form').trigger('submit')
    await nextTick()

    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('正在准备一个合适的小行动……')
    expect(warning).not.toHaveBeenCalled()
    resolveRecommendation(allowedRecommendation)
    await flushPromises()
  })
})

describe('Allowed recommendation rendering', () => {
  it('renders the exact task, server duration, and explanation', () => {
    const wrapper = mount(RecommendationResult, { props: { result: allowedRecommendation } })

    expect(wrapper.text()).toContain('写作业久坐后的起身活动')
    expect(wrapper.text()).toContain('起身活动约10分钟再继续。')
    expect(wrapper.text()).toContain('约10分钟')
    expect(wrapper.text()).toContain('这个任务适合当前短暂休息的情境。')
  })

  it('renders exact evidence with a safe unchanged source link', () => {
    const wrapper = mount(RecommendationResult, { props: { result: allowedRecommendation } })
    const evidence = wrapper.get('[data-section="evidence"]')
    const link = evidence.get('a')

    expect(evidence.text()).toContain('SRC-007')
    expect(evidence.text()).toContain('source.md:L20-L20')
    expect(link.attributes()).toMatchObject({
      href: 'https://example.test/source',
      target: '_blank',
      rel: 'noopener noreferrer',
    })
  })

  it('keeps context sources separate from formal task evidence', () => {
    const wrapper = mount(RecommendationResult, { props: { result: allowedRecommendation } })

    expect(wrapper.get('[data-section="evidence"]').text()).not.toContain('SRC-CONTEXT')
    expect(wrapper.get('[data-section="context"]').text()).toContain('SRC-CONTEXT')
    expect(wrapper.get('[data-section="context"]').text()).toContain('背景知识')
  })

  it('shows restrained personalization copy without internal audit fields', () => {
    const personalized = {
      ...allowedRecommendation,
      personalization: {
        memory_used: true,
        memory_ids: ['UM-SECRET-001'],
        base_task_rank: 2,
        personalization_delta: 3,
        adjusted_rank: -1,
        reason_codes: ['preferred_task'],
      },
    }
    const wrapper = mount(RecommendationResult, { props: { result: personalized } })

    expect(wrapper.text()).toContain('这次排序参考了你之前明确提交的任务反馈。')
    expect(wrapper.text()).not.toContain('UM-SECRET-001')
    expect(wrapper.text()).not.toContain('preferred_task')
    expect(wrapper.text()).not.toContain('adjusted_rank')
  })

  it('shows a backend fallback explanation without guard internals', () => {
    const fallback = {
      ...allowedRecommendation,
      explanation: '请按任务卡中的原始指令执行。',
      explanation_guard: {
        passed: false,
        fallback_used: true,
        reason_codes: ['adds_unsupported_action'],
      },
    }
    const wrapper = mount(RecommendationResult, { props: { result: fallback } })

    expect(wrapper.text()).toContain('请按任务卡中的原始指令执行。')
    expect(wrapper.text()).not.toContain('adds_unsupported_action')
    expect(wrapper.text()).not.toContain('Output Guard')
  })
})

describe('Non-allowed business states', () => {
  it.each([
    ['help_seeking', '现在更适合先告诉家长、老师或寻求进一步帮助'],
    ['blocked', '当前条件下暂不提供普通微任务'],
    ['no_safe_task', '当前暂时没有足够合适的微任务'],
  ] as const)('renders %s without trying to render a task', (status, message) => {
    const wrapper = mount(SafetyResult, {
      props: { result: nonAllowedRecommendation(status) },
    })

    expect(wrapper.text()).toContain(message)
    expect(wrapper.find('[data-testid="task-card"]').exists()).toBe(false)
  })
})

describe('Recommendation request errors', () => {
  it('shows a plain HTTP error without leaking backend detail', async () => {
    vi.spyOn(api, 'getRecommendation').mockRejectedValue(
      new ApiError(503, '服务暂时不可用', 'dependency_service_unavailable'),
    )
    const wrapper = mountApp()

    await submitApp(wrapper)

    expect(wrapper.text()).toContain('暂时无法获取微任务，请稍后重试。')
    expect(wrapper.text()).not.toContain('dependency_service_unavailable')
    expect(wrapper.text()).not.toContain('服务暂时不可用')
  })

  it('keeps the page usable after a network failure', async () => {
    vi.spyOn(api, 'getRecommendation').mockRejectedValue(
      new ApiError(0, '无法连接服务', 'network_error'),
    )
    const wrapper = mountApp()

    await submitApp(wrapper)

    expect(wrapper.text()).toContain('微律')
    expect(wrapper.text()).toContain('暂时无法获取微任务，请稍后重试。')
    expect(wrapper.get('[data-action="retry"]').text()).toBe('重试')
  })
})
