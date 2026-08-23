<script setup lang="ts">
import { ref } from 'vue'

import type { TodayContract } from '@/contracts'

/**
 * 冻结原型 #view-today .hero（865-879 行）：极光弧带、hero-tag、
 * 问候、状态说明、进度行（含「开始今日检查」CTA）。
 * 多根片段组件，由父级包进 .hero.stagger。
 * defineExpose(progressRow)：吸附顶栏的观察哨兵（原型
 * `.view.active .progress-row` 查询目标）。
 */

defineProps<{
  model: TodayContract
  completed: number
  total: number
  note: string
}>()

const emit = defineEmits<{
  check: []
}>()

const progressRow = ref<HTMLElement | null>(null)

defineExpose({ progressRow })
</script>

<template>
  <div class="hero-arc" aria-hidden="true"></div>
  <div class="hero-tag">{{ model.heroTag }}</div>
  <h1>{{ model.greetingLead }}<em>{{ model.greetingName }}</em></h1>
  <p>
    <template v-for="(line, lineIndex) in model.summaryLines" :key="lineIndex">
      <template v-if="lineIndex > 0"><br /></template>
      <template v-for="(segment, segmentIndex) in line" :key="segmentIndex">
        <b v-if="segment.emphasis">{{ segment.text }}</b>
        <template v-else>{{ segment.text }}</template>
      </template>
    </template>
  </p>
  <div ref="progressRow" class="progress-row" data-testid="hero-progress">
    <div class="progress-num">{{ completed }}<small>/ {{ total }}</small></div>
    <div class="progress-track">
      <div class="progress-fill" :style="{ width: `${total > 0 ? (completed / total) * 100 : 0}%` }"></div>
    </div>
    <div class="progress-note">{{ note }}</div>
    <div class="progress-cta">
      <button class="btn btn-primary btn-sm" type="button" @click="emit('check')">
        ✦ 开始今日检查
      </button>
      <span class="hero-hint">约 30 秒 · 从此刻的心情开始</span>
    </div>
  </div>
</template>
