import type {
  AgentTraceEventDto,
  AgenticRecommendationResponse,
  FeedbackRequest,
  FeedbackResponse,
  HealthResponse,
  MemoryDeleteResponse,
  MemoryListResponse,
  QuestionnaireAnswerValue,
  QuestionnaireSchema,
  QuestionnaireState,
  RecommendationRequest,
  RecommendationResponse,
  TaskAction,
  TaskEventResponse,
  UserProfile,
  UserProfileUpsertRequest,
  WeeklyResponse,
} from './types'

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
    public readonly code: string,
  ) {
    super(detail)
    this.name = 'ApiError'
  }
}

function errorFromResponse(status: number, body: unknown): ApiError {
  const serverDetail =
    typeof body === 'object' && body !== null && 'detail' in body && typeof body.detail === 'string'
      ? body.detail
      : null

  if (status === 422) {
    return new ApiError(status, '请求数据无效', 'validation_error')
  }
  if (status >= 500) {
    return new ApiError(status, '服务暂时不可用', serverDetail ?? 'service_unavailable')
  }
  return new ApiError(status, '请求未能完成', serverDetail ?? `http_${status}`)
}

async function request<T>(path: string, init: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${apiBaseUrl}${path}`, init)
  } catch {
    throw new ApiError(0, '无法连接服务', 'network_error')
  }

  const isJson = response.headers.get('content-type')?.includes('application/json') ?? false
  const body: unknown = isJson ? await response.json().catch(() => null) : null

  if (!response.ok) {
    throw errorFromResponse(response.status, body)
  }
  if (!isJson) {
    throw new ApiError(response.status, '服务返回了无效响应', 'invalid_response')
  }
  return body as T
}

function jsonRequest(method: 'POST' | 'PUT', body: unknown): RequestInit {
  return {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }
}

export function healthCheck(): Promise<HealthResponse> {
  return request('/health', { method: 'GET' })
}

export function getUserProfile(userId: string): Promise<UserProfile> {
  return request(`/api/v1/users/${encodeURIComponent(userId)}/profile`, { method: 'GET' })
}

export function upsertUserProfile(
  userId: string,
  body: UserProfileUpsertRequest,
): Promise<UserProfile> {
  return request(
    `/api/v1/users/${encodeURIComponent(userId)}/profile`,
    jsonRequest('PUT', body),
  )
}

export function getRecommendation(body: RecommendationRequest): Promise<RecommendationResponse> {
  return request('/api/v1/recommendations', jsonRequest('POST', body))
}

export function getAgenticRecommendation(
  body: RecommendationRequest,
): Promise<AgenticRecommendationResponse> {
  return request('/api/v1/recommend/agentic', jsonRequest('POST', body))
}

/**
 * B3：POST + NDJSON streaming。同一个 Agentic 执行只跑一次；
 * 完成事件携带最终 sanitized 回答，前端不再重复调用旧 endpoint。
 */
export async function streamAgenticRecommendation(
  body: RecommendationRequest,
  onEvent: (event: AgentTraceEventDto) => void,
): Promise<RecommendationResponse> {
  let response: Response
  try {
    response = await fetch(`${apiBaseUrl}/api/v1/recommend/agentic/stream`, jsonRequest('POST', body))
  } catch {
    throw new ApiError(0, '无法连接服务', 'network_error')
  }
  if (!response.ok || !response.body) {
    const text = await response.text().catch(() => '')
    let detail = '服务暂时不可用'
    try {
      const parsed: unknown = JSON.parse(text)
      if (typeof parsed === 'object' && parsed !== null && 'detail' in parsed && typeof parsed.detail === 'string') {
        detail = parsed.detail
      }
    } catch {
      /* 非 JSON 错误体：保留默认文案。 */
    }
    throw new ApiError(response.status, detail, response.status >= 500 ? 'service_unavailable' : `http_${response.status}`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let final: RecommendationResponse | null = null
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let newline = buffer.indexOf('\n')
    while (newline >= 0) {
      const line = buffer.slice(0, newline).trim()
      buffer = buffer.slice(newline + 1)
      if (line) {
        const event = JSON.parse(line) as AgentTraceEventDto
        if (event.result) final = event.result
        onEvent(event)
      }
      newline = buffer.indexOf('\n')
    }
  }
  // 流中断 / 未收到 completed：不伪造最终回答。
  if (!final) {
    throw new ApiError(0, '服务未返回最终回答', 'stream_interrupted')
  }
  return final
}

export function submitFeedback(
  userId: string,
  recommendationId: string,
  body: FeedbackRequest,
): Promise<FeedbackResponse> {
  return request(
    `/api/v1/users/${encodeURIComponent(userId)}/recommendations/${encodeURIComponent(recommendationId)}/feedback`,
    jsonRequest('POST', body),
  )
}

export function getQuestionnaireSchema(): Promise<QuestionnaireSchema> {
  return request('/api/v1/questionnaire', { method: 'GET' })
}

export function getQuestionnaireState(userId: string): Promise<QuestionnaireState> {
  return request(`/api/v1/users/${encodeURIComponent(userId)}/questionnaire`, { method: 'GET' })
}

export function saveQuestionnaire(
  userId: string,
  answers: Record<string, QuestionnaireAnswerValue>,
): Promise<QuestionnaireState> {
  return request(
    `/api/v1/users/${encodeURIComponent(userId)}/questionnaire`,
    jsonRequest('PUT', { answers }),
  )
}

export function skipQuestionnaire(userId: string): Promise<QuestionnaireState> {
  return request(
    `/api/v1/users/${encodeURIComponent(userId)}/questionnaire/skip`,
    { method: 'POST' },
  )
}

/** B2：提交任务动作事件（不是 Feedback）。 */
export function postTaskEvent(
  userId: string,
  recommendationId: string,
  action: TaskAction,
): Promise<TaskEventResponse> {
  return request(
    `/api/v1/users/${encodeURIComponent(userId)}/recommendations/${encodeURIComponent(recommendationId)}/events`,
    jsonRequest('POST', { action }),
  )
}

/** B4：Memory list。 */
export function getUserMemories(userId: string): Promise<MemoryListResponse> {
  return request(`/api/v1/users/${encodeURIComponent(userId)}/memories`, { method: 'GET' })
}

/** B4：Memory delete（后端由 forget_memory 完成）。 */
export function deleteUserMemory(userId: string, memoryId: string): Promise<MemoryDeleteResponse> {
  return request(
    `/api/v1/users/${encodeURIComponent(userId)}/memories/${encodeURIComponent(memoryId)}/delete`,
    { method: 'POST' },
  )
}

/** B5：Weekly 只读聚合（UTC date 边界，见 B5 contract）。 */
export function getWeekly(
  userId: string,
  startDate: string,
  endDate: string,
): Promise<WeeklyResponse> {
  const query = `?start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`
  return request(`/api/v1/users/${encodeURIComponent(userId)}/weekly${query}`, { method: 'GET' })
}
