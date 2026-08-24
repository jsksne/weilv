import { computed, reactive, ref, type Ref } from 'vue'

import type {
  OnboardingAnswerValue,
  OnboardingContract,
  OnboardingStepContract,
  OnboardingSubmitAnswers,
  OnboardingSubmitResult,
} from '@/contracts'

export const DEMO_ONBOARDING_STORAGE_KEY = 'wl_aurora_onboarded'

export type OnboardingFlowStatus = 'active' | 'completed' | 'skipped'
export type OnboardingSubmitPhase = 'idle' | 'submitting' | 'completed' | 'error' | 'unsupported'

export interface OnboardingController {
  index: Ref<number>
  currentStep: Ref<OnboardingStepContract | undefined>
  total: Ref<number>
  isFirst: Ref<boolean>
  isLast: Ref<boolean>
  answers: Record<string, OnboardingAnswerValue>
  status: Ref<OnboardingFlowStatus>
  phase: Ref<OnboardingSubmitPhase>
  submitMessage: Ref<string>
  consent: Ref<boolean>
  setConsent: (granted: boolean) => void
  next: () => void
  back: () => void
  skip: () => void
  complete: () => void
  submit: () => Promise<void>
  setAnswer: (id: string, value: OnboardingAnswerValue) => void
  answered: (id: string) => OnboardingAnswerValue | undefined
}

function hasStorage(): boolean {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined'
}

export function hasDemoOnboardingCompleted(key = DEMO_ONBOARDING_STORAGE_KEY): boolean {
  if (!hasStorage()) return false
  try {
    return window.localStorage.getItem(key) === '1'
  } catch {
    return false
  }
}

function markDemoOnboardingCompleted(model: OnboardingContract): void {
  if (model.state.mode !== 'demo' || !hasStorage()) return
  try {
    window.localStorage.setItem(model.storageKey || DEMO_ONBOARDING_STORAGE_KEY, '1')
  } catch {
    // Demo progress is best effort; no questionnaire or health data is persisted.
  }
}

function cloneAnswers(
  source: Readonly<Record<string, OnboardingAnswerValue>>,
): Record<string, OnboardingAnswerValue> {
  return Object.fromEntries(
    Object.entries(source).map(([id, value]) => [id, Array.isArray(value) ? [...value] : value]),
  )
}

export function useOnboarding(
  model: OnboardingContract,
  submitFn?: (answers: OnboardingSubmitAnswers) => Promise<OnboardingSubmitResult>,
): OnboardingController {
  const index = ref(0)
  const total = computed(() => model.steps.length)
  const currentStep = computed(() => model.steps[index.value])
  const isFirst = computed(() => index.value === 0)
  const isLast = computed(() => total.value > 0 && index.value === total.value - 1)
  const status = ref<OnboardingFlowStatus>('active')
  const phase = ref<OnboardingSubmitPhase>('idle')
  const submitMessage = ref('')
  const consent = ref(false)
  const answers = reactive<Record<string, OnboardingAnswerValue>>(cloneAnswers(model.initialAnswers))

  function setAnswer(id: string, value: OnboardingAnswerValue): void {
    answers[id] = Array.isArray(value) ? [...value] : value
  }

  function answered(id: string): OnboardingAnswerValue | undefined {
    return answers[id]
  }

  function complete(): void {
    markDemoOnboardingCompleted(model)
    status.value = 'completed'
  }

  function skip(): void {
    markDemoOnboardingCompleted(model)
    status.value = 'skipped'
  }

  function setConsent(granted: boolean): void {
    consent.value = granted
  }

  async function submit(): Promise<void> {
    if (!submitFn) {
      // Demo / 无提交通道：本地完成，不产生任何后端调用。
      complete()
      return
    }
    phase.value = 'submitting'
    submitMessage.value = ''
    try {
      const grade = answers.grade
      const result = await submitFn({
        grade: typeof grade === 'string' ? grade : undefined,
        memoryEnabled: consent.value,
      })
      if (result.status !== 'completed') {
        phase.value = result.status
        submitMessage.value = result.message ?? ''
        return
      }
    } catch (cause) {
      phase.value = 'error'
      submitMessage.value = cause instanceof Error ? cause.message : '保存引导结果失败。'
      return
    }
    phase.value = 'completed'
    status.value = 'completed'
  }

  function next(): void {
    if (isLast.value) void submit()
    else if (index.value < total.value - 1) index.value += 1
  }

  function back(): void {
    if (index.value > 0 && status.value === 'active') index.value -= 1
  }

  return {
    index,
    currentStep,
    total,
    isFirst,
    isLast,
    answers,
    status,
    phase,
    submitMessage,
    consent,
    setConsent,
    next,
    back,
    skip,
    complete,
    submit,
    setAnswer,
    answered,
  }
}
