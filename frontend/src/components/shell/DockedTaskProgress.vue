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

<style scoped>
.topbar-wrap {
  position: relative;
  z-index: 55;
  max-width: 1080px;
  margin: 0 auto;
  height: 0;
  padding: 0;
}

.progress-row {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 26px;
  flex-wrap: wrap;
}

.progress-num {
  font-family: 'Noto Serif SC', 'Songti SC', 'STSong', 'SimSun', serif;
  font-size: 26px;
  font-weight: 700;
}

.progress-num small {
  font-size: 13px;
  color: #9b8495;
  font-weight: 400;
  margin-left: 6px;
}

.progress-track {
  flex: 1;
  max-width: 380px;
  min-width: 120px;
  height: 6px;
  border-radius: 99px;
  background: rgba(147, 113, 138, 0.12);
  overflow: hidden;
}

.progress-fill,
.tb-fill {
  height: 100%;
  border-radius: 99px;
  background: linear-gradient(90deg, #ffb7c5, #f78fb0 45%, #b9a7ea);
}

.progress-fill {
  box-shadow: 0 0 16px rgba(233, 160, 220, 0.45);
}

.progress-note {
  font-size: 12px;
  color: #9b8495;
}

.topbar {
  position: fixed;
  top: 8px;
  left: 50%;
  transform: translateX(160%);
  width: min(640px, calc(100vw - 28px));
  height: 40px;
  z-index: 60;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 18px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  border: 1px solid rgba(255, 183, 197, 0.4);
  box-shadow: 0 14px 38px rgba(247, 143, 176, 0.28);
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
  transition: transform 0.55s cubic-bezier(0.16, 1, 0.3, 1),
    opacity 0.4s cubic-bezier(0.16, 1, 0.3, 1), visibility 0.55s;
}

.topbar.docked {
  transform: translateX(-50%);
  opacity: 1;
  visibility: visible;
  pointer-events: auto;
}

.tb-label {
  font-size: 12px;
  letter-spacing: 2px;
  color: #7356a5;
  font-weight: 700;
  flex: none;
}

.tb-num {
  font-family: 'Noto Serif SC', 'Songti SC', 'STSong', 'SimSun', serif;
  font-size: 15px;
  font-weight: 600;
  color: #594452;
  flex: none;
}

.tb-track {
  flex: 1;
  height: 8px;
  border-radius: 99px;
  background: #ffe9ef;
  overflow: hidden;
  border: 1px solid rgba(255, 183, 197, 0.4);
}

.tb-fill {
  transition: width 0.9s cubic-bezier(0.16, 1, 0.3, 1);
  box-shadow: 0 0 12px rgba(233, 160, 220, 0.5);
}

.tb-note {
  font-size: 11.5px;
  color: #9b8495;
  flex: none;
  letter-spacing: 1px;
}

@media (max-width: 720px) {
  .tb-note {
    display: none;
  }
}
</style>
