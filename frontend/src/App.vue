<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import AppShell from '@/layouts/AppShell.vue'
import TodayView from '@/views/TodayView.vue'
import AssistantView from '@/views/AssistantView.vue'
import ProfileView from '@/views/ProfileView.vue'
import WeeklyView from '@/views/WeeklyView.vue'
import LegacyConsole from '@/views/LegacyConsole.vue'
import { shellFixture } from '@/data/fixtures/shell.fixture'
import { todayFixture } from '@/data/fixtures/today.fixture'
import { assistantFixture } from '@/data/fixtures/assistant.fixture'
import { onboardingFixture } from '@/data/fixtures/onboarding.fixture'
import { profileFixture } from '@/data/fixtures/profile.fixture'
import { weeklyFixture } from '@/data/fixtures/weekly.fixture'
import { useDailyTasks } from '@/composables/useDailyTasks'
import { hasDemoOnboardingCompleted } from '@/composables/useOnboarding'
import OnboardingFlow from '@/components/onboarding/OnboardingFlow.vue'
import type { ShellContract } from '@/contracts'

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

/* 今日交互状态唯一实例：hero 进度行与吸附顶栏都从这里取数 */
const daily = useDailyTasks(todayFixture)
const onboardingVisible = ref(false)

onMounted(() => {
  if (!legacyMode && !hasDemoOnboardingCompleted(onboardingFixture.storageKey)) {
    onboardingVisible.value = true
  }
})

/* 原型 navDate：冻结「4 月 22 日」+ 按当前日期计算星期 */
const frozenDateLabel = (): string => {
  const weekday = ['日', '一', '二', '三', '四', '五', '六'][new Date().getDay()]
  return `4 月 22 日 · 星期${weekday}`
}

const shell = computed<ShellContract>(() => ({
  state: shellFixture.state,
  navigation: shellFixture.navigation,
  displayName: shellFixture.displayName,
  dateLabel: frozenDateLabel(),
  progress: {
    completed: daily.completed.value,
    total: daily.total.value,
    note: daily.dockedProgressNote.value,
  },
  toastExample: shellFixture.toastExample,
}))

function openOnboarding(): void {
  onboardingVisible.value = true
}

function closeOnboarding(): void {
  onboardingVisible.value = false
}
</script>

<template>
  <AppShell v-if="!legacyMode" :shell="shell" @replay="openOnboarding">
    <template #today>
      <TodayView :model="todayFixture" :daily="daily" />
    </template>
    <template #assistant>
      <AssistantView :model="assistantFixture" />
    </template>
    <template #profile>
      <ProfileView :model="profileFixture" />
    </template>
    <template #weekly>
      <WeeklyView :model="weeklyFixture" />
    </template>
  </AppShell>
  <AppShell v-else>
    <LegacyConsole />
  </AppShell>
  <OnboardingFlow
    v-if="onboardingVisible && !legacyMode"
    :model="onboardingFixture"
    @complete="closeOnboarding"
  />
</template>
