<script setup lang="ts">
import { computed } from 'vue'

import type { RecommendationResponse } from '@/api/types'

const props = defineProps<{
  result: RecommendationResponse
}>()

defineEmits<{
  reset: []
}>()

const defaultMessages = {
  help_seeking: '现在更适合先告诉家长、老师或寻求进一步帮助，而不是继续依赖普通微任务。',
  blocked: '当前条件下暂不提供普通微任务。',
  no_safe_task: '当前暂时没有足够合适的微任务，可以稍后根据新的状态再试一次。',
}

const message = computed(() => {
  if (props.result.explanation) return props.result.explanation
  if (props.result.status === 'allowed') return ''
  return defaultMessages[props.result.status]
})
</script>

<template>
  <section aria-live="polite">
    <h2>本次结果</h2>
    <p>{{ message }}</p>
    <button type="button" @click="$emit('reset')">重新填写状态</button>
  </section>
</template>
