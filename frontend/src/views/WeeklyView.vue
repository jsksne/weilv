<script setup lang="ts">
import { computed } from 'vue'

import AdjustmentTimeline from '@/components/weekly/AdjustmentTimeline.vue'
import WeeklyHeader from '@/components/weekly/WeeklyHeader.vue'
import WeeklyInsightCard from '@/components/weekly/WeeklyInsightCard.vue'
import WeeklyMinutesChart from '@/components/weekly/WeeklyMinutesChart.vue'
import type { WeeklyContract } from '@/contracts'

const props = defineProps<{
  model: WeeklyContract
}>()

const unavailable = computed(
  () => props.model.state.status === 'unavailable' || props.model.dataAvailability === 'unavailable',
)
</script>

<template>
  <div class="week-wrap" data-testid="weekly-view">
    <WeeklyHeader :model="model.header" />

    <div v-if="unavailable" class="card weekly-status-card" data-testid="weekly-unavailable">
      <strong>周度变化暂不可用</strong>
      <span>{{ model.state.message || 'Production Weekly 数据暂不可用。' }}</span>
    </div>

    <div v-else class="stagger">
      <WeeklyMinutesChart :model="model" />
      <div class="week-grid">
        <AdjustmentTimeline :title="model.timelineTitle" :items="model.timeline" />
        <WeeklyInsightCard :model="model.insight" />
      </div>
    </div>
  </div>
</template>
