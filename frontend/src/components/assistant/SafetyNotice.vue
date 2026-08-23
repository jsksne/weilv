<script setup lang="ts">
import type { AssistantSafetyNotice as SafetyNoticeModel } from '@/contracts'

defineProps<{
  notice: SafetyNoticeModel
}>()
</script>

<template>
  <div class="safety-card" data-testid="safety-notice">
    <div class="st">{{ notice.title }}</div>
    <p v-for="(paragraph, index) in notice.paragraphs" :key="index">{{ paragraph }}</p>
    <div class="rule">{{ notice.rule }}</div>
  </div>
</template>
