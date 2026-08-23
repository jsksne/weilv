import { ref } from 'vue'

import { ApiError, healthCheck } from '@/api/client'

export function useServiceHealth() {
  const loading = ref(false)
  const connected = ref(false)
  const error = ref<ApiError | null>(null)

  async function refresh(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      await healthCheck()
      connected.value = true
    } catch (cause) {
      connected.value = false
      error.value =
        cause instanceof ApiError
          ? cause
          : new ApiError(0, '无法连接服务', 'network_error')
    } finally {
      loading.value = false
    }
  }

  void refresh()

  return {
    loading,
    connected,
    error,
    refresh,
  }
}
