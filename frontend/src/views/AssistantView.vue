<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

import type {
  AssistantContract,
  AssistantPipeline,
  AssistantQuickPrompt,
  AssistantReply,
  AssistantScenario,
  UiDataSource,
} from '@/contracts'
import AssistantHero from '@/components/assistant/AssistantHero.vue'
import QuickPromptList from '@/components/assistant/QuickPromptList.vue'
import ConversationLog from '@/components/assistant/ConversationLog.vue'
import UserMessage from '@/components/assistant/UserMessage.vue'
import AgentPipeline from '@/components/assistant/AgentPipeline.vue'
import ChatComposer from '@/components/assistant/ChatComposer.vue'
import { useAssistantFlow } from '@/composables/useAssistantFlow'
import { useAgenticRecommendation } from '@/composables/useAgenticRecommendation'

const props = defineProps<{
  model: AssistantContract
  dataSource?: UiDataSource
}>()

const demoFlow = useAssistantFlow(props.model)
const agenticFlow = useAgenticRecommendation(props.dataSource ?? null)
const isDemo = computed(() => props.model.state.mode === 'demo')
const question = computed(() => (isDemo.value ? demoFlow.question.value : agenticFlow.question.value))
const reply = computed<AssistantReply | null>(() =>
  isDemo.value ? demoFlow.reply.value : agenticFlow.reply.value,
)
const pipeline = computed<AssistantPipeline | null>(() =>
  isDemo.value
    ? demoFlow.pipeline.value
    : agenticFlow.pipeline.value ?? reply.value?.pipeline ?? null,
)
const busy = computed(() => (isDemo.value ? demoFlow.busy.value : agenticFlow.busy.value))
const renderVersion = computed(() =>
  isDemo.value ? demoFlow.renderVersion.value : agenticFlow.renderVersion.value,
)
const error = computed(() => (isDemo.value ? null : agenticFlow.error.value))
const log = ref<InstanceType<typeof ConversationLog> | null>(null)
const followLatest = ref(true)

/** B3：流式期间 reply 尚未落地，用占位 reply 驱动真实 live pipeline。 */
const pendingReply: AssistantReply = {
  id: 'streaming-trace',
  scenario: null,
  pipeline: {
    analysis: {
      id: 'analysis', title: '问题拆解', status: 'pending', statusLabel: '等待开始',
      statusLabels: {}, visible: true, lead: null, items: [],
    },
    retrieval: {
      id: 'retrieval', title: '知识检索', status: 'pending', statusLabel: '等待开始',
      statusLabels: {}, visible: true, chunks: [],
    },
    answer: {
      id: 'answer', title: '回答', status: 'pending', statusLabel: '等待开始',
      statusLabels: {}, visible: false,
    },
  },
  answer: [],
  suggestedTask: null,
  safety: null,
  sources: [],
  traceIsReal: true,
  timing: null,
}

function isNearBottom(): boolean {
  if (typeof window === 'undefined' || typeof document === 'undefined') return true
  const height = Math.max(document.documentElement.scrollHeight, document.body?.scrollHeight ?? 0)
  return window.scrollY + window.innerHeight >= height - 96
}

function rememberScrollPosition(): void {
  followLatest.value = isNearBottom()
}

function submit(question: string, scenario: AssistantScenario): void {
  if (isDemo.value) demoFlow.submit(question, scenario)
  else void agenticFlow.submit(question)
}

function selectPrompt(prompt: AssistantQuickPrompt): void {
  submit(prompt.question, prompt.id)
}

function submitManual(question: string): void {
  submit(question, 'fallback')
}

function retry(): void {
  if (question.value) submit(question.value, 'fallback')
}

watch(renderVersion, async () => {
  await nextTick()
  if (followLatest.value) {
    const root = log.value?.$el as HTMLElement | undefined
    const target = root?.querySelector<HTMLElement>('[data-testid="agent-pipeline"]') ?? log.value?.latestMessage
    target?.scrollIntoView?.({ behavior: 'smooth', block: 'end' })
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
    <p v-if="error" class="ask-error" data-testid="agentic-error" role="alert">
      {{ error.message }}
      <button class="btn btn-ghost" type="button" @click="retry">重试</button>
    </p>
    <ConversationLog ref="log" :greeting="model.greeting">
      <UserMessage v-if="question" :text="question" />
      <AgentPipeline v-if="pipeline" :reply="reply ?? pendingReply" :pipeline="pipeline" />
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

.ask-wrap :deep(.stage-card),
.ask-wrap :deep(.answer-card),
.ask-wrap :deep(.ask-input) {
  margin-top: 0;
}

.ask-wrap :deep(.ask-input input) {
  margin-top: 0;
}
</style>
