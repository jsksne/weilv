<script setup lang="ts">
import SuggestedMiniTask from './SuggestedMiniTask.vue'
import SafetyNotice from './SafetyNotice.vue'
import EvidenceList from './EvidenceList.vue'
import type { AssistantReply } from '@/contracts'

defineProps<{
  reply: AssistantReply
}>()
</script>

<template>
  <article class="card answer-card" data-testid="answer-card">
    <span class="answer-glow"></span>
    <div class="answer-face"><span class="mini"></span>薇薇 · 已基于片段生成</div>
    <div class="answer-text">
      <template v-for="(segment, index) in reply.answer" :key="index">
        <br v-if="segment.breakBefore" />
        <b v-if="segment.emphasis">{{ segment.text }}</b>
        <template v-else>{{ segment.text }}</template>
      </template>
      <SafetyNotice v-if="reply.safety" :notice="reply.safety" />
      <SuggestedMiniTask v-if="reply.suggestedTask" :task="reply.suggestedTask" />
      <EvidenceList :sources="reply.sources" />
    </div>
  </article>
</template>
