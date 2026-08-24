import { ApiError, getAgenticRecommendation, getRecommendation, getUserProfile, upsertUserProfile } from '@/api/client'
import type { RecommendationRequest, TargetStage } from '@/api/types'
import type { OnboardingSubmitAnswers, OnboardingSubmitResult, UiDataSource } from '@/contracts'
import {
  adaptAgenticRecommendation,
  adaptProfileResponse,
  adaptRecommendationResponse,
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

export class ApiUiDataSource implements UiDataSource {
  private readonly userId?: string
  private readonly recommendationRequest?: RecommendationRequest

  constructor(options: ApiUiDataSourceOptions = {}) {
    this.userId = options.userId
    this.recommendationRequest = options.recommendationRequest
  }

  getShell() {
    return Promise.resolve(createProductionShellContract())
  }

  getToday() {
    if (!hasCompleteRecommendationRequest(this.recommendationRequest)) {
      return Promise.resolve(
        createUnavailableTodayContract('Production Today context unavailable：缺少真实 RecommendationRequest。'),
      )
    }

    return getRecommendation(this.recommendationRequest).then(adaptRecommendationResponse)
  }

  getAssistant() {
    return Promise.resolve(createProductionAssistantContract())
  }

  async askAssistant(question: string) {
    if (!hasCompleteRecommendationRequest(this.recommendationRequest)) {
      throw new UiDataContextUnavailableError(
        'Production Assistant context unavailable：缺少真实 RecommendationRequest。',
      )
    }

    return getAgenticRecommendation({
      ...this.recommendationRequest,
      query: question,
    }).then(adaptAgenticRecommendation)
  }

  async getProfile() {
    if (!this.userId) {
      return createUnavailableProfileContract('Production Profile unavailable：缺少真实 userId。')
    }

    try {
      const profile = await getUserProfile(this.userId)
      return adaptProfileResponse(profile)
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

  getWeekly() {
    return Promise.resolve(createUnavailableWeeklyContract())
  }
}
