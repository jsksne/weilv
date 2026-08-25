import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'

import App from './views/LegacyConsole.vue'
import { ApiError } from './api/client'
import * as api from './api/client'
import FeedbackForm from './components/FeedbackForm.vue'
import FeedbackResult from './components/FeedbackResult.vue'
import { useFeedbackFlow } from './composables/useFeedbackFlow'
import { allowedRecommendation, nonAllowedRecommendation } from './test/recommendationFixtures'

const persistedFeedback = {
  status: 'recorded',
  recommendation_id: 'rec-001',
  task_id: 'MT-SED-001',
  memory_persisted: true,
  memory_id: 'UM-feedback',
  confidence: 1,
}

function mountApp() {
  /* Sprint 9.1：直接挂载保留的 legacy 组件源码（不再是 App runtime 分支）。 */
  vi.spyOn(api, 'healthCheck').mockResolvedValue({ status: 'ok' })
  return mount(App)
}

async function showAllowedRecommendation(wrapper: ReturnType<typeof mount>) {
  vi.spyOn(api, 'getRecommendation').mockResolvedValue(allowedRecommendation)
  await wrapper.get('textarea[name="query"]').setValue('当前状态')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
}

describe('useFeedbackFlow', () => {
  it('submits only the structured feedback fields', async () => {
    const submitFeedback = vi.spyOn(api, 'submitFeedback').mockResolvedValue(persistedFeedback)
    const flow = useFeedbackFlow()
    flow.updateField('completion_status', 'partially_completed')
    flow.updateField('usefulness', 'helpful')
    flow.updateField('difficulty', 'easy')

    await flow.submit('demo-user-001', 'rec-001')

    expect(submitFeedback).toHaveBeenCalledWith('demo-user-001', 'rec-001', {
      completion_status: 'partially_completed',
      usefulness: 'helpful',
      difficulty: 'easy',
      reason: '',
    })
  })

  it('reset clears result and error while restoring feedback defaults', async () => {
    vi.spyOn(api, 'submitFeedback').mockRejectedValue(
      new ApiError(503, '服务暂时不可用', 'dependency_service_unavailable'),
    )
    const flow = useFeedbackFlow()
    flow.updateField('difficulty', 'difficult')
    await flow.submit('demo-user-001', 'rec-001')

    flow.reset()

    expect(flow.input).toEqual({
      completion_status: 'completed',
      usefulness: 'neutral',
      difficulty: 'suitable',
      reason: '',
    })
    expect(flow.result.value).toBeNull()
    expect(flow.error.value).toBeNull()
  })

  it('starts Production with an unset draft and only queues explicit completion locally', async () => {
    const submitFeedback = vi.spyOn(api, 'submitFeedback')
    const flow = useFeedbackFlow({ mode: 'production' })

    expect(flow.input.completion_status).toBeNull()
    expect(flow.input.usefulness).not.toBe('neutral')
    expect(flow.input.difficulty).not.toBe('suitable')
    expect(flow.input.reason).not.toBe('')

    await flow.submit('real-user', 'real-recommendation')
    expect(flow.pendingFeedback.value).toBeNull()

    flow.updateField('completion_status', 'completed')
    await flow.submit('real-user', 'real-recommendation')

    expect(flow.pendingFeedback.value).toEqual({ completion_status: 'completed' })
    expect(submitFeedback).not.toHaveBeenCalled()
  })
})

describe('Feedback visual flow', () => {
  it('shows feedback only for an eligible allowed recommendation', async () => {
    const wrapper = mountApp()
    await showAllowedRecommendation(wrapper)

    expect(wrapper.find('[data-testid="feedback-form"]').exists()).toBe(true)
  })

  it.each([
    { response: { ...allowedRecommendation, feedback_available: false }, label: 'disabled feedback' },
    { response: { ...allowedRecommendation, recommendation_id: null }, label: 'missing session' },
    { response: nonAllowedRecommendation('help_seeking'), label: 'help seeking' },
  ])('hides feedback for $label', async ({ response }) => {
    vi.spyOn(api, 'getRecommendation').mockResolvedValue(response)
    const wrapper = mountApp()
    await wrapper.get('textarea[name="query"]').setValue('当前状态')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.find('[data-testid="feedback-form"]').exists()).toBe(false)
  })

  it('disables feedback submission while recording', async () => {
    let resolveFeedback!: (response: typeof persistedFeedback) => void
    vi.spyOn(api, 'submitFeedback').mockImplementation(
      () => new Promise((resolve) => (resolveFeedback = resolve)),
    )
    const wrapper = mountApp()
    await showAllowedRecommendation(wrapper)

    await wrapper.get('[data-testid="feedback-form"]').trigger('submit')
    await nextTick()

    expect(wrapper.get('[data-action="feedback-submit"]').attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('正在记录……')
    resolveFeedback(persistedFeedback)
    await flushPromises()
  })

  it('maps form choices to the Feedback API and shows persisted memory copy', async () => {
    const submitFeedback = vi.spyOn(api, 'submitFeedback').mockResolvedValue(persistedFeedback)
    const wrapper = mountApp()
    await showAllowedRecommendation(wrapper)
    await wrapper.get('select[name="completion_status"]').setValue('completed')
    await wrapper.get('input[value="helpful"]').setValue(true)
    await wrapper.get('select[name="difficulty"]').setValue('easy')
    await wrapper.get('input[name="reason"]').setValue('时间刚好够')

    await wrapper.get('[data-testid="feedback-form"]').trigger('submit')
    await flushPromises()

    expect(submitFeedback).toHaveBeenCalledWith('demo-user-001', 'rec-001', {
      completion_status: 'completed',
      usefulness: 'helpful',
      difficulty: 'easy',
      reason: '时间刚好够',
    })
    expect(wrapper.text()).toContain('已记录这次反馈。')
    expect(wrapper.text()).toContain('微律会在之后的类似情况中参考这次反馈。')
    expect(wrapper.text()).not.toContain('MT-SED-001')
  })

  it('shows only the recorded copy when memory was not persisted', () => {
    const wrapper = mount(FeedbackResult, {
      props: { result: { ...persistedFeedback, memory_persisted: false } },
    })

    expect(wrapper.text()).toContain('已记录这次反馈。')
    expect(wrapper.text()).not.toContain('之后的类似情况')
  })

  it('keeps the recommendation and allows retry after feedback failure', async () => {
    const submitFeedback = vi
      .spyOn(api, 'submitFeedback')
      .mockRejectedValueOnce(new ApiError(0, '无法连接服务', 'network_error'))
      .mockResolvedValueOnce(persistedFeedback)
    const wrapper = mountApp()
    await showAllowedRecommendation(wrapper)

    await wrapper.get('[data-testid="feedback-form"]').trigger('submit')
    await flushPromises()

    expect(wrapper.find('[data-testid="task-card"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('反馈暂时没有提交成功，请重试。')
    await wrapper.get('[data-action="feedback-retry"]').trigger('click')
    await flushPromises()

    expect(submitFeedback).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('已记录这次反馈。')
  })

  it('renders a standalone feedback form without mutating its input prop', () => {
    const warning = vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    const wrapper = mount(FeedbackForm, {
      props: {
        input: {
          completion_status: 'completed',
          usefulness: 'neutral',
          difficulty: 'suitable',
          reason: '',
        },
        loading: false,
      },
    })

    expect(wrapper.get('select[name="completion_status"]').element.value).toBe('completed')
    expect(wrapper.get('input[value="neutral"]').element.checked).toBe(true)
    expect(warning).not.toHaveBeenCalled()
  })
})
