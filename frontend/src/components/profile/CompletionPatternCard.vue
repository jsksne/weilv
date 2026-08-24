<script setup lang="ts">
import type { CompletionPatternContract } from '@/contracts'

import CompletionRing from './CompletionRing.vue'

const props = defineProps<{
  model: CompletionPatternContract
  replayKey?: number
}>()
</script>

<template>
  <div class="card p-card" data-profile-section="completion">
    <h3>
      <svg class="ic" aria-hidden="true"><use :href="`#i-${model.icon}`" /></svg>
      {{ model.title }}
    </h3>
    <div v-if="model.status === 'available' && model.percentage !== null" class="stat-ring">
      <CompletionRing :percentage="model.percentage" :replay-key="props.replayKey" />
      <div class="stat-txt">
        <template v-for="(line, index) in model.summaryLines" :key="line">
          <template v-if="index === 0"><b>3 分钟以内</b>的小任务完成率最高。</template>
          <template v-else>{{ line }}</template>
          <br v-if="index < model.summaryLines.length - 1" />
        </template>
      </div>
    </div>
    <p v-else class="consent" data-testid="completion-unavailable">
      {{ model.unavailableMessage }}
    </p>
  </div>
</template>
