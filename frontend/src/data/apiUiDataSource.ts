import {
  ApiError,
  createScheduleEvent,
  deleteScheduleEvent,
  deleteUserMemory,
  submitFeedback,
  getAgenticRecommendation,
  getRecommendation,
  getSchedule,
  getTodaySessions,
  getUserMemories,
  getUserProfile,
  getWeekly,
  postTaskEvent,
  streamAgenticRecommendation,
  updateScheduleEvent,
  upsertUserProfile,
} from '@/api/client'
import type {
  AgentTraceStageResult,
  ConversationTurn,
  RecommendationRequest,
  ScheduleEvent,
  ScheduleEventFact,
  ScheduleEventUpsert,
  TargetStage,
  UserProfile,
  WeeklyResponse,
} from '@/api/types'
import type {
  AssistantTraceStageResult,
  AssistantTraceEvent,
  OnboardingSubmitAnswers,
  OnboardingSubmitResult,
  ProfileMemoryListContract,
  TodayTaskAction,
  UiDataSource,
} from '@/contracts'
import type { LightFeedbackPayload } from '@/contracts'
import {
  adaptAgenticRecommendation,
  adaptMemoryListResponse,
  adaptProfileResponse,
  adaptRecommendationResponse,
  adaptTodaySessions,
  adaptWeeklyResponse,
  createProductionAssistantContract,
  createProductionOnboardingContract,
  createProductionShellContract,
  createUnavailableProfileContract,
  createUnavailableTodayContract,
  createUnavailableWeeklyContract,
  mergeTodayContracts,
  PRODUCTION_TARGET_STAGES,
} from './adapters'

const TODAY_MOOD_LABELS: Record<string, string> = {
  happy: '还不错',
  calm: '平静',
  tired: '有点累',
  low: '有点低落',
}

export interface ApiUiDataSourceOptions {
  userId?: string
  recommendationRequest?: RecommendationRequest
  recommendationContext?: {
    query: string
    current_context: 'unknown' | 'home' | 'school' | 'study_space' | 'commute' | 'bedroom' | 'outdoor'
    activity_context: 'unknown' | 'reading' | 'writing' | 'screen' | 'other'
  }
}

const recommendationContextKeys = [
  'user_id',
  'query',
  'target_stage',
  'current_context',
  'activity_context',
  'available_minutes',
  'vision_abnormal',
  'physical_discomfort',
  'medical_request',
  'cannot_move',
  'unstable_environment',
  'sleep_being_crowded',
] as const satisfies readonly (keyof RecommendationRequest)[]

function hasCompleteRecommendationRequest(
  request: RecommendationRequest | undefined,
): request is RecommendationRequest {
  return (
    request !== undefined &&
    recommendationContextKeys.every(key => request[key] !== undefined)
  )
}

function mapStageResult(
  raw: AgentTraceStageResult | null | undefined,
): AssistantTraceStageResult | undefined {
  if (!raw) return undefined
  const analysis = raw.analysis
    ? {
        lead: raw.analysis.analysis_fallback
          ? '本次未返回结构化问题拆解；已使用原问题继续真实检索。'
          : raw.analysis.factors.length
            ? `已将问题整理为 ${raw.analysis.factors.length} 个可公开、可核验的方向。`
            : '已完成需求理解；本次执行没有返回可公开的结构化拆解。',
        items: raw.analysis.analysis_fallback
          ? []
          : raw.analysis.factors.map(factor => ({
              id: factor.factor_id,
              title: factor.subquery,
              direction:
                factor.evidence_need ||
                (factor.domain_hint ? `关注领域：${factor.domain_hint}` : '检索相关审核知识'),
            })),
      }
    : undefined
  const retrieval = raw.retrieval
    ? {
        chunks: raw.retrieval.knowledge_chunks.map(chunk => ({
          id: `${chunk.factor_id}-${chunk.chunk_id}`,
          source: chunk.source_locator || chunk.source_url || '审核知识库',
          text: chunk.excerpt,
          relevance: null,
        })),
      }
    : undefined
  if (!analysis && !retrieval) return undefined
  return { analysis, retrieval }
}

