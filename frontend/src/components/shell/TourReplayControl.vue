<script setup lang="ts">
const emit = defineEmits<{
  tour: []
}>()
</script>

<template>
  <button
    id="tourTag"
    class="proto-tag proto-tag-tour"
    type="button"
    title="重新查看新手教程"
    @click="emit('tour')"
  >
    新手教程
  </button>
</template>
