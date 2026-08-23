import { computed, reactive, ref } from 'vue'

import {
  ApiError,
  getQuestionnaireSchema,
  getQuestionnaireState,
  saveQuestionnaire,
  skipQuestionnaire,
} from '@/api/client'
import type {
  QuestionnaireAnswerValue,
  QuestionnaireQuestion,
  QuestionnaireState,
} from '@/api/types'

export type QuestionnaireStatus =
  | 'idle'
  | 'loading'
  | 'active'
  | 'completed'
  | 'skipped'
  | 'error'

export function useQuestionnaire() {
  const questions = ref<QuestionnaireQuestion[]>([])
  const index = ref(0)
  const answers = reactive<Record<string, QuestionnaireAnswerValue>>({})
  const state = ref<QuestionnaireState | null>(null)
  const status = ref<QuestionnaireStatus>('idle')
  const saving = ref(false)
  const error = ref<ApiError | null>(null)

  const question = computed(() => questions.value[index.value] ?? null)
  const isLast = computed(() => index.value === questions.value.length - 1)
  const total = computed(() => questions.value.length)
  const progress = computed(() =>
    total.value ? Math.round(((index.value + 1) / total.value) * 100) : 0,
  )
  const answeredCount = computed(
    () => questions.value.filter((item) => isAnswered(item.question_id)).length,
  )

  function isAnswered(questionId: string): boolean {
    const value = answers[questionId]
    if (Array.isArray(value)) return value.length > 0
    return value !== undefined && value !== ''
  }

  async function load(userId: string): Promise<void> {
    status.value = 'loading'
    error.value = null
    try {
      const schema = await getQuestionnaireSchema()
      questions.value = schema.questions
      const record = await getQuestionnaireState(userId)
      state.value = record
      // never leak a previous user's answers into a fresh session
      for (const key of Object.keys(answers)) delete answers[key]
      index.value = 0
      if (record.completion_state === 'completed' || record.completion_state === 'skipped') {
        status.value = record.completion_state
        return
      }
      Object.assign(answers, record.answers)
      const resumeAt = questions.value.findIndex((item) => !isAnswered(item.question_id))
      index.value = resumeAt === -1 ? 0 : resumeAt
      status.value = 'active'
    } catch (cause) {
      error.value =
        cause instanceof ApiError ? cause : new ApiError(0, '无法连接服务', 'network_error')
      status.value = 'error'
    }
  }

  function setAnswer(questionId: string, value: QuestionnaireAnswerValue): void {
    answers[questionId] = value
  }

  function next(): void {
    const current = question.value
    if (!current) return
    if (current.required && !isAnswered(current.question_id)) return
    if (index.value < questions.value.length - 1) index.value += 1
  }

  function back(): void {
    if (index.value > 0) index.value -= 1
  }

  function answered(questionId: string): QuestionnaireAnswerValue | undefined {
    return answers[questionId]
  }

  async function finish(userId: string): Promise<void> {
    saving.value = true
    error.value = null
    try {
      const saved = await saveQuestionnaire(userId, { ...answers })
      state.value = saved
      status.value =
        saved.completion_state === 'completed' || saved.completion_state === 'skipped'
          ? saved.completion_state
          : 'active'
    } catch (cause) {
      error.value =
        cause instanceof ApiError ? cause : new ApiError(0, '无法连接服务', 'network_error')
      status.value = 'error'
    } finally {
      saving.value = false
    }
  }

  async function skip(userId: string): Promise<void> {
    saving.value = true
    error.value = null
    try {
      const record = await skipQuestionnaire(userId)
      state.value = record
      status.value = 'skipped'
    } catch (cause) {
      error.value =
        cause instanceof ApiError ? cause : new ApiError(0, '无法连接服务', 'network_error')
      status.value = 'error'
    } finally {
      saving.value = false
    }
  }

  return {
    questions,
    question,
    index,
    total,
    progress,
    isLast,
    answeredCount,
    answers,
    state,
    status,
    saving,
    error,
    load,
    setAnswer,
    next,
    back,
    answered,
    finish,
    skip,
  }
}