export class UiDataContextUnavailableError extends Error {
  readonly code = 'ui_context_unavailable'

  constructor(message = '真实 RecommendationRequest 不可用。') {
    super(message)
    this.name = 'UiDataContextUnavailableError'
  }
}

/** 近 7 天（UTC 日期边界，与 B5 定义一致）。 */
function trailingWeekDates(now: Date): { start: string; end: string } {
  const end = now.toISOString().slice(0, 10)
  const startDate = new Date(now)
  startDate.setUTCDate(now.getUTCDate() - 6)
  const start = startDate.toISOString().slice(0, 10)
  return { start, end }
}

export class ApiUiDataSource implements UiDataSource {
  private readonly userId?: string
  private readonly recommendationRequest?: RecommendationRequest
  private readonly recommendationContext?: ApiUiDataSourceOptions['recommendationContext']
  private profileTargetStage?: TargetStage
  private profileLoaded = false
  private profileInFlight?: Promise<UserProfile | null>
  private weeklyInFlight?: Promise<WeeklyResponse>
  private todayContext: {
    mood: string
    availableMinutes: number
    cannotMove?: boolean
    easyStart?: boolean
  } = {
    mood: '',
    availableMinutes: 0,
  }
  private scheduleCache?: { loadedAt: number; events: ScheduleEvent[] }

  constructor(options: ApiUiDataSourceOptions = {}) {
    this.userId = options.userId
    this.recommendationRequest = options.recommendationRequest
    this.recommendationContext = options.recommendationContext
  }

  setTodayContext(context: {
    mood: string
    availableMinutes: number
    cannotMove?: boolean
    easyStart?: boolean
  }): void {
    this.todayContext = { ...context }
  }

  /** F6：轻反馈走正式 Feedback 端点。 */
  async submitLightFeedback(
    recommendationId: string,
    body: LightFeedbackPayload,
  ): Promise<{ status: string }> {
    const userId = this.userId
    if (!userId) return { status: 'error' }
    try {
      const result = await submitFeedback(userId, recommendationId, body)
      return { status: result.status }
    } catch {
      return { status: 'error' }
    }
  }

  /* ---------- 日程最小实现（缓存 60s；写操作立即失效） ---------- */

  async getSchedule(fromDate?: string, toDate?: string): Promise<ScheduleEvent[]> {
    if (!this.userId) return []
    const dto = await getSchedule(this.userId, fromDate, toDate)
    return dto.events
  }

  async getTodaySchedule(): Promise<ScheduleEvent[]> {
    if (!this.userId) return []
    if (this.scheduleCache && Date.now() - this.scheduleCache.loadedAt < 60_000) {
      return this.scheduleCache.events
    }
    try {
      const events = await this.getSchedule()
      this.scheduleCache = { loadedAt: Date.now(), events }
      return events
    } catch {
      return []
    }
  }

  async saveScheduleEvent(body: ScheduleEventUpsert, eventId?: string): Promise<{ status: string }> {
    const userId = this.userId
    if (!userId) return { status: 'error' }
    if (eventId) await updateScheduleEvent(userId, eventId, body)
    else await createScheduleEvent(userId, body)
    this.scheduleCache = undefined
    return { status: 'saved' }
  }

  async deleteScheduleEvent(eventId: string): Promise<{ status: string }> {
    const userId = this.userId
    if (!userId) return { status: 'error' }
    await deleteScheduleEvent(userId, eventId)
    this.scheduleCache = undefined
    return { status: 'deleted' }
  }

  getShell() {
    return Promise.resolve(createProductionShellContract())
  }

