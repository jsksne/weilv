<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import AppShell from '@/layouts/AppShell.vue'
import TodayView from '@/views/TodayView.vue'
import AssistantView from '@/views/AssistantView.vue'
import ProfileView from '@/views/ProfileView.vue'
import WeeklyView from '@/views/WeeklyView.vue'
import { useDailyTasks } from '@/composables/useDailyTasks'
import { hasDemoOnboardingCompleted } from '@/composables/useOnboarding'
import { useUiDataSource } from '@/composables/useUiDataSource'
import { createUiDataSource } from '@/data/createUiDataSource'
import { createProductionShellContract, createUnavailableTodayContract } from '@/data/adapters'
import { getConfiguredApiBaseUrl } from '@/config/apiBaseUrl'
import { getConfiguredRecommendationContext } from '@/config/recommendationContext'
import { getConfiguredUiMode, UiModeConfigurationError } from '@/config/uiMode'
import { getConfiguredUserId, UserContextConfigurationError } from '@/config/userContext'
import OnboardingFlow from '@/components/onboarding/OnboardingFlow.vue'
import type { ShellContract, TodayContextSelection, UiDataSource } from '@/contracts'
import type {
  OnboardingSubmitAnswers,
  OnboardingSubmitResult,
  TodayTaskAction,
  TodayTaskView,
} from '@/contracts'

/**
 * Sprint 9.1：正式集成入口，唯一的应用运行路径。
 * Demo → FixtureUiDataSource（fixture only）；Production → ApiUiDataSource（API only）。
 * Production 用户身份来自显式 VITE_USER_ID（可替换 integration seam，非认证系统）。
 * 旧组件/旧 CSS/旧 flow 源码保留在仓库，但不再挂载、不再作为 alternate runtime。
 */

const configurationError = ref<Error | null>(null)
let dataSource: UiDataSource | null = null
try {
  const mode = getConfiguredUiMode()
  const options =
    mode === 'production'
      ? {
          userId: getConfiguredUserId(),
          recommendationContext: getConfiguredRecommendationContext(),
        }
      : {}
  if (mode === 'production') getConfiguredApiBaseUrl()
  dataSource = createUiDataSource(mode, options)
} catch (cause) {
  configurationError.value =
    cause instanceof UiModeConfigurationError || cause instanceof UserContextConfigurationError
      ? cause
      : cause instanceof Error
        ? cause
        : new Error('UI 配置无效。')
}

const ui = useUiDataSource(dataSource, {
  autoLoad: !configurationError.value,
})
if (configurationError.value) {
  ui.status.value = 'error'
  ui.error.value = configurationError.value
}
const { status, retry } = ui
const errorMessage = computed(() => ui.error.value?.message ?? 'UI 数据配置或加载失败。')

const bundle = computed(() => ui.data.value)
const today = computed(() => bundle.value?.today ?? createUnavailableTodayContract('UI 数据加载中。'))

/** Sprint 9：Production 任务动作 → B2 事件（用该任务自己的 recommendation_id）。 */
function onTaskAction(task: TodayTaskView, action: TodayTaskAction): void {
  if (!task.recommendationId) return
  if (dataSource?.submitTaskAction) void dataSource.submitTaskAction(task.recommendationId, action)
}

function onTodayContextChange(context: TodayContextSelection): void {
  dataSource?.setTodayContext?.(context)
}

/* 今日交互状态唯一实例：hero 进度行与吸附顶栏都从 DataSource Contract 取数 */
const daily = useDailyTasks(today, { onAction: onTaskAction })
const onboardingVisible = ref(false)
const onboarding = computed(() => bundle.value?.onboarding ?? null)
const productionNewUser = computed(
  () =>
    bundle.value?.profile.state.mode === 'production' &&
    bundle.value.profile.state.status === 'unavailable' &&
    bundle.value.profile.targetStage === 'unavailable',
)

watch(
  [() => ui.status.value, onboarding, productionNewUser],
  ([status, model, newUser]) => {
    if (status !== 'ready' || !model) return
    const isDemo = model.state.mode === 'demo'
    if (
      (isDemo && !hasDemoOnboardingCompleted(model.storageKey)) ||
      (!isDemo && newUser)
    ) {
      onboardingVisible.value = true
    }
  },
  { immediate: true },
)

/* Demo 保留冻结日期；Production 使用当前真实日期。 */
const frozenDateLabel = (): string => {
  const weekday = ['日', '一', '二', '三', '四', '五', '六'][new Date().getDay()]
  return `4 月 22 日 · 星期${weekday}`
}

const currentDateLabel = (): string => {
  const now = new Date()
  const weekday = ['日', '一', '二', '三', '四', '五', '六'][now.getDay()]
  return `${now.getMonth() + 1} 月 ${now.getDate()} 日 · 星期${weekday}`
}

const shell = computed<ShellContract>(() => {
  const base = bundle.value?.shell ?? createProductionShellContract()
  return {
    ...base,
    dateLabel: base.state.mode === 'demo' ? frozenDateLabel() : currentDateLabel(),
    progress: {
      completed: daily.completed.value,
      total: daily.total.value,
      note: daily.dockedProgressNote.value,
    },
  }
})

function openOnboarding(): void {
  onboardingVisible.value = true
}

function closeOnboarding(): void {
  onboardingVisible.value = false
}

/** 绑定 DataSource 方法到实例（避免解引用后 this 丢失）。 */
function submitOnboarding(
  answers: OnboardingSubmitAnswers,
): Promise<OnboardingSubmitResult> {
  return (
    dataSource?.submitOnboarding?.(answers) ??
    Promise.resolve({ status: 'error', message: '缺少 DataSource，无法保存引导结果。', persistence: [] })
  )
}

/**
 * Production 引导完成：重新加载 bundle（真实 Profile 已写入），
 * 由真实 Profile 状态驱动进入 Today。失败/跳过不假装完成。
 */
function onOnboardingComplete(): void {
  closeOnboarding()
  if (bundle.value?.onboarding.state.mode === 'production') void ui.load()
}

async function refreshProfile(): Promise<void> {
  if (dataSource && bundle.value?.profile.state.mode === 'production') await ui.load()
}
</script>

<template>
  <AppShell v-if="status === 'ready' && bundle" :shell="shell" @replay="openOnboarding">
    <template #today>
      <TodayView :model="bundle.today" :daily="daily" @context-change="onTodayContextChange" />
    </template>
    <template #assistant>
      <AssistantView :model="bundle.assistant" :data-source="dataSource ?? undefined" />
    </template>
    <template #profile>
      <ProfileView
        :model="bundle.profile"
        :data-source="dataSource ?? undefined"
        :on-refresh="refreshProfile"
      />
    </template>
    <template #weekly>
      <WeeklyView :model="bundle.weekly" />
    </template>
  </AppShell>
  <section v-else-if="status === 'loading'" data-testid="ui-data-loading" role="status">
    正在加载微律数据……
  </section>
  <section v-else data-testid="ui-data-error" role="alert">
    <p>{{ errorMessage }}</p>
    <button type="button" @click="retry">重试</button>
  </section>
  <OnboardingFlow
    v-if="onboardingVisible && onboarding"
    :model="onboarding"
    :submit="submitOnboarding"
    @complete="onOnboardingComplete"
  />
</template>
