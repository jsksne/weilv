import { reactive, ref } from 'vue'

import { ApiError, submitFeedback } from '@/api/client'
import type { FeedbackRequest, FeedbackResponse } from '@/api/types'

function initialInput(): FeedbackRequest {
  return {
    completion_status: 'completed',
    usefulness: 'neutral',
    difficulty: 'suitable',
    reason: '',
  }
}

export type FeedbackFlowMode = 'demo' | 'production'

export interface PendingFeedback {
  completion_status: FeedbackRequest['completion_status']
}

export function useFeedbackFlow(options: { mode?: FeedbackFlowMode } = {}) {
  const mode = options.mode ?? 'demo'
  const input = reactive<FeedbackRequest>(initialInput())
  const loading = ref(false)
  const result = ref<FeedbackResponse | null>(null)
  const error = ref<ApiError | null>(null)
  const pendingFeedback = ref<PendingFeedback | null>(null)

  function updateField<K extends keyof FeedbackRequest>(
    field: K,
    value: FeedbackRequest[K],
  ): void {
    input[field] = value
  }

  async function submit(userId: string, recommendationId: string): Promise<void> {
    if (loading.value) return

    if (mode === 'production') {
      pendingFeedback.value = { completion_status: input.completion_status }
      result.value = null
      error.value = null
      return
    }

    loading.value = true
    result.value = null
    error.value = null
    try {
      result.value = await submitFeedback(userId, recommendationId, { ...input })
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
    Object.assign(input, initialInput())
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
