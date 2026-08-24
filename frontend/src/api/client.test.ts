import {
  ApiError,
  deleteUserMemory,
  getRecommendation,
  getUserMemories,
  getWeekly,
  healthCheck,
  postTaskEvent,
} from './client'
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

  it('postTaskEvent sends only the action to the recommendation events endpoint', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(response({ status: 'recorded', recommendation_id: 'rec-1', task_id: 'MT-A', action: 'started', recorded_at: 't' }))
    vi.stubGlobal('fetch', fetchMock)

    await postTaskEvent('user-001', 'rec-1', 'started')

    const [url, init] = fetchMock.mock.calls[0]!
    expect(String(url)).toContain('/api/v1/users/user-001/recommendations/rec-1/events')
    expect((init as RequestInit).method).toBe('POST')
    expect(JSON.parse(String((init as RequestInit).body))).toEqual({ action: 'started' })
  })

  it('getUserMemories and deleteUserMemory hit the B4 endpoints', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ user_id: 'user-001', memory_enabled: true, memories: [] }))
      .mockResolvedValueOnce(response({ status: 'forgotten', memory_id: 'UM-1' }))
    vi.stubGlobal('fetch', fetchMock)

    await getUserMemories('user-001')
    await deleteUserMemory('user-001', 'UM-1')

    expect(String(fetchMock.mock.calls[0]![0])).toContain('/api/v1/users/user-001/memories')
    expect((fetchMock.mock.calls[0]![1] as RequestInit).method).toBe('GET')
    expect(String(fetchMock.mock.calls[1]![0])).toContain('/api/v1/users/user-001/memories/UM-1/delete')
    expect((fetchMock.mock.calls[1]![1] as RequestInit).method).toBe('POST')
  })

  it('getWeekly requests the UTC date range on the B5 endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({ user_id: 'user-001', start_date: '2026-08-18', end_date: '2026-08-24', minutes_policy: 'x', days: [], totals: { completed_minutes: 0, action_counts: {} }, events: [], adjustments: [] }))
    vi.stubGlobal('fetch', fetchMock)

    await getWeekly('user-001', '2026-08-18', '2026-08-24')

    expect(String(fetchMock.mock.calls[0]![0])).toContain('/api/v1/users/user-001/weekly?start_date=2026-08-18&end_date=2026-08-24')
  })
})
