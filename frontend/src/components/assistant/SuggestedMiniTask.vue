<script setup lang="ts">
import type { AssistantSuggestedTask } from '@/contracts'

defineProps<{
  task: AssistantSuggestedTask
}>()
</script>

<template>
  <div class="mini-task" data-testid="suggested-mini-task">
    <div class="mt-icon">{{ task.icon }}</div>
    <div>
      <b>{{ task.title }}</b>
      <span>{{ task.meta }}</span>
    </div>
    <button class="go" type="button" disabled :aria-label="`${task.actionLabel}（仅展示）`">
      {{ task.actionLabel }}
    </button>
  </div>
</template>
