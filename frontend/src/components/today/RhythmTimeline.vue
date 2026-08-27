<script setup lang="ts">
import type { TodayContract } from '@/contracts'

/**
 * 冻结原型 .card.rhythm-card（978-984 行）：今日节奏时间轴。
 */
defineProps<{
  rhythm: TodayContract['rhythm']
}>()
</script>

<template>
  <div class="card rhythm-card">
    <h3>{{ rhythm.title }}</h3>
    <div class="sub">{{ rhythm.sub }}</div>
    <div
      v-for="(item, index) in rhythm.items"
      :key="index"
      class="rhythm-item"
      :class="{ now: item.now }"
    >
      <span class="rhythm-time">{{ item.time }}</span>
      <span class="rhythm-dot"></span>
      <div class="rhythm-txt"><b>{{ item.title }}</b>{{ item.note }}</div>
    </div>
    <p v-if="!rhythm.items.length" class="obs-sub" data-testid="rhythm-empty">
      暂未形成可展示的今日节奏。
    </p>
  </div>
</template>
