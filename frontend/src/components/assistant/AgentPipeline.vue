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

/** B3：可访问性状态文本——每收到一个真实阶段 transition 更新一次。 */
const liveStatus = computed(() => {
  const last = [...stages.value].reverse().find(stage => stage.status !== 'pending')
  return last ? last.statusLabel : ''
})
</script>

<template>
  <div class="pipe" data-testid="agent-pipeline">
    <span class="visually-hidden" role="status" aria-live="polite">{{ liveStatus }}</span>
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

<style scoped>
.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: -1px;
  padding: 0;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
  border: 0;
}
</style>
