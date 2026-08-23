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

export function useFeedbackFlow() {
  const input = reactive<FeedbackRequest>(initialInput())
  const loading = ref(false)
  const result = ref<FeedbackResponse | null>(null)
  const error = ref<ApiError | null>(null)

  function updateField<K extends keyof FeedbackRequest>(
    field: K,
    value: FeedbackRequest[K],
  ): void {
    input[field] = value
  }

  async function submit(userId: string, recommendationId: string): Promise<void> {
    if (loading.value) return

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
  }

  return {
    input,
    loading,
    result,
    error,
    updateField,
    submit,
    reset,
  }
}
