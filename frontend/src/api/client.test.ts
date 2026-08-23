import { ApiError, getRecommendation, healthCheck } from './client'
import type { RecommendationRequest, RecommendationResponse } from './types'

const request: RecommendationRequest = {
  user_id: 'user-001',
  query: '我写作业快一个小时了，现在有10分钟休息。',
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
}

const helpSeekingResponse: RecommendationResponse = {
  status: 'help_seeking',
  selected_task: null,
  explanation: null,
  sources: [],
  context_sources: null,
  matched_rule_ids: ['SR-001'],
  reason_codes: ['vision_abnormal_help_seeking'],
  explanation_guard: null,
  personalization: null,
  recommendation_id: null,
  feedback_available: false,
}

function response(body: unknown, status = 200, contentType = 'application/json') {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': contentType },
  })
}

describe('API client', () => {
  it('healthCheck sends GET /health and returns the response', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({ status: 'ok' }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(healthCheck()).resolves.toEqual({ status: 'ok' })
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/health',
      expect.objectContaining({ method: 'GET' }),
    )
  })

  it('returns help_seeking as a normal HTTP 200 recommendation response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(helpSeekingResponse)))

    await expect(getRecommendation(request)).resolves.toEqual(helpSeekingResponse)
  })

  it.each([422, 503])('turns HTTP %s into ApiError', async (status) => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(response({ detail: 'dependency_service_unavailable' }, status)),
    )

    const result = getRecommendation(request)

    await expect(result).rejects.toBeInstanceOf(ApiError)
    await expect(result).rejects.toMatchObject({ status })
  })

  it('sanitizes network failures as ApiError without exposing the original exception', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('socket secret detail')))

    const result = healthCheck()

    await expect(result).rejects.toMatchObject({
      status: 0,
      code: 'network_error',
      detail: '无法连接服务',
    })
    await expect(result).rejects.not.toMatchObject({ detail: expect.stringContaining('socket') })
  })
})
