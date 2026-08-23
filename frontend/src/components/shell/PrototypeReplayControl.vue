<script setup lang="ts">
const emit = defineEmits<{
  replay: []
}>()
</script>

<template>
  <button
    id="protoTag"
    class="proto-tag"
    type="button"
    title="点击重新体验首次引导"
    @click="emit('replay')"
  >
    UI 原型 02 · 春日极光
  </button>
</template>
