import { reactive, ref } from 'vue'

import { ApiError, submitFeedback } from '@/api/client'
import type { FeedbackRequest, FeedbackResponse } from '@/api/types'

export type FeedbackFlowMode = 'demo' | 'production'

export interface FeedbackDraft {
  completion_status: FeedbackRequest['completion_status'] | null
  usefulness: FeedbackRequest['usefulness'] | null
  difficulty: FeedbackRequest['difficulty'] | null
  reason: string | null
}

function initialInput(mode: FeedbackFlowMode): FeedbackDraft {
  if (mode === 'production') {
    return {
      completion_status: null,
      usefulness: null,
      difficulty: null,
      reason: null,
    }
  }

  return {
    completion_status: 'completed',
    usefulness: 'neutral',
    difficulty: 'suitable',
    reason: '',
  }
}

export interface PendingFeedback {
  completion_status: FeedbackRequest['completion_status']
}

function toFeedbackRequest(input: FeedbackDraft): FeedbackRequest | null {
  if (
    input.completion_status === null ||
    input.usefulness === null ||
    input.difficulty === null ||
    input.reason === null
  ) {
    return null
  }

  return {
    completion_status: input.completion_status,
    usefulness: input.usefulness,
    difficulty: input.difficulty,
    reason: input.reason,
  }
}

export function useFeedbackFlow(options: { mode?: FeedbackFlowMode } = {}) {
  const mode = options.mode ?? 'demo'
  const input = reactive<FeedbackDraft>(initialInput(mode))
  const loading = ref(false)
  const result = ref<FeedbackResponse | null>(null)
  const error = ref<ApiError | null>(null)
  const pendingFeedback = ref<PendingFeedback | null>(null)

  function updateField<K extends keyof FeedbackDraft>(
    field: K,
    value: FeedbackDraft[K],
  ): void {
    input[field] = value
  }

  async function submit(userId: string, recommendationId: string): Promise<void> {
    if (loading.value) return

    if (mode === 'production') {
      if (input.completion_status === null) return
      pendingFeedback.value = { completion_status: input.completion_status }
      result.value = null
      error.value = null
      return
    }

    const payload = toFeedbackRequest(input)
    if (!payload) return

    loading.value = true
    result.value = null
    error.value = null
    try {
      result.value = await submitFeedback(userId, recommendationId, payload)
    } catch (cause) {
      error.value =
        cause instanceof ApiError
          ? cause
          : new ApiError(0, '无法连接服务', 'network_error')
    } finally {
      loading.value = false
    }
  }

  function reset(): void {
    Object.assign(input, initialInput(mode))
    result.value = null
    error.value = null
    pendingFeedback.value = null
  }

  return {
    input,
    loading,
    result,
    error,
    pendingFeedback,
    updateField,
    submit,
    reset,
  }
}
