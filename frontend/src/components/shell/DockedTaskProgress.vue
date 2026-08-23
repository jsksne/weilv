<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'

import type { ShellTaskProgress } from '@/contracts'
import { useDockedProgress } from '@/composables/useDockedProgress'

const props = defineProps<{
  progress: ShellTaskProgress
}>()

const progressRow = ref<HTMLElement | null>(null)
const { isDocked } = useDockedProgress(progressRow)
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
  <div ref="progressRow" class="progress-row" data-testid="progress-row">
    <div id="progNum" class="progress-num">
      {{ progress.completed }}<small>/ {{ progress.total }}</small>
    </div>
    <div class="progress-track">
      <div id="progFill" class="progress-fill" :style="{ width: `${percentage}%` }"></div>
    </div>
    <div id="progNote" class="progress-note">{{ progress.note }}</div>
  </div>
  <div class="topbar-wrap">
    <div
      id="topbar"
      class="topbar"
      :class="{ docked: isDocked }"
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
