<script setup lang="ts">
import type { AssistantStageBase } from '@/contracts'

defineProps<{
  stage: AssistantStageBase
}>()
</script>

<template>
  <article class="card stage-card" :data-stage-card="stage.id">
    <div class="stage-head">
      <span class="stage-no">{{ stage.id === 'analysis' ? '1' : stage.id === 'retrieval' ? '2' : '3' }}</span>
      <h4>{{ stage.title }}</h4>
      <span class="stage-state">{{ stage.statusLabel }}</span>
    </div>
    <div class="stage-body">
      <slot />
    </div>
  </article>
</template>
