<script setup lang="ts">
import { computed } from 'vue'

import PipelineStage from './PipelineStage.vue'
import PipelineRail from './PipelineRail.vue'
import ProblemAnalysisStage from './ProblemAnalysisStage.vue'
import KnowledgeRetrievalStage from './KnowledgeRetrievalStage.vue'
import AnswerCard from './AnswerCard.vue'
import type { AssistantPipeline, AssistantReply } from '@/contracts'

const props = defineProps<{
  reply: AssistantReply
  pipeline: AssistantPipeline
}>()

const stages = computed(() => [props.pipeline.analysis, props.pipeline.retrieval, props.pipeline.answer] as const)
</script>

<template>
  <div class="pipe" data-testid="agent-pipeline">
    <PipelineRail :stages="stages" />
    <ProblemAnalysisStage
      v-if="pipeline.analysis.visible || pipeline.analysis.status === 'unavailable'"
      :stage="pipeline.analysis"
    />
    <KnowledgeRetrievalStage
      v-if="pipeline.retrieval.visible || pipeline.retrieval.status === 'unavailable'"
      :stage="pipeline.retrieval"
    />
    <PipelineStage v-if="pipeline.answer.status === 'active'" :stage="pipeline.answer">
      <span class="typing" aria-label="正在生成"><i></i><i></i><i></i></span>
    </PipelineStage>
    <AnswerCard v-if="pipeline.answer.status === 'done' && pipeline.answer.visible" :reply="reply" />
  </div>
</template>
