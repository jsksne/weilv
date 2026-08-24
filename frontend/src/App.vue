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
import OnboardingFlow from '@/components/onboarding/OnboardingFlow.vue'
import type { ShellContract, UiDataSource } from '@/contracts'

/**
 * Sprint 4：产品运行态切换为 Shell + TodayView（fixture-driven Demo，
 * 不请求 API）。真实 Shell 导航（导航胶囊 / glider / 日期 / avatar）
 * 首次在实际产品运行态可见。
 *
 * legacy 表单流保留在 ?legacy=1 查询参数之后（可回滚 backup，
 * 既有 flow 测试经该入口继续覆盖；Sprint 9 移除）。
 */

const legacyMode =
  typeof window !== 'undefined' &&
  typeof window.location !== 'undefined' &&
  new URLSearchParams(window.location.search).has('legacy')

const configurationError = ref<Error | null>(null)
let dataSource: UiDataSource | null = null
if (!legacyMode) {
  try {
    dataSource = createUiDataSource()
  } catch (cause) {
    configurationError.value = cause instanceof Error ? cause : new Error('UI mode 配置无效。')
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
/* 今日交互状态唯一实例：hero 进度行与吸附顶栏都从 DataSource Contract 取数 */
const daily = useDailyTasks(today)
const onboardingVisible = ref(false)
const onboarding = computed(() => bundle.value?.onboarding ?? null)

watch(
  [() => ui.status.value, onboarding],
  ([status, model]) => {
    if (
      status === 'ready' &&
      model?.state.mode === 'demo' &&
      !hasDemoOnboardingCompleted(model.storageKey)
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
      <ProfileView :model="bundle.profile" />
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
    @complete="closeOnboarding"
  />
</template>