  /** 同一轮 Today/Profile 共用真实 Profile 请求；settle 后允许 reload 读取新值。 */
  private loadProfileDto(): Promise<UserProfile | null> {
    if (!this.userId) return Promise.resolve(null)
    if (!this.profileInFlight) {
      const inFlight = getUserProfile(this.userId).then(
        profile => {
          if (this.profileInFlight === inFlight) {
            this.profileTargetStage = profile.target_stage
            this.profileLoaded = true
          }
          return profile
        },
        cause => {
          if (cause instanceof ApiError && cause.status === 404) return null
          throw cause
        },
      )
      this.profileInFlight = inFlight
      inFlight.then(
        () => { if (this.profileInFlight === inFlight) this.profileInFlight = undefined },
        () => { if (this.profileInFlight === inFlight) this.profileInFlight = undefined },
      )
    }
    return this.profileInFlight
  }

  /** 尝试加载并缓存真实 Profile（404 = 新用户，不缓存 target_stage）。 */
  private async ensureProfile(): Promise<{ targetStage: TargetStage | null }> {
    if (!this.userId) return { targetStage: null }
    if (this.profileLoaded) return { targetStage: this.profileTargetStage ?? null }
    const profile = await this.loadProfileDto()
    return { targetStage: profile?.target_stage ?? null }
  }

  /** 构造真实 RecommendationRequest：target_stage 来自 Profile，不硬编码。 */
  private async buildRecommendationRequest(
    queryOverride?: string,
    history?: ConversationTurn[],
    options: { withSchedule?: boolean; easyStart?: boolean } = {},
  ): Promise<RecommendationRequest | null> {
    if (!this.userId) return null
    /* 日程事实只在与推荐/对话相关的请求中读取；读取失败不阻塞推荐。 */
    const events = options.withSchedule
      ? (await this.getTodaySchedule()).map(event => ({
          kind: event.kind,
          busy_level: event.busy_level ?? undefined,
        }))
      : undefined
    if (hasCompleteRecommendationRequest(this.recommendationRequest)) {
      const request = queryOverride
        ? { ...this.recommendationRequest, query: queryOverride }
        : { ...this.recommendationRequest }
      return this.applyTodayContext(request, history, events, options.easyStart)
    }
    const { targetStage } = await this.ensureProfile()
    if (!targetStage) return null
    const context = this.recommendationContext ?? {
      query: '请为我推荐一个适合现在完成的微任务。',
      current_context: 'unknown' as const,
      activity_context: 'unknown' as const,
    }
    return this.applyTodayContext(
      {
        user_id: this.userId,
        query: queryOverride ?? context.query,
        target_stage: targetStage,
        current_context: context.current_context,
        activity_context: context.activity_context,
        vision_abnormal: false,
        physical_discomfort: false,
        medical_request: false,
        cannot_move: false,
        unstable_environment: false,
        sleep_being_crowded: false,
      },
      history,
      events,
      options.easyStart,
    )
  }

  private applyTodayContext(
    request: RecommendationRequest,
    history?: ConversationTurn[],
    events?: ScheduleEventFact[],
    easyStart?: boolean,
  ): RecommendationRequest {
    const next = { ...request }
    if (this.todayContext.availableMinutes > 0) {
      next.available_minutes = this.todayContext.availableMinutes
    }
    const moodLabel = TODAY_MOOD_LABELS[this.todayContext.mood] ?? this.todayContext.mood
    if (moodLabel) next.query = `${next.query}\n当前心情：${moodLabel}`
    if (this.todayContext.cannotMove) next.cannot_move = true
    if (this.todayContext.easyStart || easyStart) next.prefer_easy_start = true
    if (history && history.length > 0) next.conversation_history = history
    if (events && events.length > 0) next.schedule_events = events
    return next
  }

  /** “本次考虑”：只从本次请求真实使用的字段生成，最多 3 条。 */
  private consideredFromRequest(request: RecommendationRequest): string[] {
    const items: string[] = []
    if (request.available_minutes) items.push(`可用 ${request.available_minutes} 分钟`)
    const kinds = new Set((request.schedule_events ?? []).map(event => event.kind))
    if (kinds.has('exam')) items.push('今天有考试安排')
    else if (kinds.has('holiday')) items.push('今天在假期')
    if (request.cannot_move) items.push('希望原地、轻量')
    else if (request.current_context === 'school') items.push('当前在教室')
    if (request.prefer_easy_start) items.push('想要更容易开始的')
    return items.slice(0, 3)
  }

