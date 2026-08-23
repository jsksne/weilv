import { flushPromises, mount } from '@vue/test-utils'

import App from './App.vue'
import * as api from './api/client'
import { useQuestionnaire } from './composables/useQuestionnaire'
import type { QuestionnaireSchema, QuestionnaireState } from './api/types'

const schema: QuestionnaireSchema = {
  questionnaire_id: 'v1',
  questions: [
    {
      question_id: 'bedtime',
      title: '平时几点睡觉？',
      description: null,
      option_type: 'single',
      required: false,
      options: [
        { value: 'before_2130', label: '21:30 前' },
        { value: 'varies', label: '不太固定' },
      ],
    },
    {
      question_id: 'rest_preference',
      title: '学习后喜欢哪种休息？',
      description: null,
      option_type: 'single',
      required: true,
      options: [
        { value: 'quiet_rest', label: '安静休息一下' },
        { value: 'far_view', label: '远眺放松' },
      ],
    },
    {
      question_id: 'annoying_reminders',
      title: '哪些提醒会让你觉得有点烦？',
      description: null,
      option_type: 'multi',
      required: true,
      options: [
        { value: 'activity', label: '动一动' },
        { value: 'none', label: '都不烦' },
      ],
    },
    {
      question_id: 'main_context',
      title: '你大多数时候在哪里学习？',
      description: null,
      option_type: 'single',
      required: true,
      options: [
        { value: 'home', label: '主要在家' },
        { value: 'school', label: '主要在学校' },
      ],
    },
  ],
}

const fullAnswers = {
  bedtime: 'varies',
  rest_preference: 'quiet_rest',
  annoying_reminders: ['activity'],
  main_context: 'home',
}

function notStartedState(userId = 'demo-user-001'): QuestionnaireState {
  return {
    user_id: userId,
    questionnaire_id: 'v1',
    completion_state: 'not_started',
    updated_at: null,
    completed_at: null,
    answers: {},
    memory_record_ids: [],
  }
}

function completedState(userId = 'demo-user-001'): QuestionnaireState {
  return {
    user_id: userId,
    questionnaire_id: 'v1',
    completion_state: 'completed',
    updated_at: '2026-08-19T08:00:00+00:00',
    completed_at: '2026-08-19T08:00:00+00:00',
    answers: fullAnswers,
    memory_record_ids: ['UM-1'],
  }
}

function mockServices(overrides: {
  state?: QuestionnaireState
  saved?: QuestionnaireState
  skipped?: QuestionnaireState
} = {}) {
  vi.spyOn(api, 'healthCheck').mockResolvedValue({ status: 'ok' })
  vi.spyOn(api, 'getUserProfile').mockResolvedValue({
    user_id: 'demo-user-001',
    target_stage: 'junior_high',
    memory_enabled: true,
    created_at: '2026-08-13T10:00:00+08:00',
    updated_at: '2026-08-13T10:00:00+08:00',
  })
  vi.spyOn(api, 'getQuestionnaireSchema').mockResolvedValue(schema)
  vi.spyOn(api, 'getQuestionnaireState').mockResolvedValue(
    overrides.state ?? notStartedState(),
  )
  const save = vi
    .spyOn(api, 'saveQuestionnaire')
    .mockResolvedValue(overrides.saved ?? completedState())
  const skip = vi
    .spyOn(api, 'skipQuestionnaire')
    .mockResolvedValue(overrides.skipped ?? { ...notStartedState(), completion_state: 'skipped' })
  return { save, skip }
}

async function selectOption(
  wrapper: ReturnType<typeof mount>,
  value: string,
  checked = true,
) {
  const input = wrapper.get(`input[value="${value}"]`)
  ;(input.element as HTMLInputElement).checked = checked
  await input.trigger('change')
}

