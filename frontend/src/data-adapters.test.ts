import { flushPromises } from '@vue/test-utils'

import type { AgenticRecommendationResponse } from './api/types'
import {
  adaptAgenticRecommendation,
  adaptRecommendationResponse,
  createUnavailableTodayContract,
} from './data/adapters'
import { FixtureUiDataSource } from './data/fixtureUiDataSource'
import { useUiDataSource } from './composables/useUiDataSource'
import type { UiDataSource } from './contracts'
import { allowedRecommendation, nonAllowedRecommendation } from './test/recommendationFixtures'

describe('Sprint 8 DTO to Contract adapters', () => {
  it('maps one real Recommendation task and marks unsupported Today fields unavailable', () => {
    const today = adaptRecommendationResponse(allowedRecommendation)

    expect(today.dataAvailability).toBe('partial')
    expect(today.recommendationStatus).toBe('allowed')
    expect(today.tasks).toHaveLength(1)
    expect(today.tasks[0]).toMatchObject({
      name: '写作业久坐后的起身活动',
      description: '起身活动约10分钟再继续。',
      meta: '约 10 分钟',
    })
    expect(today.availability.dailyTasks).toBe('unavailable')
    expect(today.availability.sleepStats).toBe('unavailable')
    expect(today.availability.progress).toBe('unavailable')
    expect(today.replacePool).toEqual([])
    expect(today.tasks).not.toHaveLength(3)
  })

  it.each(['allowed', 'blocked', 'help_seeking', 'no_safe_task'] as const)(
    'preserves Recommendation status %s without using explanation text',
    status => {
      const dto = status === 'allowed' ? allowedRecommendation : nonAllowedRecommendation(status)

      expect(adaptRecommendationResponse(dto).recommendationStatus).toBe(status)
    },
  )

  it('uses unavailable for a Today contract with no Recommendation request', () => {
    expect(createUnavailableTodayContract().recommendationStatus).toBe('unavailable')
  })

  it('does not expose Agentic trace or internal diagnostics identifiers', () => {
    const response: AgenticRecommendationResponse = {
      ...allowedRecommendation,
      agentic: true,
      diagnostics: {
        memory_id: 'UM-secret',
        matched_rule_id: 'SR-secret',
        chunk_internal_id: 'KC-secret',
        raw_query: 'secret query',
      },
    }
    const assistantReply = adaptAgenticRecommendation(response)
    const serialized = JSON.stringify(assistantReply)

    expect(assistantReply.traceIsReal).toBe(false)
    expect(assistantReply.pipeline.analysis.status).toBe('unavailable')
    expect(assistantReply.pipeline.retrieval.status).toBe('unavailable')
    expect(serialized).not.toContain('UM-secret')
    expect(serialized).not.toContain('SR-secret')
    expect(serialized).not.toContain('KC-secret')
    expect(serialized).not.toContain('secret query')
    expect(serialized).not.toContain('SRC-007')
  })
})

describe('Sprint 8 production failure boundary', () => {
  it('surfaces API errors without invoking a fixture provider', async () => {
    const fixture = new FixtureUiDataSource()
    const fixtureProvider = vi.spyOn(fixture, 'getToday')
    const source: UiDataSource = {
      getShell: () => Promise.reject(new Error('api down')),
      getToday: () => Promise.reject(new Error('api down')),
      getAssistant: () => Promise.reject(new Error('api down')),
      getProfile: () => Promise.reject(new Error('api down')),
      getOnboarding: () => Promise.reject(new Error('api down')),
      getWeekly: () => Promise.resolve(fixture.getWeekly() as never),
      askAssistant: () => Promise.reject(new Error('api down')),
    }
    const ui = useUiDataSource(source)

    await flushPromises()

    expect(ui.status.value).toBe('error')
    expect(ui.data.value).toBeNull()
    expect(fixtureProvider).not.toHaveBeenCalled()
  })
})
