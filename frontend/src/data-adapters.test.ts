import { flushPromises } from '@vue/test-utils'

import type { AgenticRecommendationResponse } from './api/types'
import {
  adaptAgenticRecommendation,
  adaptMemoryListResponse,
  adaptProfileResponse,
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
    expect(today.availability.dailyTasks).toBe('available')
    expect(today.availability.sleepStats).toBe('unavailable')
    expect(today.availability.progress).toBe('available')
    expect(today.availability.restore).toBe('available')
    expect(today.availability.replace).toBe('unavailable')
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

  it('wires public evidence metadata into the real retrieval stage without exposing private reasoning', () => {
    const reply = adaptAgenticRecommendation(allowedRecommendation, { traceIsReal: true })

    expect(reply.pipeline.analysis.lead).toBeTruthy()
    expect(reply.pipeline.analysis.items).toEqual([])
    expect(reply.pipeline.retrieval.chunks[0]).toMatchObject({
      text: null,
      relevance: null,
    })
  })

  it('uses B4 memory and B5 task history for truthful Profile slices', () => {
    const memories = adaptMemoryListResponse({
      user_id: 'u-1',
      memory_enabled: true,
      memories: [],
    })
    const profile = adaptProfileResponse(
      {
        user_id: 'u-1',
        target_stage: 'senior_high',
        memory_enabled: true,
      },
      memories,
      {
        user_id: 'u-1',
        start_date: '2026-08-21',
        end_date: '2026-08-27',
        minutes_policy: 'official_estimated_minutes_only',
        days: [],
        totals: {
          completed_minutes: 6,
          action_counts: { completed: 2, partially_completed: 1, skipped: 1 },
        },
        events: [],
        adjustments: [],
      },
    )

    expect(profile.memory.status).toBe('available')
    expect(profile.memory.notice).toContain('尚未形成')
    expect(profile.completionPattern.percentage).toBe(75)
    expect(profile.completionPattern.summaryLines[0]).toContain('完成 2 项')
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
