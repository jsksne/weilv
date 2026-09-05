<script setup lang="ts">
import { ref } from 'vue'

defineProps<{
  busy: boolean
  easyStart?: boolean
}>()

const emit = defineEmits<{
  submit: [question: string]
  'toggle-easy-start': [value: boolean]
}>()

const text = ref('')

function submit(): void {
  const question = text.value.trim()
  if (!question) return
  emit('submit', question)
  text.value = ''
}
</script>

<template>
  <form class="card ask-input" data-testid="chat-composer" @submit.prevent="submit">
    <span class="ai-dot" aria-hidden="true"></span>
    <input
      v-model="text"
      data-testid="chat-input"
      type="text"
      placeholder="说说你现在的状态…"
      aria-label="说说你现在的状态"
      autocomplete="off"
    />
    <button class="btn-send" data-testid="chat-submit" type="submit" :disabled="busy">
      问问薇薇
    </button>
    <button
      class="easy-toggle"
      type="button"
      data-testid="easy-start-toggle"
      :aria-pressed="easyStart ? 'true' : 'false'"
      :disabled="busy"
      title="开启后，回答会在安全候选里优先容易开始的小事"
      @click="emit('toggle-easy-start', !easyStart)"
    >
      🌿 轻一点
    </button>
  </form>
</template>

<style scoped>
.easy-toggle {
  border: 1px solid rgba(247, 143, 176, 0.42);
  border-radius: 999px;
  background: rgba(255, 250, 252, 0.9);
  font: inherit;
  font-size: 12px;
  padding: 0 12px;
  min-height: 34px;
  cursor: pointer;
  color: var(--ink-1, #3f3348);
}

.easy-toggle[aria-pressed='true'] {
  background: rgba(247, 143, 176, 0.18);
  border-color: rgba(247, 143, 176, 0.7);
}
</style>
