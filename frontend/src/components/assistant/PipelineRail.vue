<script setup lang="ts">
import type { AssistantPipeline, AssistantStageBase } from '@/contracts'

defineProps<{
  stages: readonly [AssistantPipeline['analysis'], AssistantPipeline['retrieval'], AssistantPipeline['answer']]
}>()

function nodeNumber(stage: AssistantStageBase): string {
  return stage.id === 'analysis' ? '1' : stage.id === 'retrieval' ? '2' : '3'
}
</script>

<template>
  <div class="pipe-rail" data-testid="pipeline-rail">
    <template v-for="(stage, index) in stages" :key="stage.id">
      <div class="pnode" :class="stage.status" :data-stage="stage.id">
        <i class="pno">{{ nodeNumber(stage) }}</i>
        <span>{{ stage.title }}</span>
      </div>
      <div v-if="index < stages.length - 1" class="pline" :class="{ fill: stage.status === 'done' }"></div>
    </template>
  </div>
</template>
