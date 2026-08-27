<script setup lang="ts">
import type { AssistantKnowledgeChunk } from '@/contracts'

defineProps<{
  chunk: AssistantKnowledgeChunk
}>()
</script>

<template>
  <div class="chunk">
    <span class="chunk-badge">{{ chunk.source }}</span>
    <p>{{ chunk.text ?? '已检索到该来源。' }}</p>
    <div v-if="chunk.relevance !== null" class="rel">
      <div class="rel-bar"><i :style="{ width: `${chunk.relevance * 100}%` }"></i></div>
      <span class="rel-val">相关度 {{ chunk.relevance.toFixed(2) }}</span>
    </div>
  </div>
</template>
