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

export interface PublicRagFactor {
  factor_id: string
  subquery: string
  evidence_need: string
  domain_hint: string | null
}

export interface PublicRagKnowledgeChunk {
  factor_id: string
  chunk_id: string
  source_locator: string
  source_url: string | null
  excerpt: string
}

export interface PublicRagTrace {
  analysis_fallback?: boolean
  factors: PublicRagFactor[]
  knowledge_chunks: PublicRagKnowledgeChunk[]
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
  public_rag?: PublicRagTrace | null
  matched_rule_ids: string[]
  reason_codes: string[]
  explanation_guard: ExplanationGuard | null
  personalization: PersonalizationAudit | null
  recommendation_id: string | null
  feedback_available: boolean
  /** B1：同一次 recommendation run 的 surfaced tasks（0～3 条）。 */
  tasks?: SurfacedTask[] | null
}

export interface SurfacedTask {
  recommendation_id: string | null
  task_id: string
  title: string
  instruction: string
  estimated_minutes: number
  sources: EvidenceSource[]
}

export type TaskAction =
  | 'started'
  | 'completed'
  | 'partially_completed'
  | 'skipped'
  | 'replaced'
  | 'restored'

export interface TaskEventRequest {
  action: TaskAction
}

export interface TaskEventResponse {
  status: string
  recommendation_id: string
  task_id: string
  action: string
  recorded_at: string
}

export interface MemoryItem {
  memory_id: string
  memory_type: string
  summary: string
  created_at: string
  updated_at: string
}

export interface MemoryListResponse {
  user_id: string
  memory_enabled: boolean
  memories: MemoryItem[]
}

export interface MemoryDeleteResponse {
  status: string
  memory_id: string
}

export interface WeeklyEvent {
  recommendation_id: string
  task_id: string
  title: string | null
  action: string
  recorded_at: string
}

export interface WeeklyDay {
  date: string
  completed_minutes: number
  action_counts: Record<string, number>
}

export interface WeeklyTotals {
  completed_minutes: number
  action_counts: Record<string, number>
}

export interface WeeklyResponse {
  user_id: string
  start_date: string
  end_date: string
  minutes_policy: string
  days: WeeklyDay[]
  totals: WeeklyTotals
  events: WeeklyEvent[]
  adjustments: WeeklyEvent[]
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

/** B3：backend 公开的粗粒度 Agentic trace 阶段（真实 pipeline 映射，非 fake）。 */
export type AgentTraceStage =
  | 'accepted'
  | 'safety'
  | 'analysis'
  | 'retrieval'
  | 'ranking'
  | 'memory'
  | 'personalization'
  | 'grounding'
  | 'generation'
  | 'completed'
  | 'error'

export type AgentTraceStatus = 'active' | 'complete' | 'error'

export interface AgentTraceStageResult {
  analysis?: {
    analysis_fallback: boolean
    factors: PublicRagFactor[]
  }
  retrieval?: {
    knowledge_chunks: PublicRagKnowledgeChunk[]
  }
}

/** B3：一次 sanitized 公共 trace 事件（NDJSON 流中的一行）。 */
export interface AgentTraceEventDto {
  stage: AgentTraceStage
  status: AgentTraceStatus
  label: string
  sequence?: number
  timestamp_ms?: number
  /** analysis/retrieval 完成时携带的 sanitized 阶段内容。 */
  stage_result?: AgentTraceStageResult | null
  /** 仅 completed 事件携带：同一次执行产生的最终 sanitized 回答（无内部 diagnostics）。 */
  result?: RecommendationResponse | null
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
