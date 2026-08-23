<script setup lang="ts">
import { computed } from 'vue'

import AppShell from '@/layouts/AppShell.vue'
import TodayView from '@/views/TodayView.vue'
import LegacyConsole from '@/views/LegacyConsole.vue'
import { shellFixture } from '@/data/fixtures/shell.fixture'
import { todayFixture } from '@/data/fixtures/today.fixture'
import { useDailyTasks } from '@/composables/useDailyTasks'
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

/* 未迁移页面：最小 placeholder/unavailable 结构态，不填业务数据 */
const pendingViews = [
  { id: 'assistant', label: '问问薇薇' },
  { id: 'profile', label: '我的画像' },
  { id: 'weekly', label: '周度变化' },
] as const
</script>

<template>
  <AppShell v-if="!legacyMode" :shell="shell">
    <template #today>
      <TodayView :model="todayFixture" :daily="daily" />
    </template>
    <template v-for="view in pendingViews" :key="view.id" #[view.id]>
      <div class="card" :data-view-pending="view.id" style="padding: 26px 30px; margin-top: 26px">
        <h3 style="font-family: var(--disp); font-weight: 600; letter-spacing: 1px">
          {{ view.label }}
        </h3>
        <p style="margin-top: 10px; font-size: 13px; color: var(--ink-2)">
          该页面尚未迁移（后续 Sprint），此处为结构性占位，无演示数据。
        </p>
      </div>
    </template>
  </AppShell>
  <AppShell v-else>
    <LegacyConsole />
  </AppShell>
</template>
