import {
  ApiError,
  deleteUserMemory,
  getAgenticRecommendation,
  getRecommendation,
  getUserMemories,
  getUserProfile,
  getWeekly,
  postTaskEvent,
  streamAgenticRecommendation,
  upsertUserProfile,
} from '@/api/client'
import type {
  AgentTraceStageResult,
  RecommendationRequest,
  TargetStage,
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
import {
  adaptAgenticRecommendation,
  adaptMemoryListResponse,
  adaptProfileResponse,
  adaptRecommendationResponse,
  adaptWeeklyResponse,
  createProductionAssistantContract,
  createProductionOnboardingContract,
  createProductionShellContract,
  createUnavailableProfileContract,
  createUnavailableTodayContract,
  createUnavailableWeeklyContract,
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
  private weeklyInFlight?: Promise<WeeklyResponse>
  private todayContext = { mood: '', availableMinutes: 0 }

  constructor(options: ApiUiDataSourceOptions = {}) {
    this.userId = options.userId
    this.recommendationRequest = options.recommendationRequest
    this.recommendationContext = options.recommendationContext
  }

  setTodayContext(context: { mood: string; availableMinutes: number }): void {
    this.todayContext = { ...context }
  }

  getShell() {
    return Promise.resolve(createProductionShellContract())
  }

  /** 尝试加载并缓存真实 Profile（404 = 新用户，不缓存 target_stage）。 */
  private async ensureProfile(): Promise<{ targetStage: TargetStage | null }> {
    if (!this.userId) return { targetStage: null }
    if (this.profileLoaded) {
      return { targetStage: this.profileTargetStage ?? null }
    }
    try {
      const profile = await getUserProfile(this.userId)
      this.profileTargetStage = profile.target_stage
      this.profileLoaded = true
      return { targetStage: profile.target_stage }
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 404) {
        return { targetStage: null }
      }
      throw cause
    }
  }

  /** 构造真实 RecommendationRequest：target_stage 来自 Profile，不硬编码。 */
  private async buildRecommendationRequest(
    queryOverride?: string,
  ): Promise<RecommendationRequest | null> {
    if (!this.userId) return null
    if (hasCompleteRecommendationRequest(this.recommendationRequest)) {
      const request = queryOverride
        ? { ...this.recommendationRequest, query: queryOverride }
        : { ...this.recommendationRequest }
      return this.applyTodayContext(request)
    }
    const { targetStage } = await this.ensureProfile()
    if (!targetStage) return null
    const context = this.recommendationContext ?? {
      query: '请为我推荐一个适合现在完成的微任务。',
      current_context: 'unknown' as const,
      activity_context: 'unknown' as const,
    }
    return this.applyTodayContext({
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
    })
  }

  private applyTodayContext(request: RecommendationRequest): RecommendationRequest {
    const next = { ...request }
    if (this.todayContext.availableMinutes > 0) {
      next.available_minutes = this.todayContext.availableMinutes
    }
    const moodLabel = TODAY_MOOD_LABELS[this.todayContext.mood] ?? this.todayContext.mood
    if (moodLabel) next.query = `${next.query}\n当前心情：${moodLabel}`
    return next
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
    const request = await this.buildRecommendationRequest()
    if (!request) {
      return createUnavailableTodayContract(
        'Production Today 尚无可用的真实 Profile；完成首次引导后即可获得推荐。',
      )
    }
    return getRecommendation(request).then(adaptRecommendationResponse)
  }

  getAssistant() {
    return Promise.resolve(createProductionAssistantContract())
  }

  async askAssistant(question: string) {
    if (!this.userId) {
      throw new UiDataContextUnavailableError(
        'Production Assistant context unavailable：缺少真实 userId。',
      )
    }
    const request = await this.buildRecommendationRequest(question)
    if (!request) {
      throw new UiDataContextUnavailableError(
        'Production Assistant context unavailable：缺少真实 Profile。',
      )
    }
    return getAgenticRecommendation(request).then(dto =>
      adaptAgenticRecommendation(dto, { traceIsReal: true }),
    )
  }

  /**
   * B3：一次真实 Agentic 流式执行。onEvent 只携带 sanitized 公开阶段；
   * 最终回答来自同一次执行（stream 的 completed 事件），不重复调用旧 endpoint。
   */
  async askAssistantStreaming(
    question: string,
    onEvent: (event: AssistantTraceEvent) => void,
  ) {
    if (!this.userId) {
      throw new UiDataContextUnavailableError(
        'Production Assistant context unavailable：缺少真实 userId。',
      )
    }
    const request = await this.buildRecommendationRequest(question)
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
    return adaptAgenticRecommendation(dto, { traceIsReal: true })
  }

  async getProfile() {
    if (!this.userId) {
      return createUnavailableProfileContract('Production Profile unavailable：缺少真实 userId。')
    }

    try {
      const profile = await getUserProfile(this.userId)
      this.profileTargetStage = profile.target_stage
      this.profileLoaded = true
      let memories: ProfileMemoryListContract | null = null
      let weekly: WeeklyResponse | null = null
      try {
        memories = adaptMemoryListResponse(await getUserMemories(this.userId))
      } catch (cause) {
        // Memory list 失败不拖垮 Profile；保持 Memory 部分 unavailable。
        if (!(cause instanceof ApiError)) throw cause
      }
      try {
        weekly = await this.loadWeeklyDto()
      } catch (cause) {
        // Weekly 统计失败不拖垮 Profile；完成情况保持真实空态。
        if (!(cause instanceof ApiError)) throw cause
      }
      return adaptProfileResponse(profile, memories, weekly)
    } catch (cause) {
      // 新用户尚无画像：保持 bundle 可加载，Profile 显示未建立状态。
      if (cause instanceof ApiError && cause.status === 404) {
        return createUnavailableProfileContract('新用户尚无画像：完成首次引导后建立。')
      }
      throw cause
    }
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
