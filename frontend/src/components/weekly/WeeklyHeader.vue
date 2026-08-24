<script setup lang="ts">
import type { WeeklyHeader as WeeklyHeaderModel } from '@/contracts'

defineProps<{
  model: WeeklyHeaderModel
}>()
</script>

<template>
  <div class="week-head" data-testid="weekly-header">
    <h2>{{ model.title }}</h2>
    <p>{{ model.description }}</p>
  </div>
</template>
