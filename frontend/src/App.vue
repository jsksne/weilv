<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import AppShell from '@/layouts/AppShell.vue'
import TodayView from '@/views/TodayView.vue'
import AssistantView from '@/views/AssistantView.vue'
import ProfileView from '@/views/ProfileView.vue'
import WeeklyView from '@/views/WeeklyView.vue'
import LegacyConsole from '@/views/LegacyConsole.vue'
import { useDailyTasks } from '@/composables/useDailyTasks'
import { hasDemoOnboardingCompleted } from '@/composables/useOnboarding'
import { useUiDataSource } from '@/composables/useUiDataSource'
import { createUiDataSource } from '@/data/createUiDataSource'
import { createProductionShellContract, createUnavailableTodayContract } from '@/data/adapters'
import { getConfiguredRecommendationContext } from '@/config/recommendationContext'
import { getConfiguredUiMode, UiModeConfigurationError } from '@/config/uiMode'
import { getConfiguredUserId, UserContextConfigurationError } from '@/config/userContext'
import OnboardingFlow from '@/components/onboarding/OnboardingFlow.vue'
import type { ShellContract, UiDataSource } from '@/contracts'
import type { TodayTaskAction, TodayTaskView } from '@/contracts'

/**
 * Sprint 9：正式集成入口。
 * Demo → FixtureUiDataSource（fixture only）；Production → ApiUiDataSource（API only）。
 * Production 用户身份来自显式 VITE_USER_ID（可替换 integration seam，非认证系统）。
 * 旧组件/旧 CSS/旧 flow 源码保留，但只在 ?legacy=1 之后（Sprint 10 清理）。
 */

const legacyMode =
  typeof window !== 'undefined' &&
  typeof window.location !== 'undefined' &&
  new URLSearchParams(window.location.search).has('legacy')

const configurationError = ref<Error | null>(null)
let dataSource: UiDataSource | null = null
if (!legacyMode) {
  try {
    const mode = getConfiguredUiMode()
    const options =
      mode === 'production'
        ? { userId: getConfiguredUserId(), recommendationContext: getConfiguredRecommendationContext() }
        : {}
    dataSource = createUiDataSource(mode, options)
  } catch (cause) {
    configurationError.value =
      cause instanceof UiModeConfigurationError || cause instanceof UserContextConfigurationError
        ? cause
        : cause instanceof Error
          ? cause
          : new Error('UI 配置无效。')
  }
}

const ui = useUiDataSource(dataSource, {
  autoLoad: !legacyMode && !configurationError.value,
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

/* 原型 navDate：冻结「4 月 22 日」+ 按当前日期计算星期 */
const frozenDateLabel = (): string => {
  const weekday = ['日', '一', '二', '三', '四', '五', '六'][new Date().getDay()]
  return `4 月 22 日 · 星期${weekday}`
}

const shell = computed<ShellContract>(() => {
  const base = bundle.value?.shell ?? createProductionShellContract()
  return {
    ...base,
    dateLabel: base.state.mode === 'demo' ? frozenDateLabel() : base.dateLabel,
    progress:
      base.state.mode === 'demo'
        ? {
            completed: daily.completed.value,
            total: daily.total.value,
            note: daily.dockedProgressNote.value,
          }
        : base.progress,
  }
})

function openOnboarding(): void {
  onboardingVisible.value = true
}

function closeOnboarding(): void {
  onboardingVisible.value = false
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
  <AppShell v-if="!legacyMode && status === 'ready' && bundle" :shell="shell" @replay="openOnboarding">
    <template #today>
      <TodayView :model="bundle.today" :daily="daily" />
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
  <AppShell v-else-if="legacyMode">
    <LegacyConsole />
  </AppShell>
  <section v-else-if="status === 'loading'" data-testid="ui-data-loading" role="status">
    正在加载微律数据……
  </section>
  <section v-else data-testid="ui-data-error" role="alert">
    <p>{{ errorMessage }}</p>
    <button type="button" @click="retry">重试</button>
  </section>
  <OnboardingFlow
    v-if="onboardingVisible && !legacyMode && onboarding"
    :model="onboarding"
    :submit="dataSource?.submitOnboarding"
    @complete="onOnboardingComplete"
  />
</template>
