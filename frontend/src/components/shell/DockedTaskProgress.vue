<script setup lang="ts">
import { computed, onUnmounted, toRef, watch } from 'vue'

import type { ShellTaskProgress } from '@/contracts'
import { useDockedProgress } from '@/composables/useDockedProgress'

/**
 * Sprint 4：吸附顶栏进度（迁移自冻结原型 .topbar，104-126 行）。
 *
 * Sprint 2R 版本同时渲染 hero 进度行 + 顶栏；冻结原型中进度行属于
 * hero 内部（含「开始今日检查」CTA），Sprint 4 起进度行归还
 * TodayHero，本组件收敛为「仅顶栏」，通过 sentinel prop 观察
 * hero 进度行元素（等价于原型的 `.view.active .progress-row` 查询）。
 */

const props = defineProps<{
  progress: ShellTaskProgress
  /** hero 内 .progress-row 元素；滚出视口时顶栏吸附显示 */
  sentinel?: HTMLElement | null
}>()

const sentinelRef = toRef(props, 'sentinel')
const { isDocked } = useDockedProgress(sentinelRef)
const percentage = computed(() => {
  if (props.progress.total <= 0) return 0
  return Math.min(100, Math.max(0, (props.progress.completed / props.progress.total) * 100))
})

watch(
  isDocked,
  value => document.body.classList.toggle('tb-dock', value),
  { immediate: true },
)

onUnmounted(() => document.body.classList.remove('tb-dock'))
</script>

<template>
  <div class="topbar-wrap">
    <div
      id="topbar"
      class="topbar"
      data-testid="docked-progress"
      :aria-hidden="!isDocked"
    >
      <span class="tb-label">✦ 今日微任务</span>
      <span id="tbNum" class="tb-num">{{ progress.completed }} / {{ progress.total }}</span>
      <div class="tb-track">
        <div id="tbFill" class="tb-fill" :style="{ width: `${percentage}%` }"></div>
      </div>
      <span id="tbNote" class="tb-note">{{ progress.note }}</span>
    </div>
  </div>
</template>
