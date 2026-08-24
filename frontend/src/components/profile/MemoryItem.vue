<script setup lang="ts">
import type { MemoryItemContract } from '@/contracts'

defineProps<{
  model: MemoryItemContract
  removing?: boolean
  canDelete?: boolean
}>()

const emit = defineEmits<{
  remove: [id: string]
}>()
</script>

<template>
  <div class="mem-item" :class="{ removing }" :data-memory-id="model.id">
    <span class="mi-ic">
      <svg class="ic" aria-hidden="true"><use :href="`#i-${model.icon}`" /></svg>
    </span>
    <p><b>{{ model.lead }}</b>{{ model.text }}</p>
    <button
      class="mem-del"
      type="button"
      aria-label="删除这条记忆"
      :disabled="!canDelete || removing"
      @click="emit('remove', model.id)"
    >
      ×
    </button>
  </div>
</template>
