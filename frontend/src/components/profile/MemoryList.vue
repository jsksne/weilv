<script setup lang="ts">
import type { MemoryItemContract } from '@/contracts'

import MemoryItem from './MemoryItem.vue'

defineProps<{
  items: readonly MemoryItemContract[]
  canDelete: boolean
  removingIds?: ReadonlySet<string>
}>()

const emit = defineEmits<{
  remove: [id: string]
}>()
</script>

<template>
  <div class="mem-list" data-testid="memory-list">
    <MemoryItem
      v-for="item in items"
      :key="item.id"
      :model="item"
      :can-delete="canDelete"
      :removing="removingIds?.has(item.id)"
      @remove="emit('remove', $event)"
    />
    <p v-if="items.length === 0" class="consent" data-testid="memory-empty">暂时还没有可展示的记忆。</p>
  </div>
</template>
