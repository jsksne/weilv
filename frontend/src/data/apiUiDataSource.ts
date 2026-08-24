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
  createUnavailableWeeklyContract,
} from './adapters'

const defaultRecommendationRequest: RecommendationRequest = {
  user_id: 'demo-user-001',
  query: '请给我一个今天可以完成的微任务',
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

export interface ApiUiDataSourceOptions {
  userId?: string
  recommendationRequest?: Partial<RecommendationRequest>
}

export class ApiUiDataSource implements UiDataSource {
  private readonly userId: string
  private readonly recommendationRequest: RecommendationRequest

  constructor(options: ApiUiDataSourceOptions = {}) {
    this.userId = options.userId ?? defaultRecommendationRequest.user_id
    this.recommendationRequest = {
      ...defaultRecommendationRequest,
      ...options.recommendationRequest,
      user_id: this.userId,
    }
  }

  getShell() {
    return Promise.resolve(createProductionShellContract())
  }

  getToday() {
    return getRecommendation(this.recommendationRequest).then(adaptRecommendationResponse)
  }

  getAssistant() {
    return Promise.resolve(createProductionAssistantContract())
  }

  askAssistant(question: string) {
    return getAgenticRecommendation({
      ...this.recommendationRequest,
      query: question,
    }).then(adaptAgenticRecommendation)
  }

  getProfile() {
    return getUserProfile(this.userId).then(adaptProfileResponse)
  }

  async getOnboarding() {
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
