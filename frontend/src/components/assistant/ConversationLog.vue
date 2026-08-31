<script setup lang="ts">
import type { AssistantGreeting } from '@/contracts'

defineProps<{
  greeting: AssistantGreeting
}>()
</script>

<template>
  <div class="ask-log" data-testid="conversation-log">
    <div class="card answer-card greeting-card">
      <span class="answer-glow"></span>
      <div class="answer-face"><span class="mini"></span>{{ greeting.face }}</div>
      <div class="answer-text">
        <template v-for="(segment, index) in greeting.segments" :key="index">
          <template v-if="segment.breakBefore">
            <br />
            <br />
          </template>
          <template v-if="segment.emphasis"><b>{{ segment.text }}</b></template>
          <template v-else>{{ segment.text }}</template>
        </template>
      </div>
    </div>
    <slot />
  </div>
</template>
