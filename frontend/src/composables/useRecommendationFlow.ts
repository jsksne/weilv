import { reactive, ref } from 'vue'

import { ApiError, getRecommendation } from '@/api/client'
import type { RecommendationRequest, RecommendationResponse } from '@/api/types'

function initialForm(): RecommendationRequest {
  return {
    user_id: 'demo-user-001',
    query: '',
    target_stage: 'junior_high',
    current_context: 'home',
    activity_context: 'writing',
    available_minutes: 10,
    vision_abnormal: false,
    physical_discomfort: false,
    medical_request: false,
    cannot_move: false,
    unstable_environment: false,
    sleep_being_crowded: false,
  }
}

export function useRecommendationFlow() {
  const form = reactive<RecommendationRequest>(initialForm())
  const loading = ref(false)
  const result = ref<RecommendationResponse | null>(null)
  const error = ref<ApiError | null>(null)
  const submittedRequest = ref<RecommendationRequest | null>(null)

  async function submit(): Promise<void> {
    if (loading.value) return

    loading.value = true
    result.value = null
    error.value = null
    submittedRequest.value = null
    const request = { ...form }
    try {
      result.value = await getRecommendation(request)
      submittedRequest.value = request
    } catch (cause) {
      error.value =
        cause instanceof ApiError
          ? cause
          : new ApiError(0, '无法连接服务', 'network_error')
    } finally {
      loading.value = false
    }
  }

  function updateField<K extends keyof RecommendationRequest>(
    field: K,
    value: RecommendationRequest[K],
  ): void {
    form[field] = value
  }

  function reset(): void {
    Object.assign(form, initialForm())
    result.value = null
    error.value = null
    submittedRequest.value = null
  }

  return {
    form,
    loading,
    result,
    error,
    submittedRequest,
    updateField,
    submit,
    reset,
  }
}
