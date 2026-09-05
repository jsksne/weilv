<script setup lang="ts">
import { computed } from 'vue'

import type { AssistantSuggestedTask, SuggestedTaskState } from '@/contracts'

const props = defineProps<{
  task: AssistantSuggestedTask
  /** F2：今日真实状态（absent=可加入；pending=去开始；started=继续；done=已完成）。 */
  state?: SuggestedTaskState
}>()

const emit = defineEmits<{
  activate: [task: AssistantSuggestedTask]
}>()

const buttonLabel = computed(() => {
  if (props.state === 'done') return '今天已完成'
  if (props.state === 'started') return '继续'
  if (props.state === 'pending') return '开始这件事'
  return '加入今日'
})

const buttonDisabled = computed(() => props.state === 'done')
</script>

<template>
  <div class="mini-task" data-testid="suggested-mini-task">
    <div class="mt-icon">{{ task.icon }}</div>
    <div>
      <b>{{ task.title }}</b>
      <span>{{ task.meta }}</span>
    </div>
    <button
      class="go"
      type="button"
      :disabled="buttonDisabled"
      :aria-label="`${buttonLabel}：${task.title}`"
      @click="emit('activate', task)"
    >
      {{ buttonLabel }}
    </button>
  </div>
</template>