  /** B5 共享同一轮 in-flight GET；settle 后清空，后续 reload 会重新读取真实历史。 */
  private loadWeeklyDto(): Promise<WeeklyResponse> {
    if (!this.userId) throw new UiDataContextUnavailableError('缺少真实 userId，无法读取周度数据。')
    if (!this.weeklyInFlight) {
      const { start, end } = trailingWeekDates(new Date())
      const inFlight = getWeekly(this.userId, start, end)
      this.weeklyInFlight = inFlight
      inFlight.then(
        () => { if (this.weeklyInFlight === inFlight) this.weeklyInFlight = undefined },
        () => { if (this.weeklyInFlight === inFlight) this.weeklyInFlight = undefined },
      )
    }
    return this.weeklyInFlight
  }

  async getToday() {
    if (!this.userId) {
      return createUnavailableTodayContract('Production Today context unavailable：缺少真实 userId。')
    }
    /* F4：读回当天已保存的会话（任务/动作状态）；已开始/已完成/已放下
       的记录始终保留，未开始候选由新推荐按当前上下文给出。 */
    const restored = await this.loadRestoredToday()
    const request = await this.buildRecommendationRequest()
    if (!request) {
      return (
        restored ??
        createUnavailableTodayContract(
          'Production Today 尚无可用的真实 Profile；完成首次引导后即可获得推荐。',
        )
      )
    }
    try {
      const fresh = await getRecommendation(request).then(adaptRecommendationResponse)
      return restored ? mergeTodayContracts(restored, fresh) : fresh
    } catch (cause) {
      /* 新推荐失败时，已保存的当天记录仍然如实展示。 */
      if (restored) return restored
      throw cause
    }
  }

  /** 读回当天会话；读取失败返回 null（退回既有“新推荐”路径，不阻塞加载）。 */
  private async loadRestoredToday() {
    const userId = this.userId
    if (!userId) return null
    try {
      const dto = await getTodaySessions(userId)
      return adaptTodaySessions(dto)
    } catch {
      return null
    }
  }

  getAssistant() {
    return Promise.resolve(createProductionAssistantContract())
  }

  async askAssistant(question: string, history?: ConversationTurn[], easyStart?: boolean) {
    if (!this.userId) {
      throw new UiDataContextUnavailableError(
        'Production Assistant context unavailable：缺少真实 userId。',
      )
    }
    const request = await this.buildRecommendationRequest(question, history, {
      withSchedule: true,
      easyStart,
    })
    if (!request) {
      throw new UiDataContextUnavailableError(
        'Production Assistant context unavailable：缺少真实 Profile。',
      )
    }
    const reply = await getAgenticRecommendation(request).then(dto =>
      adaptAgenticRecommendation(dto, { traceIsReal: true }),
    )
    return { ...reply, considered: this.consideredFromRequest(request) }
  }

  /**
   * B3：一次真实 Agentic 流式执行。onEvent 只携带 sanitized 公开阶段；
   * 最终回答来自同一次执行（stream 的 completed 事件），不重复调用旧 endpoint。
   * history（F1）随请求进入后端理解环节。
   */
  async askAssistantStreaming(
    question: string,
    onEvent: (event: AssistantTraceEvent) => void,
    history?: ConversationTurn[],
    easyStart?: boolean,
  ) {
    if (!this.userId) {
      throw new UiDataContextUnavailableError(
        'Production Assistant context unavailable：缺少真实 userId。',
      )
    }
    const request = await this.buildRecommendationRequest(question, history, {
      withSchedule: true,
      easyStart,
    })
    if (!request) {
      throw new UiDataContextUnavailableError(
        'Production Assistant context unavailable：缺少真实 Profile。',
      )
    }
    const dto = await streamAgenticRecommendation(request, raw => {
      onEvent({
        stage: raw.stage,
        status: raw.status,
        label: raw.label,
        stageResult: mapStageResult(raw.stage_result),
      })
    })
    const reply = adaptAgenticRecommendation(dto, { traceIsReal: true })
    return { ...reply, considered: this.consideredFromRequest(request) }
  }

