<script setup lang="ts">
defineProps<{
  loading: boolean
  connected: boolean
}>()

defineEmits<{
  refresh: []
}>()
</script>

<template>
  <section aria-live="polite">
    <h2>服务状态</h2>
    <p v-if="loading">正在连接服务…</p>
    <p v-else-if="connected">服务已连接</p>
    <template v-else>
      <p>暂时无法连接服务</p>
      <button type="button" @click="$emit('refresh')">重新连接</button>
    </template>
  </section>
</template>
