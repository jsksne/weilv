import {
  ApiError,
  deleteUserMemory,
  getAgenticRecommendation,
  getRecommendation,
  getUserMemories,
  getUserProfile,
  getWeekly,
  postTaskEvent,
  upsertUserProfile,
} from '@/api/client'
import type { RecommendationRequest, TargetStage } from '@/api/types'
import type {
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

  constructor(options: ApiUiDataSourceOptions = {}) {
    this.userId = options.userId
    this.recommendationRequest = options.recommendationRequest
    this.recommendationContext = options.recommendationContext
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
      return queryOverride
        ? { ...this.recommendationRequest, query: queryOverride }
        : this.recommendationRequest
    }
    const { targetStage } = await this.ensureProfile()
    if (!targetStage) return null
    const context = this.recommendationContext ?? {
      query: '请为我推荐一个适合现在完成的微任务。',
      current_context: 'unknown' as const,
      activity_context: 'unknown' as const,
    }
    return {
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
    }
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
    return getAgenticRecommendation(request).then(adaptAgenticRecommendation)
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
      try {
        memories = adaptMemoryListResponse(await getUserMemories(this.userId))
      } catch (cause) {
        // Memory list 失败不拖垮 Profile；保持 Memory 部分 unavailable。
        if (!(cause instanceof ApiError)) throw cause
      }
      return adaptProfileResponse(profile, memories)
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
    const { start, end } = trailingWeekDates(new Date())
    const dto = await getWeekly(this.userId, start, end)
    return dto
      ? adaptWeeklyResponse(dto)
      : createUnavailableWeeklyContract('Production Weekly 返回空数据，暂不可用。')
  }
}
