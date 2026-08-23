<script setup lang="ts">
defineProps<{
  text: string
}>()
</script>

<template>
  <div class="q-bubble" data-testid="user-message">{{ text }}</div>
</template>
