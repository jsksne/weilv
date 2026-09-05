import { ref } from 'vue'

import type { OnboardingContract, UiDataBundle, UiDataSource } from '@/contracts'

export type UiDataSourceStatus = 'idle' | 'loading' | 'ready' | 'error'

export interface UiLoadProgress {
  completed: number
  total: number
  percent: number
  stage: string
}

const LOAD_TOTAL = 6

function progressStage(completed: number): string {
  if (completed === 0) return '连接微律'
  if (completed <= 2) return '读取你的状态'
  if (completed < LOAD_TOTAL) return '整理今日微行动'
  return '准备好了'
}

export function useUiDataSource(
  source: UiDataSource | null,
  options: { autoLoad?: boolean } = {},
) {
  const status = ref<UiDataSourceStatus>('idle')
  const data = ref<UiDataBundle | null>(null)
  const onboarding = ref<OnboardingContract | null>(null)
  const error = ref<Error | null>(null)
  const progress = ref<UiLoadProgress>({
    completed: 0,
    total: LOAD_TOTAL,
    percent: 0,
    stage: progressStage(0),
  })
  let inFlight: Promise<void> | null = null
  let loadVersion = 0

  const initialData = source?.getInitialData?.()
  if (initialData) {
    data.value = initialData
    onboarding.value = initialData.onboarding
    status.value = 'ready'
    progress.value = {
      completed: LOAD_TOTAL,
      total: LOAD_TOTAL,
      percent: 100,
      stage: progressStage(LOAD_TOTAL),
    }
  }

  function startLoad(): Promise<void> {
    if (!source) return Promise.resolve()
    const version = ++loadVersion
    status.value = 'loading'
    error.value = null
    data.value = null
    onboarding.value = null
    progress.value = {
      completed: 0,
      total: LOAD_TOTAL,
      percent: 0,
      stage: progressStage(0),
    }

    const track = <T>(request: Promise<T>, onResolve?: (value: T) => void): Promise<T> =>
      request.then(value => {
        if (version === loadVersion && status.value === 'loading') {
          onResolve?.(value)
          const completed = progress.value.completed + 1
          progress.value = {
            completed,
            total: LOAD_TOTAL,
            percent: Math.round((completed / LOAD_TOTAL) * 100),
            stage: progressStage(completed),
          }
        }
        return value
      })

    const operation = (async () => {
      try {
        const [shell, today, assistant, profile, onboardingModel, weekly] = await Promise.all([
          track(source.getShell()),
          track(source.getToday()),
          track(source.getAssistant()),
          track(source.getProfile()),
          track(source.getOnboarding(), model => { onboarding.value = model }),
          track(source.getWeekly()),
        ])
        data.value = { shell, today, assistant, profile, onboarding: onboardingModel, weekly }
        status.value = 'ready'
      } catch (cause) {
        error.value = cause instanceof Error ? cause : new Error('UI 数据加载失败。')
        status.value = 'error'
      }
    })()

    const current = operation.finally(() => {
      if (inFlight === current) inFlight = null
    })
    inFlight = current
    return current
  }

  function load(): Promise<void> {
    return inFlight ?? startLoad()
  }

  async function reload(): Promise<void> {
    if (inFlight) await inFlight
    return startLoad()
  }

  /**
   * F4：保存成功后按需刷新部分视图数据（周报/画像），
   * 不清空 bundle——整站卸载会丢掉助手会话与今日交互状态。
   * 单项失败保留旧数据（已保存的任务不因此回滚），可下次再取。
   */
  async function refreshPartial(keys: ReadonlyArray<'weekly' | 'profile'>): Promise<void> {
    if (!source || !data.value) return
    await Promise.all(
      keys.map(async key => {
        try {
          const next = key === 'weekly' ? await source.getWeekly() : await source.getProfile()
          if (data.value) data.value = { ...data.value, [key]: next }
        } catch {
          /* 保留旧数据；统计暂未更新不打断用户。 */
        }
      }),
    )
  }

  if (options.autoLoad !== false && !initialData) void load()

  return { status, data, onboarding, error, progress, load, reload, refreshPartial, retry: load }
}
