<script setup lang="ts">
import type { AssistantQuickPrompt } from '@/contracts'

defineProps<{
  prompts: readonly AssistantQuickPrompt[]
  busy: boolean
}>()

const emit = defineEmits<{
  select: [prompt: AssistantQuickPrompt]
}>()
</script>

<template>
  <div class="quick-row" data-testid="quick-prompts">
    <button
      v-for="prompt in prompts"
      :key="prompt.id"
      class="chip"
      type="button"
      :data-prompt="prompt.id"
      :disabled="busy"
      @click="emit('select', prompt)"
    >
      {{ prompt.label }}
    </button>
  </div>
</template>
