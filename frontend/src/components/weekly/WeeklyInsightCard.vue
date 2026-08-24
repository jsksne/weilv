<script setup lang="ts">
import type { WeeklyInsight } from '@/contracts'

defineProps<{
  model: WeeklyInsight
}>()
</script>

<template>
  <div class="card insight-card" data-testid="weekly-insight">
    <h3>
      <svg class="ic" aria-hidden="true"><use href="#i-flower" /></svg>
      {{ model.title }}
    </h3>
    <p>
      <template v-for="(segment, index) in model.segments" :key="`${segment.text}-${index}`">
        <b v-if="segment.emphasis">{{ segment.text }}</b>
        <template v-else>{{ segment.text }}</template>
      </template>
    </p>
    <div v-if="model.quote" class="insight-quote">{{ model.quote }}</div>
  </div>
</template>