  async getProfile() {
    if (!this.userId) {
      return createUnavailableProfileContract('Production Profile unavailable：缺少真实 userId。')
    }

    const profile = await this.loadProfileDto()
    if (!profile) {
      return createUnavailableProfileContract('新用户尚无画像：完成首次引导后建立。')
    }

    const [memoriesResult, weeklyResult] = await Promise.allSettled([
      getUserMemories(this.userId),
      this.loadWeeklyDto(),
    ])
    if (memoriesResult.status === 'rejected' && !(memoriesResult.reason instanceof ApiError)) {
      throw memoriesResult.reason
    }
    if (weeklyResult.status === 'rejected' && !(weeklyResult.reason instanceof ApiError)) {
      throw weeklyResult.reason
    }
    const memories = memoriesResult.status === 'fulfilled'
      ? adaptMemoryListResponse(memoriesResult.value)
      : null
    const weekly = weeklyResult.status === 'fulfilled' ? weeklyResult.value : null
    return adaptProfileResponse(profile, memories, weekly)
  }

  getOnboarding() {
    return Promise.resolve(createProductionOnboardingContract())
  }

  async submitOnboarding(answers: OnboardingSubmitAnswers): Promise<OnboardingSubmitResult> {
    if (!this.userId) {
      return { status: 'error', message: '缺少真实 userId，无法保存引导结果。', persistence: [] }
    }
    if (!answers.grade) {
      return { status: 'error', message: '请先选择学段。', persistence: [] }
    }
    if (!PRODUCTION_TARGET_STAGES.includes(answers.grade)) {
      return {
        status: 'unsupported',
        message: `学段「${answers.grade}」当前后端无合法对应值，未保存。`,
        persistence: [],
      }
    }

    try {
      await upsertUserProfile(this.userId, {
        target_stage: answers.grade as TargetStage,
        memory_enabled: answers.memoryEnabled,
      })
      this.profileInFlight = undefined
      this.profileLoaded = false
      this.profileTargetStage = answers.grade as TargetStage
      return {
        status: 'completed',
        persistence: [
          { fieldId: 'grade', status: 'persisted' },
          { fieldId: 'memory_enabled', status: 'persisted' },
        ],
      }
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : '保存引导结果失败。'
      return { status: 'error', message, persistence: [] }
    }
  }

  async submitTaskAction(recommendationId: string, action: TodayTaskAction): Promise<{ status: string }> {
    if (!this.userId) {
      return { status: 'error' }
    }
    const result = await postTaskEvent(this.userId, recommendationId, action)
    return { status: result.status }
  }

  async getUserMemories(): Promise<ProfileMemoryListContract> {
    if (!this.userId) {
      return { enabled: false, consent: 'missing', items: [], canDelete: false, notice: '' }
    }
    return adaptMemoryListResponse(await getUserMemories(this.userId))
  }

  async deleteUserMemory(memoryId: string): Promise<{ status: string }> {
    if (!this.userId) {
      throw new Error('缺少真实 userId，无法删除 Memory。')
    }
    const result = await deleteUserMemory(this.userId, memoryId)
    return { status: result.status }
  }

  async getWeekly() {
    if (!this.userId) {
      return createUnavailableWeeklyContract('Production Weekly unavailable：缺少真实 userId。')
    }
    const dto = await this.loadWeeklyDto()
    return dto
      ? adaptWeeklyResponse(dto)
      : createUnavailableWeeklyContract('周度数据暂时无法加载。')
  }
}
