import { ref } from 'vue'

import type { UiDataBundle, UiDataSource } from '@/contracts'

export type UiDataSourceStatus = 'idle' | 'loading' | 'ready' | 'error'

export function useUiDataSource(
  source: UiDataSource | null,
  options: { autoLoad?: boolean } = {},
) {
  const status = ref<UiDataSourceStatus>('idle')
  const data = ref<UiDataBundle | null>(null)
  const error = ref<Error | null>(null)

  const initialData = source?.getInitialData?.()
  if (initialData) {
    data.value = initialData
    status.value = 'ready'
  }

  async function load(): Promise<void> {
    if (!source || status.value === 'loading') return

    status.value = 'loading'
    error.value = null
    data.value = null
    try {
      const [shell, today, assistant, profile, onboarding, weekly] = await Promise.all([
        source.getShell(),
        source.getToday(),
        source.getAssistant(),
        source.getProfile(),
        source.getOnboarding(),
        source.getWeekly(),
      ])
      data.value = { shell, today, assistant, profile, onboarding, weekly }
      status.value = 'ready'
    } catch (cause) {
      error.value = cause instanceof Error ? cause : new Error('UI 数据加载失败。')
      status.value = 'error'
    }
  }

  if (options.autoLoad !== false && !initialData) void load()

  return { status, data, error, load, retry: load }
}
