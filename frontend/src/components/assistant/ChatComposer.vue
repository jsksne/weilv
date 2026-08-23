<script setup lang="ts">
import { ref } from 'vue'

defineProps<{
  busy: boolean
}>()

const emit = defineEmits<{
  submit: [question: string]
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
      autocomplete="off"
      :disabled="busy"
    />
    <button class="btn-send" data-testid="chat-submit" type="submit" :disabled="busy">
      问问薇薇
    </button>
  </form>
</template>
