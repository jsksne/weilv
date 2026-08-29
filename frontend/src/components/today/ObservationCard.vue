<script setup lang="ts">
import { computed } from 'vue'
import type { TodayObservationView } from '@/contracts'

/**
 * 冻结原型 .card.observe-card（881-895 行）：微律观察、状态总结、
 * 三个观察指标与两条今日建议（线性图标 sprite）。
 */
const props = defineProps<{
  observation: TodayObservationView
}>()

const hasObservationData = computed(
  () => props.observation.stats.length > 0 || props.observation.suggestions.length > 0,
)
</script>

<template>
  <div class="obs-head">
    <h3>微律观察</h3>
    <span class="live"><i></i>{{ hasObservationData ? '每天 8:00 更新' : '等待真实数据' }}</span>
  </div>
  <p class="obs-main">
    {{ observation.mainLead }}<em>{{ observation.mainEmphasis }}</em>{{ observation.mainTail }}
  </p>
  <p class="obs-sub">{{ observation.summary }}</p>
  <div class="obs-stats">
    <div v-for="stat in observation.stats" :key="stat.key" class="ob-stat">
      <span class="os-k">{{ stat.key }}</span>
      <b>{{ stat.value }}</b>
      <span class="os-delta" :class="stat.deltaTone">{{ stat.delta }}</span>
    </div>
  </div>
  <div class="sug-row">
    <div class="sug-title">今日建议</div>
    <div v-for="(suggestion, index) in observation.suggestions" :key="index" class="sug-item">
      <span class="sg-ic" :class="{ night: suggestion.night }">
        <svg class="ic"><use :href="`#${suggestion.icon}`" /></svg>
      </span>
      <p><b>{{ suggestion.lead }}</b>{{ suggestion.rest }}</p>
    </div>
    <div v-if="!observation.suggestions.length" class="sug-item" data-testid="observation-empty">
      <p>有足够的真实状态信息后，这里会出现对应建议；微律不会替你猜。</p>
    </div>
  </div>
</template>
