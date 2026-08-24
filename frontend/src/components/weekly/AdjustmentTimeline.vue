<script setup lang="ts">
import type { WeeklyTimelineItem } from '@/contracts'

defineProps<{
  title: string
  items: readonly WeeklyTimelineItem[]
}>()
</script>

<template>
  <div class="card tl-card" data-testid="weekly-timeline">
    <h3>{{ title }}</h3>
    <div
      v-for="item in items"
      :key="item.id"
      class="tl-item"
      :class="{ hit: item.status === 'completed', adj: item.status === 'adjusted' }"
      :data-status="item.status"
    >
      <span class="tl-day">{{ item.time }}</span>
      <span class="tl-dot"></span>
      <div class="tl-body">
        <strong>{{ item.action }}</strong><span class="tl-tag" :class="item.status === 'completed' ? 'g' : item.status === 'adjusted' ? 'm' : 'n'">{{ item.tag }}</span><br />
        {{ item.description }}
      </div>
    </div>
    <p v-if="!items.length" class="weekly-empty" data-testid="weekly-timeline-empty">
      暂无调整轨迹
    </p>
  </div>
</template>
