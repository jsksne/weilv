export type TargetStage = 'primary_upper' | 'junior_high' | 'senior_high'

export type CurrentContext =
  | 'home'
  | 'school'
  | 'study_space'
  | 'commute'
  | 'bedroom'
  | 'outdoor'
  | 'unknown'

export type ActivityContext = 'reading' | 'writing' | 'screen' | 'other' | 'unknown'

export type RecommendationStatus = 'allowed' | 'blocked' | 'help_seeking' | 'no_safe_task'

export interface RecommendationRequest {
  user_id: string
  query: string
  target_stage: TargetStage
  current_context: CurrentContext
  activity_context?: ActivityContext
  available_minutes?: number | null
  vision_abnormal?: boolean
  physical_discomfort?: boolean
  medical_request?: boolean
  cannot_move?: boolean
  unstable_environment?: boolean
  sleep_being_crowded?: boolean
}

export interface SelectedTask {
  task_id: string
  title: string
  instruction: string
  evidence_chunk_ids: string[]
  covered_domains: string[]
  estimated_minutes: number
}

export interface EvidenceSource {
  chunk_id: string
  document_id: string
  source_locator: string
  source_url: string
}

export interface ExplanationGuard {
  passed: boolean
  fallback_used: boolean
  reason_codes: string[]
}

export interface PersonalizationAudit {
  memory_used: boolean
  memory_ids: string[]
  base_task_rank: number
  personalization_delta: number
  adjusted_rank: number
  reason_codes: string[]
}

export interface RecommendationResponse {
  status: RecommendationStatus
  selected_task: SelectedTask | null
  explanation: string | null
  sources: EvidenceSource[]
  context_sources: EvidenceSource[] | null
  matched_rule_ids: string[]
  reason_codes: string[]
  explanation_guard: ExplanationGuard | null
  personalization: PersonalizationAudit | null
  recommendation_id: string | null
  feedback_available: boolean
}

export interface AgenticDiagnostics {
  agentic?: boolean
  factor_count?: number
  factor_domains?: string[]
  analysis_fallback?: boolean
  knowledge_chunk_ids_by_factor?: Record<string, string[]>
  [key: string]: unknown
}

export interface AgenticRecommendationResponse extends RecommendationResponse {
  agentic: boolean
  diagnostics: AgenticDiagnostics
}

export interface UserProfileUpsertRequest {
  target_stage: TargetStage
  memory_enabled: boolean
}

export interface UserProfile extends UserProfileUpsertRequest {
  user_id: string
  created_at: string
  updated_at: string
}

export type CompletionStatus = 'completed' | 'partially_completed' | 'skipped'
export type Usefulness = 'helpful' | 'neutral' | 'not_helpful'
export type Difficulty = 'easy' | 'suitable' | 'difficult'

export interface FeedbackRequest {
  completion_status: CompletionStatus
  usefulness: Usefulness
  difficulty: Difficulty
  reason: string
}

export interface FeedbackResponse {
  status: string
  recommendation_id: string
  task_id: string
  memory_persisted: boolean
  memory_id: string | null
  confidence: number | null
}

export interface HealthResponse {
  status: string
}

export type QuestionnaireCompletionState =
  | 'not_started'
  | 'partially_completed'
  | 'completed'
  | 'skipped'

export interface QuestionnaireOption {
  value: string
  label: string
}

export interface QuestionnaireQuestion {
  question_id: string
  title: string
  description: string | null
  option_type: 'single' | 'multi'
  required: boolean
  options: QuestionnaireOption[]
}

export interface QuestionnaireSchema {
  questionnaire_id: string
  questions: QuestionnaireQuestion[]
}

export type QuestionnaireAnswerValue = string | string[]

export interface QuestionnaireState {
  user_id: string
  questionnaire_id: string
  completion_state: QuestionnaireCompletionState
  updated_at: string | null
  completed_at: string | null
  answers: Record<string, QuestionnaireAnswerValue>
  memory_record_ids: string[]
}
