<script setup lang="ts">
import PipelineStage from './PipelineStage.vue'
import type { AssistantAnalysisStage } from '@/contracts'

defineProps<{
  stage: AssistantAnalysisStage
}>()
</script>

<template>
  <PipelineStage :stage="stage">
    <p v-if="stage.status === 'unavailable'" class="stage-lead">
      后端没有提供实时问题拆解轨迹。
    </p>
    <span v-else-if="stage.status === 'active'" class="typing" aria-label="正在拆解">
      <i></i><i></i><i></i>
    </span>
    <template v-else>
      <p class="stage-lead">{{ stage.lead }}</p>
      <div class="dirs">
        <div v-for="(item, index) in stage.items" :key="item.id" class="dir-row">
          <span class="dir-no">Q{{ index + 1 }}</span>
          <div>
            <b>{{ item.title }}</b>
            <span>{{ item.direction }}</span>
          </div>
        </div>
      </div>
    </template>
  </PipelineStage>
</template>
