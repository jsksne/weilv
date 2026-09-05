import type { UiState } from './common'

export type AssistantScenario = 'exam' | 'sleep' | 'neck' | 'fallback'
export type AssistantPromptId = Exclude<AssistantScenario, 'fallback'>
export type AssistantStageId = 'analysis' | 'retrieval' | 'answer'
export type AssistantStageStatus = 'pending' | 'active' | 'done' | 'unavailable'
export type AssistantSafetyStatus = 'allowed' | 'blocked' | 'help_seeking' | 'no_safe_task'

export interface AssistantTextSegment {
  text: string
  emphasis?: boolean
  breakBefore?: boolean
}

export interface AssistantQuickPrompt {
  id: AssistantPromptId
  label: string
  question: string
}

export interface AssistantGreeting {
  face: string
  segments: readonly AssistantTextSegment[]
}

export interface AssistantAnalysisItem {
  id: string
  title: string
  direction: string
}

export interface AssistantKnowledgeChunk {
  id: string
  source: string
  text: string | null
  relevance: number | null
}

export interface AssistantSource {
  label: string
  url?: string
}

/** F2：建议任务在今日清单中的落地状态（由 App 按今日 entries 解析）。 */
export type SuggestedTaskState = 'absent' | 'pending' | 'started' | 'done'

export interface AssistantSuggestedTask {
  taskId: string
  icon: string
  title: string
  meta: string
  actionLabel: string
  /** F2：本次 Agentic 执行的正式记录 id；无真实记录时缺省（不可捏造）。 */
  recommendationId?: string
  /** 正式任务说明，用于加入今日时完整建卡。 */
  instruction?: string
  domains?: readonly string[]
}

export interface AssistantSafetyNotice {
  status: AssistantSafetyStatus
  title: string
  paragraphs: readonly string[]
  rule: string
}

export type AssistantStageLabels = Partial<Record<AssistantStageStatus, string>>

export interface AssistantStageBase {
  id: AssistantStageId
  title: string
  status: AssistantStageStatus
  statusLabel: string
  statusLabels: AssistantStageLabels
  visible: boolean
}

export interface AssistantAnalysisStage extends AssistantStageBase {
  id: 'analysis'
  lead: string | null
  items: readonly AssistantAnalysisItem[]
}

export interface AssistantRetrievalStage extends AssistantStageBase {
  id: 'retrieval'
  chunks: readonly AssistantKnowledgeChunk[]
}

export interface AssistantAnswerStage extends AssistantStageBase {
  id: 'answer'
}

export interface AssistantPipeline {
  analysis: AssistantAnalysisStage
  retrieval: AssistantRetrievalStage
  answer: AssistantAnswerStage
}

export interface AssistantTiming {
  analysisCard: number
  analysisFill: number
  retrievalCard: number
  retrievalFill: number
  answer: number
}

export interface AssistantReply {
  id: string
  scenario: AssistantScenario | null
  pipeline: AssistantPipeline
  answer: readonly AssistantTextSegment[]
  suggestedTask: AssistantSuggestedTask | null
  safety: AssistantSafetyNotice | null
  sources: readonly AssistantSource[]
  /** Production Output Guard 使用固定安全兜底时的透明提示；Demo 可省略。 */
  guardNotice?: string | null
  /** “本次考虑”：来自本次请求真实字段的条件摘要（最多 3 条）。 */
  considered?: readonly string[]
  traceIsReal: boolean
  timing: AssistantTiming | null
}

/** B3：前端公开的粗粒度执行阶段（真实 backend 事件映射，非 fake）。 */
export type AssistantTraceStage =
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

export type AssistantTraceStatus = 'active' | 'complete' | 'error'

export interface AssistantTraceStageResult {
  analysis?: {
    lead: string | null
    items: readonly AssistantAnalysisItem[]
  }
  retrieval?: {
    chunks: readonly AssistantKnowledgeChunk[]
  }
}

/** B3：一次 UI 级 trace 事件（由 DataSource 从 sanitized DTO 映射而来）。 */
export interface AssistantTraceEvent {
  stage: AssistantTraceStage
  status: AssistantTraceStatus
  label: string
  stageResult?: AssistantTraceStageResult
}

export interface AssistantContract {
  state: UiState
  isDemo: boolean
  traceIsReal: boolean
  demoLabel: string
  quickPrompts: readonly AssistantQuickPrompt[]
  greeting: AssistantGreeting
  replies: Readonly<Record<AssistantScenario, AssistantReply>>
}
