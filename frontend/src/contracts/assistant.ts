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

export interface AssistantSuggestedTask {
  icon: string
  title: string
  meta: string
  actionLabel: string
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

/** B3：一次 UI 级 trace 事件（由 DataSource 从 sanitized DTO 映射而来）。 */
export interface AssistantTraceEvent {
  stage: AssistantTraceStage
  status: AssistantTraceStatus
  label: string
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
