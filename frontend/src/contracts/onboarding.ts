import type { UiState } from './common'

export type OnboardingAnswerValue = string | string[]
export type OnboardingStepKind = 'welcome' | 'choices' | 'generation'
export type QuestionnaireCompatibilityStatus = 'contractMismatch' | 'unavailable'

/**
 * B6 Production onboarding 阶段：
 * loading / ready / submitting / completed / unavailable / error / unsupported。
 * 其中 unsupported 表示当前输入存在后端无法承载的值（例如不支持的学段）。
 */
export type OnboardingFlowPhase =
  | 'loading'
  | 'ready'
  | 'submitting'
  | 'completed'
  | 'unavailable'
  | 'error'
  | 'unsupported'

/** 单个引导字段的持久化真实状态（不假装保存成功）。 */
export type OnboardingPersistenceStatus = 'persisted' | 'unsupported' | 'unavailable'

export interface OnboardingPersistenceReport {
  fieldId: string
  status: OnboardingPersistenceStatus
  reason?: string
}

export interface OnboardingConsentContract {
  prompt: string
  note: string
}

/** Production 提交引导时需要的最小答案集合。 */
export interface OnboardingSubmitAnswers {
  grade?: string
  memoryEnabled: boolean
}

export interface OnboardingSubmitResult {
  status: 'completed' | 'unsupported' | 'error'
  message?: string
  persistence: readonly OnboardingPersistenceReport[]
}

export interface OnboardingChoice {
  value: string
  label: string
  /** false 表示该原型选项当前后端无合法对应值，Production 中应禁用并如实标注。 */
  supported?: boolean
}

export interface OnboardingChoiceGroup {
  id: string
  prompt: string
  multiple?: boolean
  options: readonly OnboardingChoice[]
  defaultValue?: string
  defaultValues?: readonly string[]
}

export interface OnboardingStepContract {
  id: string
  kind: OnboardingStepKind
  title: string
  intro?: readonly string[]
  groups?: readonly OnboardingChoiceGroup[]
}

export interface QuestionnairePresentationContract {
  status: 'available' | 'unavailable'
  questionnaireId: string | null
  completionState: string | null
  questionCount: number | null
  answers: Readonly<Record<string, OnboardingAnswerValue>>
}

export interface QuestionnaireCompatibilityContract {
  status: QuestionnaireCompatibilityStatus
  prototypeStepCount: number
  backendQuestionCount: number | null
  message: string
}

export interface OnboardingSummaryContract {
  title: string
  lines: readonly string[]
}

export interface OnboardingContract {
  state: UiState
  phase: OnboardingFlowPhase
  steps: readonly OnboardingStepContract[]
  totalSteps: number
  initialAnswers: Readonly<Record<string, OnboardingAnswerValue>>
  summary: OnboardingSummaryContract
  questionnaire: QuestionnairePresentationContract
  questionnaireCompatibility: QuestionnaireCompatibilityContract
  persistence: readonly OnboardingPersistenceReport[]
  consent: OnboardingConsentContract
  storageKey: string
}
