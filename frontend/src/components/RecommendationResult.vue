<script setup lang="ts">
import type { RecommendationResponse } from '@/api/types'
import EvidenceList from '@/components/EvidenceList.vue'

defineProps<{
  result: RecommendationResponse
}>()
</script>

<template>
  <article v-if="result.selected_task" data-testid="task-card">
    <h2>{{ result.selected_task.title }}</h2>
    <p>{{ result.selected_task.instruction }}</p>
    <p>约{{ result.selected_task.estimated_minutes }}分钟</p>

    <section v-if="result.explanation">
      <h3>为什么推荐这个行动</h3>
      <p>{{ result.explanation }}</p>
    </section>

    <p v-if="result.personalization?.memory_used">
      这次排序参考了你之前明确提交的任务反馈。
    </p>

    <section data-section="evidence">
      <h3>当前任务的正式依据</h3>
      <EvidenceList :sources="result.sources" />
    </section>

    <details v-if="result.context_sources?.length" data-section="context">
      <summary>背景知识</summary>
      <p>以下内容是与当前状态相关的背景知识，不是当前任务的正式依据。</p>
      <EvidenceList :sources="result.context_sources" />
    </details>
  </article>
</template>
