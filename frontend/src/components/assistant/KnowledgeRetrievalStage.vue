<script setup lang="ts">
import PipelineStage from './PipelineStage.vue'
import KnowledgeChunk from './KnowledgeChunk.vue'
import type { AssistantRetrievalStage } from '@/contracts'

defineProps<{
  stage: AssistantRetrievalStage
}>()
</script>

<template>
  <PipelineStage :stage="stage">
    <p v-if="stage.status === 'unavailable'" class="stage-lead">
      后端没有提供实时检索阶段、片段正文或相关度。
    </p>
    <span v-else-if="stage.status === 'active'" class="typing" aria-label="正在检索">
      <i></i><i></i><i></i>
    </span>
    <template v-else>
      <details v-if="stage.chunks.length" class="retrieval-evidence" data-testid="retrieval-evidence">
        <summary class="stage-lead">找到 {{ stage.chunks.length }} 条审核依据</summary>
        <div>
          <KnowledgeChunk v-for="chunk in stage.chunks" :key="chunk.id" :chunk="chunk" />
        </div>
      </details>
      <p v-if="!stage.chunks.length" class="stage-lead">
        已完成检索；本次回答没有可公开的来源条目。
      </p>
    </template>
  </PipelineStage>
</template>
