<script setup lang="ts">
defineProps<{
  current: number
  total: number
}>()
</script>

<template>
  <div class="ob-dots" data-testid="onboarding-progress" :aria-label="`第 ${current} 步，共 ${total} 步`">
    <i
      v-for="index in total"
      :key="index"
      :class="{ on: index <= current }"
      aria-hidden="true"
    />
  </div>
</template>
