<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

import type { AssistantContract, AssistantQuickPrompt, AssistantScenario } from '@/contracts'
import AssistantHero from '@/components/assistant/AssistantHero.vue'
import QuickPromptList from '@/components/assistant/QuickPromptList.vue'
import ConversationLog from '@/components/assistant/ConversationLog.vue'
import UserMessage from '@/components/assistant/UserMessage.vue'
import AgentPipeline from '@/components/assistant/AgentPipeline.vue'
import ChatComposer from '@/components/assistant/ChatComposer.vue'
import { useAssistantFlow } from '@/composables/useAssistantFlow'

const props = defineProps<{
  model: AssistantContract
}>()

const { question, reply, pipeline, busy, renderVersion, submit: submitQuestion } = useAssistantFlow(props.model)
const log = ref<InstanceType<typeof ConversationLog> | null>(null)
const followLatest = ref(true)

function isNearBottom(): boolean {
  if (typeof window === 'undefined' || typeof document === 'undefined') return true
  const height = Math.max(document.documentElement.scrollHeight, document.body?.scrollHeight ?? 0)
  return window.scrollY + window.innerHeight >= height - 96
}

function rememberScrollPosition(): void {
  followLatest.value = isNearBottom()
}

function submit(question: string, scenario: AssistantScenario): void {
  rememberScrollPosition()
  submitQuestion(question, scenario)
}

function selectPrompt(prompt: AssistantQuickPrompt): void {
  submit(prompt.question, prompt.id)
}

function submitManual(question: string): void {
  submit(question, 'fallback')
}

watch(renderVersion, async () => {
  await nextTick()
  if (followLatest.value) {
    log.value?.latestMessage?.scrollIntoView?.({ behavior: 'smooth', block: 'end' })
  }
})

onMounted(() => window.addEventListener('scroll', rememberScrollPosition))
onUnmounted(() => window.removeEventListener('scroll', rememberScrollPosition))
</script>

<template>
  <div class="ask-wrap" :data-trace-real="model.traceIsReal">
    <div class="ask-bg" aria-hidden="true"><i class="g1"></i><i class="g2"></i><i class="g3"></i></div>
    <AssistantHero />
    <p
      v-if="model.isDemo"
      class="ask-foot"
      data-testid="demo-badge"
      style="margin: -10px 0 14px"
    >
      {{ model.demoLabel }}
    </p>
    <QuickPromptList :prompts="model.quickPrompts" :busy="busy" @select="selectPrompt" />
    <ConversationLog ref="log" :greeting="model.greeting">
      <UserMessage v-if="question" :text="question" />
      <AgentPipeline v-if="reply && pipeline" :reply="reply" :pipeline="pipeline" />
    </ConversationLog>
    <ChatComposer :busy="busy" @submit="submitManual" />
    <p class="ask-foot">
      回答基于审核知识库与你的历史记忆 · 薇薇不做医疗诊断<br />
      遇到持续不适，请第一时间告诉家长或老师
    </p>
  </div>
</template>

<style scoped>
.ask-wrap {
  overflow-x: clip;
}
</style>
