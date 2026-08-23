<script setup lang="ts">
import { onMounted } from 'vue'

import type { TodayContract } from '@/contracts'
import { useBreathCycle } from '@/composables/useBreathCycle'

/**
 * 冻结原型 .card.breath-card（968-977 行）：呼吸核心/光环由 today.css
 * 的 9s breathCycle CSS 动画驱动；文字节奏（label/count）来自
 * useBreathCycle，与 CSS 动画同频。挂载即启动，卸载自动清理。
 */
defineProps<{
  breath: TodayContract['breath']
}>()

const { label, count, start } = useBreathCycle()

onMounted(start)
</script>

<template>
  <div class="card breath-card">
    <h3>{{ breath.title }}</h3>
    <div class="sub">{{ breath.sub }}</div>
    <div class="breath-stage">
      <div class="breath-halo"></div>
      <div class="breath-halo h2"></div>
      <div class="breath-halo h3"></div>
      <div class="breath-core">
        <div class="breath-count">{{ count }}</div>
      </div>
      <div class="breath-label">{{ label }}</div>
    </div>
    <p class="breath-tip">
      {{ breath.tip }}<br />页面上所有动效，都遵循这同一条曲线。
    </p>
  </div>
</template>
