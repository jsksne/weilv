import { computed, reactive, ref, type Ref } from 'vue'

import type {
  OnboardingAnswerValue,
  OnboardingContract,
  OnboardingStepContract,
} from '@/contracts'

export const DEMO_ONBOARDING_STORAGE_KEY = 'wl_aurora_onboarded'

export type OnboardingFlowStatus = 'active' | 'completed' | 'skipped'

export interface OnboardingController {
  index: Ref<number>
  currentStep: Ref<OnboardingStepContract | undefined>
  total: Ref<number>
  isFirst: Ref<boolean>
  isLast: Ref<boolean>
  answers: Record<string, OnboardingAnswerValue>
  status: Ref<OnboardingFlowStatus>
  next: () => void
  back: () => void
  skip: () => void
  complete: () => void
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

export function useOnboarding(model: OnboardingContract): OnboardingController {
  const index = ref(0)
  const total = computed(() => model.steps.length)
  const currentStep = computed(() => model.steps[index.value])
  const isFirst = computed(() => index.value === 0)
  const isLast = computed(() => total.value > 0 && index.value === total.value - 1)
  const status = ref<OnboardingFlowStatus>('active')
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

  function next(): void {
    if (isLast.value) complete()
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
    next,
    back,
    skip,
    complete,
    setAnswer,
    answered,
  }
}
