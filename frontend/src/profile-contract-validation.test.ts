import type { QuestionnaireSchema, QuestionnaireState } from './api/types'
import {
  adaptOnboardingContract,
  adaptProfileAndQuestionnaire,
  adaptQuestionnaireResponse,
  adaptQuestionnaireSchemaResponse,
} from './data/adapters'

const schema: QuestionnaireSchema = {
  questionnaire_id: 'current-v2',
  questions: Array.from({ length: 7 }, (_, index) => ({
    question_id: `question-${index + 1}`,
    title: `当前问卷问题 ${index + 1}`,
    description: null,
    option_type: 'single' as const,
    required: false,
    options: [{ value: 'yes', label: '是' }],
  })),
}

const questionnaire: QuestionnaireState = {
  user_id: 'production-user',
  questionnaire_id: 'current-v2',
  completion_state: 'partially_completed',
  updated_at: '2026-08-24T08:00:00+08:00',
  completed_at: null,
  answers: { 'question-1': 'yes' },
  memory_record_ids: ['backend-memory-id'],
}

describe('Sprint 6 offline DTO to Contract validation', () => {
  it('maps questionnaire state and schema without guessing prototype answers', () => {
    const presentation = adaptQuestionnaireResponse(questionnaire, schema)
    const compatibility = adaptQuestionnaireSchemaResponse(schema)

    expect(presentation.status).toBe('available')
    expect(presentation.completionState).toBe('partially_completed')
    expect(presentation.answers).toEqual({ 'question-1': 'yes' })
    expect(presentation.questionCount).toBe(7)
    expect(compatibility.status).toBe('contractMismatch')
    expect(compatibility.prototypeStepCount).toBe(5)
    expect(compatibility.backendQuestionCount).toBe(7)
  })

  it('keeps Production profile gaps unavailable and never carries fixture Memory', () => {
    const { profile, onboarding } = adaptProfileAndQuestionnaire(
      { user_id: 'production-user', memory_enabled: false },
      schema,
      questionnaire,
    )

    expect(profile.state.mode).toBe('production')
    expect(profile.timePreference.status).toBe('unavailable')
    expect(profile.taskPreference.status).toBe('unavailable')
    expect(profile.completionPattern.percentage).toBeNull()
    expect(profile.memory.enabled).toBe(false)
    expect(profile.memory.items).toEqual([])
    expect(profile.memory.canDelete).toBe(false)
    expect(onboarding.state.mode).toBe('production')
    expect(onboarding.questionnaire.answers).toEqual({ 'question-1': 'yes' })
    expect(onboarding.questionnaireCompatibility.status).toBe('contractMismatch')
    expect(onboarding.steps).toEqual([])
  })

  it('returns unavailable when the schema is absent rather than fabricating a mapping', () => {
    const onboarding = adaptOnboardingContract(null, questionnaire)

    expect(onboarding.state.status).toBe('unavailable')
    expect(onboarding.questionnaire.status).toBe('unavailable')
    expect(onboarding.questionnaireCompatibility.status).toBe('unavailable')
    expect(onboarding.questionnaireCompatibility.backendQuestionCount).toBeNull()
    expect(onboarding.steps).toEqual([])
  })
})
