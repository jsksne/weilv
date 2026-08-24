import {
  getAgenticRecommendation,
  getQuestionnaireSchema,
  getQuestionnaireState,
  getRecommendation,
  getUserProfile,
} from '@/api/client'
import type { RecommendationRequest } from '@/api/types'
import type { UiDataSource } from '@/contracts'
import {
  adaptAgenticRecommendation,
  adaptOnboardingContract,
  adaptProfileResponse,
  adaptRecommendationResponse,
  createProductionAssistantContract,
  createProductionShellContract,
  createUnavailableProfileContract,
  createUnavailableTodayContract,
  createUnavailableWeeklyContract,
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

  getProfile() {
    if (!this.userId) {
      return Promise.resolve(
        createUnavailableProfileContract('Production Profile unavailable：缺少真实 userId。'),
      )
    }

    return getUserProfile(this.userId).then(adaptProfileResponse)
  }

  async getOnboarding() {
    if (!this.userId) {
      return adaptOnboardingContract(null, null)
    }

    const [schema, state] = await Promise.all([
      getQuestionnaireSchema(),
      getQuestionnaireState(this.userId),
    ])
    return adaptOnboardingContract(schema, state)
  }

  getWeekly() {
    return Promise.resolve(createUnavailableWeeklyContract())
  }
}
