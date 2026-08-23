<script setup lang="ts">
import type { AssistantSource } from '@/contracts'

defineProps<{
  sources: readonly AssistantSource[]
}>()
</script>

<template>
  <div v-if="sources.length" class="cites" data-testid="evidence-list">
    <div class="ct">依据来源</div>
    <a
      v-for="source in sources"
      :key="`${source.label}-${source.url ?? ''}`"
      class="cite"
      :href="source.url"
      :target="source.url ? '_blank' : undefined"
      :rel="source.url ? 'noreferrer' : undefined"
    >
      {{ source.label }}
    </a>
  </div>
</template>
