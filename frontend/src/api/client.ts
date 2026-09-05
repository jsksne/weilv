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
  ScheduleEventUpsert,
  ScheduleListResponse,
  TaskAction,
  TaskEventResponse,
  TodaySessionsResponse,
  UserProfile,
  UserProfileUpsertRequest,
  WeeklyResponse,
} from './types'
import {
  ApiBaseUrlConfigurationError,
  getConfiguredApiBaseUrl,
} from '@/config/apiBaseUrl'

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

function apiUrl(path: string): string {
  try {
    const baseUrl = getConfiguredApiBaseUrl()
    return baseUrl === '/' ? path : `${baseUrl}${path}`
  } catch (cause) {
    if (cause instanceof ApiBaseUrlConfigurationError) {
      throw new ApiError(0, '生产 API 地址未配置', 'api_base_url_missing')
    }
    throw cause
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
  const url = apiUrl(path)
  let response: Response
  try {
    response = await fetch(url, init)
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
  const url = apiUrl('/api/v1/recommend/agentic/stream')
  let response: Response
  try {
    response = await fetch(url, jsonRequest('POST', body))
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

/** 日程最小实现：列出与 [from, to] 重叠的事件。 */
export function getSchedule(userId: string, fromDate?: string, toDate?: string): Promise<ScheduleListResponse> {
  const params = new URLSearchParams()
  if (fromDate) params.set('from', fromDate)
  if (toDate) params.set('to', toDate)
  const query = params.toString()
  return request(
    `/api/v1/users/${encodeURIComponent(userId)}/schedule${query ? `?${query}` : ''}`,
    { method: 'GET' },
  )
}

export function createScheduleEvent(userId: string, body: ScheduleEventUpsert): Promise<ScheduleEventUpsert & { event_id: string }> {
  return request(
    `/api/v1/users/${encodeURIComponent(userId)}/schedule`,
    jsonRequest('POST', body),
  )
}

export function updateScheduleEvent(
  userId: string,
  eventId: string,
  body: ScheduleEventUpsert,
): Promise<ScheduleEventUpsert & { event_id: string }> {
  return request(
    `/api/v1/users/${encodeURIComponent(userId)}/schedule/${encodeURIComponent(eventId)}`,
    jsonRequest('PUT', body),
  )
}

export function deleteScheduleEvent(userId: string, eventId: string): Promise<{ status: string }> {
  return request(
    `/api/v1/users/${encodeURIComponent(userId)}/schedule/${encodeURIComponent(eventId)}`,
    { method: 'DELETE' },
  )
}

/** F4：读回某用户当天（UTC 日界）已保存的推荐会话。 */
export function getTodaySessions(
  userId: string,
  date?: string,
): Promise<TodaySessionsResponse> {
  return request(
    `/api/v1/users/${encodeURIComponent(userId)}/today${date ? `?date=${encodeURIComponent(date)}` : ''}`,
    { method: 'GET' },
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
