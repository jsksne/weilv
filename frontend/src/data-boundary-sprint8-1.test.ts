import { mount } from '@vue/test-utils'

import * as api from './api/client'
import type { AgenticRecommendationResponse, RecommendationRequest } from './api/types'
import { adaptRecommendationResponse } from './data/adapters'
import { ApiUiDataSource } from './data/apiUiDataSource'
import { FixtureUiDataSource } from './data/fixtureUiDataSource'
import { assistantFixture } from './data/fixtures/assistant.fixture'
import { todayFixture } from './data/fixtures/today.fixture'
import TodayView from './views/TodayView.vue'
import { useDailyTasks } from './composables/useDailyTasks'
import { allowedRecommendation } from './test/recommendationFixtures'

const explicitRecommendationRequest: RecommendationRequest = {
  user_id: 'real-user-123',
  query: '真实上下文问题',
  target_stage: 'senior_high',
  current_context: 'study_space',
  activity_context: 'writing',
  available_minutes: 25,
  vision_abnormal: true,
  physical_discomfort: false,
  medical_request: true,
  cannot_move: false,
  unstable_environment: true,
  sleep_being_crowded: false,
}

const agenticRecommendation: AgenticRecommendationResponse = {
  ...allowedRecommendation,
  agentic: true,
  diagnostics: {},
}

function response(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

function requestBody(call: unknown[]): unknown {
  return JSON.parse(String((call[1] as RequestInit).body))
}

describe('Sprint 8.1 Production data boundary', () => {
  it('returns explicit unavailable contracts without fabricating a user or calling the network', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const source = new ApiUiDataSource()

    const today = await source.getToday()
    const profile = await source.getProfile()
    const onboarding = await source.getOnboarding()

    expect(today.recommendationStatus).toBe('unavailable')
    expect(profile.state.status).toBe('unavailable')
    // B6：Production onboarding 现在是可用五步引导（不依赖旧问卷）。
    expect(onboarding.state.status).toBe('ready')
    expect(onboarding.phase).toBe('ready')
    expect(onboarding.steps).toHaveLength(5)
    await expect(source.askAssistant('真实问题')).rejects.toMatchObject({
      name: 'UiDataContextUnavailableError',
      code: 'ui_context_unavailable',
    })
    expect(JSON.stringify({ today, profile, onboarding })).not.toContain('demo-user-001')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('keeps Profile and Questionnaire unavailable when userId is missing', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const source = new ApiUiDataSource({ recommendationRequest: explicitRecommendationRequest })

    const [profile, onboarding] = await Promise.all([source.getProfile(), source.getOnboarding()])

    expect(profile.state.status).toBe('unavailable')
    expect(onboarding.state.status).toBe('ready')
    expect(onboarding.steps).toHaveLength(5)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('uses a complete explicit request as-is and changes only the Agentic query', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(allowedRecommendation))
      .mockResolvedValueOnce(response(agenticRecommendation))
    vi.stubGlobal('fetch', fetchMock)
    const source = new ApiUiDataSource({
      userId: 'real-profile-user',
      recommendationRequest: explicitRecommendationRequest,
    })

    await source.getToday()
    await source.askAssistant('用户本次真实问题')

    expect(requestBody(fetchMock.mock.calls[0]!)).toEqual(explicitRecommendationRequest)
    expect(requestBody(fetchMock.mock.calls[1]!)).toEqual({
      ...explicitRecommendationRequest,
      query: '用户本次真实问题',
    })
  })

  it('sends the selected Today mood and available time through the next real recommendation request', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(allowedRecommendation))
    vi.stubGlobal('fetch', fetchMock)
    const source = new ApiUiDataSource({
      userId: 'real-profile-user',
      recommendationRequest: explicitRecommendationRequest,
    })

    source.setTodayContext({ mood: 'tired', availableMinutes: 10 })
    await source.getToday()

    const body = requestBody(fetchMock.mock.calls[0]!)
    const { query, ...bodyWithoutQuery } = body
    const { query: _configuredQuery, ...configuredWithoutQuery } = explicitRecommendationRequest
    expect(bodyWithoutQuery).toEqual({ ...configuredWithoutQuery, available_minutes: 10 })
    expect(query).toContain('有点累')
  })

  it('does not turn an incomplete request into health defaults', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const incompleteRequest = {
      user_id: 'real-user-123',
      query: '只有部分上下文',
      target_stage: 'junior_high',
      current_context: 'home',
    } as RecommendationRequest
    const source = new ApiUiDataSource({ recommendationRequest: incompleteRequest })

    const today = await source.getToday()

    expect(today.recommendationStatus).toBe('unavailable')
    expect(fetchMock).not.toHaveBeenCalled()
  })
})

describe('Sprint 8.1 Fixture assistant boundary', () => {
  it('marks the Demo Today fixture as allowed', () => {
    expect(todayFixture.recommendationStatus).toBe('allowed')
  })

  it.each(['我脖子疼', 'neck pain', '最近睡不好'])(
    'uses fallback for free text: %s',
    async question => {
      const reply = await new FixtureUiDataSource().askAssistant(question)

      expect(reply).toBe(assistantFixture.replies.fallback)
      expect(reply).not.toBe(assistantFixture.replies.neck)
      expect(reply).not.toBe(assistantFixture.replies.sleep)
      expect(reply).not.toBe(assistantFixture.replies.exam)
    },
  )
})

describe('Sprint 8.1 Production task feedback boundary', () => {
  it('keeps task completion local and does not call Feedback API', async () => {
    const submitFeedback = vi.spyOn(api, 'submitFeedback')
    const model = adaptRecommendationResponse(allowedRecommendation)
    let now = 1_000
    const daily = useDailyTasks(model, { now: () => now })
    const completionFxStub = {
      name: 'TaskCompletionFx',
      props: {},
      setup() {
        return { play: () => undefined, reset: () => undefined }
      },
      render: () => null,
    }
    const wrapper = mount(TodayView, {
      props: { model, daily },
      global: { stubs: { TaskCompletionFx: completionFxStub } },
    })

    await wrapper.get('[data-act="start"]').trigger('click')
    now += 450
    await wrapper.get('[data-act="done"]').trigger('click')

    expect(daily.pendingFeedback.value).toHaveLength(1)
    expect(wrapper.get('[data-testid="pending-feedback"]').exists()).toBe(true)
    expect(submitFeedback).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
