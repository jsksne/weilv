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

<style scoped>
.proto-tag {
  position: fixed;
  left: 18px;
  bottom: 18px;
  z-index: 80;
  font-size: 11px;
  letter-spacing: 2px;
  color: #9b8495;
  padding: 7px 14px;
  border-radius: 999px;
  border: 1.5px dashed rgba(255, 183, 197, 0.7);
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(8px);
  user-select: none;
  cursor: pointer;
  transition: color 0.4s, border-color 0.4s;
}

.proto-tag:hover {
  color: #f27ba4;
  border-color: #f27ba4;
}
</style>
