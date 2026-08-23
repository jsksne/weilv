<script setup lang="ts">
import type { FeedbackResponse } from '@/api/types'

defineProps<{
  result: FeedbackResponse
}>()
</script>

<template>
  <section aria-live="polite">
    <h3>反馈结果</h3>
    <p>已记录这次反馈。</p>
    <p v-if="result.memory_persisted">
      微律会在之后的类似情况中参考这次反馈。
    </p>
  </section>
</template>
