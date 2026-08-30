<script setup lang="ts">
import { computed } from 'vue'

import type { AssistantSource } from '@/contracts'

const props = defineProps<{
  sources: readonly AssistantSource[]
}>()

const uniqueSources = computed(() => {
  const seen = new Set<string>()
  return props.sources.filter(source => {
    const identity = source.url ?? source.label
    if (seen.has(identity)) return false
    seen.add(identity)
    return true
  })
})
</script>

<template>
  <details v-if="uniqueSources.length" class="cites" data-testid="evidence-list">
    <summary class="ct">依据来源 · {{ uniqueSources.length }} 条</summary>
    <div class="cites-body">
      <a
        v-for="source in uniqueSources"
        :key="source.url ?? source.label"
        class="cite"
        :href="source.url"
        :target="source.url ? '_blank' : undefined"
        :rel="source.url ? 'noreferrer' : undefined"
      >
        {{ source.label }}
      </a>
    </div>
  </details>
</template>