describe('useQuestionnaire', () => {
  it('loads the schema and starts fresh for a new user', async () => {
    mockServices()
    const flow = useQuestionnaire()

    await flow.load('demo-user-001')

    expect(flow.status.value).toBe('active')
    expect(flow.total.value).toBe(4)
    expect(flow.index.value).toBe(0)
    expect(flow.question.value?.question_id).toBe('bedtime')
  })

  it('resumes at the first unanswered question for a partial completion', async () => {
    mockServices({
      state: {
        ...notStartedState(),
        completion_state: 'partially_completed',
        answers: { rest_preference: 'quiet_rest' },
      },
    })
    const flow = useQuestionnaire()

    await flow.load('demo-user-001')

    expect(flow.status.value).toBe('active')
    expect(flow.answers.rest_preference).toBe('quiet_rest')
    expect(flow.index.value).toBe(0) // first unanswered (bedtime) is shown again
  })

  it('advances past optional questions but not unanswered required ones', async () => {
    mockServices()
    const flow = useQuestionnaire()
    await flow.load('demo-user-001')

    expect(flow.question.value?.question_id).toBe('bedtime') // optional
    flow.next()
    expect(flow.question.value?.question_id).toBe('rest_preference') // required, unanswered
    flow.next()
    expect(flow.question.value?.question_id).toBe('rest_preference') // blocked by required

    flow.setAnswer('rest_preference', 'quiet_rest')
    flow.next()
    expect(flow.question.value?.question_id).toBe('annoying_reminders')
  })

  it('clears a previous user answers when loading another user', async () => {
    vi.spyOn(api, 'getQuestionnaireSchema').mockResolvedValue(schema)
    vi.spyOn(api, 'getQuestionnaireState')
      .mockResolvedValueOnce({
        ...notStartedState('user-a'),
        answers: { rest_preference: 'quiet_rest', main_context: 'home' },
      })
      .mockResolvedValueOnce(notStartedState('user-b'))
    const flow = useQuestionnaire()

    await flow.load('user-a')
    flow.setAnswer('bedtime', 'before_2130')
    expect(flow.answers.rest_preference).toBe('quiet_rest')

    await flow.load('user-b') // fresh user, empty record

    expect(flow.answers).toEqual({})
    expect(flow.index.value).toBe(0)
  })
})

describe('Questionnaire web flow', () => {
  it('completes the questionnaire, saves answers, and hides it', async () => {
    const { save } = mockServices()
    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.get('[data-testid="questionnaire"]').exists()).toBe(true)

    await selectOption(wrapper, 'varies')
    await wrapper.get('[data-action="questionnaire-next"]').trigger('click')
    await selectOption(wrapper, 'quiet_rest')
    await wrapper.get('[data-action="questionnaire-next"]').trigger('click')
    await selectOption(wrapper, 'activity')
    await wrapper.get('[data-action="questionnaire-next"]').trigger('click')
    await selectOption(wrapper, 'home')
    await wrapper.get('[data-action="questionnaire-next"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('先确认一下，再开始为你推荐～')
    await wrapper.get('[data-action="questionnaire-finish"]').trigger('click')
    await flushPromises()

    expect(save).toHaveBeenCalledWith('demo-user-001', fullAnswers)
    expect(wrapper.find('[data-testid="questionnaire"]').exists()).toBe(false)
  })

  it('skipping the questionnaire stores the skip and keeps the product usable', async () => {
    const { skip } = mockServices()
    const wrapper = mount(App)
    await flushPromises()

    await wrapper.get('[data-action="questionnaire-skip"]').trigger('click')
    await flushPromises()

    expect(skip).toHaveBeenCalledWith('demo-user-001')
    expect(wrapper.find('[data-testid="questionnaire"]').exists()).toBe(false)
    expect(wrapper.get('textarea[name="query"]').exists()).toBe(true)
  })

  it('back navigates to the previous question', async () => {
    mockServices()
    const wrapper = mount(App)
    await flushPromises()

    await selectOption(wrapper, 'varies')
    await wrapper.get('[data-action="questionnaire-next"]').trigger('click')
    expect(wrapper.text()).toContain('学习后喜欢哪种休息？')

    await wrapper.get('[data-action="questionnaire-back"]').trigger('click')
    expect(wrapper.text()).toContain('平时几点睡觉？')
  })

  it('multi-select none is exclusive with other options', async () => {
    mockServices()
    const wrapper = mount(App)
    await flushPromises()

    // move to the multi-select question
    await selectOption(wrapper, 'varies')
    await wrapper.get('[data-action="questionnaire-next"]').trigger('click')
    await selectOption(wrapper, 'quiet_rest')
    await wrapper.get('[data-action="questionnaire-next"]').trigger('click')

    await selectOption(wrapper, 'activity')
    await selectOption(wrapper, 'none')
    expect((wrapper.get('input[value="activity"]').element as HTMLInputElement).checked).toBe(false)
    expect((wrapper.get('input[value="none"]').element as HTMLInputElement).checked).toBe(true)

    await selectOption(wrapper, 'activity')
    expect((wrapper.get('input[value="activity"]').element as HTMLInputElement).checked).toBe(true)
    expect((wrapper.get('input[value="none"]').element as HTMLInputElement).checked).toBe(false)
  })
})
