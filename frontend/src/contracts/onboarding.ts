import type { UiState } from './common'

export type OnboardingAnswerValue = string | string[]
export type OnboardingStepKind = 'welcome' | 'choices' | 'generation'
export type QuestionnaireCompatibilityStatus = 'contractMismatch' | 'unavailable'

export interface OnboardingChoice {
  value: string
  label: string
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
  steps: readonly OnboardingStepContract[]
  totalSteps: number
  initialAnswers: Readonly<Record<string, OnboardingAnswerValue>>
  summary: OnboardingSummaryContract
  questionnaire: QuestionnairePresentationContract
  questionnaireCompatibility: QuestionnaireCompatibilityContract
  storageKey: string
}
