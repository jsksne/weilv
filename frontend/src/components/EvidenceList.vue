<script setup lang="ts">
import type { EvidenceSource } from '@/api/types'

defineProps<{
  sources: EvidenceSource[]
}>()
</script>

<template>
  <ul>
    <li v-for="source in sources" :key="source.chunk_id">
      <p>{{ source.document_id }}</p>
      <p>{{ source.source_locator }}</p>
      <a
        v-if="source.source_url"
        :href="source.source_url"
        target="_blank"
        rel="noopener noreferrer"
      >查看来源</a>
    </li>
  </ul>
</template>
