import { getAgenticRecommendation } from './client'
import type { AgenticRecommendationResponse, RecommendationRequest } from './types'

const request: RecommendationRequest = {
  user_id: 'user-001',
  query: '我现在需要一个小任务',
  target_stage: 'junior_high',
  current_context: 'home',
  activity_context: 'screen',
  available_minutes: 10,
  vision_abnormal: false,
  physical_discomfort: false,
  medical_request: false,
  cannot_move: false,
  unstable_environment: false,
  sleep_being_crowded: false,
}

const agenticResponse: AgenticRecommendationResponse = {
  status: 'help_seeking',
  selected_task: null,
  explanation: '请先找一位大人聊聊。',
  sources: [],
  context_sources: null,
  matched_rule_ids: [],
  reason_codes: [],
  explanation_guard: null,
  personalization: null,
  recommendation_id: null,
  feedback_available: false,
  agentic: true,
  diagnostics: { factor_count: 1 },
}

function response(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('Agentic API client', () => {
  it('uses the existing client rules and the Agentic endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(agenticResponse))
    vi.stubGlobal('fetch', fetchMock)

    await expect(getAgenticRecommendation(request)).resolves.toEqual(agenticResponse)
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/recommend/agentic',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(request),
      }),
    )
  })
})
