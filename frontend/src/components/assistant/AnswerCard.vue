<script setup lang="ts">
import { computed } from 'vue'

import SuggestedMiniTask from './SuggestedMiniTask.vue'
import SafetyNotice from './SafetyNotice.vue'
import EvidenceList from './EvidenceList.vue'
import type { AssistantReply, SuggestedTaskState } from '@/contracts'

const props = defineProps<{
  reply: AssistantReply
  resolveTaskState?: (taskId: string) => SuggestedTaskState
}>()

const emit = defineEmits<{
  'activate-task': [task: NonNullable<AssistantReply['suggestedTask']>]
}>()

const answerFace = computed(() => {
  if (props.reply.safety) return '薇薇 · 已完成安全分流'
  if (props.reply.traceIsReal) return '薇薇 · 已基于本次真实执行'
  return '薇薇 · 已基于片段生成'
})
</script>

<template>
  <article class="card answer-card" data-testid="answer-card">
    <span class="answer-glow"></span>
    <div class="answer-face"><span class="mini"></span>{{ answerFace }}</div>
    <div class="answer-text">
      <template v-for="(segment, index) in reply.answer" :key="index">
        <br v-if="segment.breakBefore" />
        <b v-if="segment.emphasis">{{ segment.text }}</b>
        <template v-else>{{ segment.text }}</template>
      </template>
      <SafetyNotice v-if="reply.safety" :notice="reply.safety" />
      <p
        v-if="reply.considered && reply.considered.length > 0"
        class="considered-note"
        data-testid="considered-note"
      >
        <b>本次考虑</b>
        <span v-for="(item, index) in reply.considered" :key="index" class="considered-chip">{{ item }}</span>
        <span class="considered-tail">——这条推荐对应你这次给的条件。</span>
      </p>
      <SuggestedMiniTask
        v-if="reply.suggestedTask"
        :task="reply.suggestedTask"
        :state="resolveTaskState?.(reply.suggestedTask.taskId) ?? 'absent'"
        @activate="emit('activate-task', $event)"
      />
      <p v-if="reply.guardNotice" class="answer-guard-note" data-testid="answer-guard-notice">
        {{ reply.guardNotice }}
      </p>
      <EvidenceList :sources="reply.sources" />
    </div>
  </article>
</template>

<style scoped>
.considered-note {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin: 10px 0 2px;
  font-size: 12px;
  color: var(--ink-2, #7c6f86);
}

.considered-note b {
  color: var(--ink-1, #3f3348);
}

.considered-chip {
  padding: 2px 10px;
  border: 1px solid rgba(247, 143, 176, 0.42);
  border-radius: 999px;
  background: rgba(247, 143, 176, 0.1);
}

.considered-tail {
  color: var(--ink-2, #7c6f86);
}
</style>
