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
const streamFallbackUsed = computed(() =>
  isDemo.value ? false : agenticFlow.streamFallbackUsed.value,
)
const latestMessage = ref<HTMLElement | null>(null)
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
  // 新问题默认重新跟随；之后主动上滑仍可退出本轮自动跟随。
  followLatest.value = true
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

function scrollToLatestAnchor(): void {
  const target = latestMessage.value
  if (!target?.scrollIntoView) return

  // 全局导航使用平滑滚动；流式更新临时切到即时滚动，避免动画排队。
  const root = document.documentElement
  const previousScrollBehavior = root.style.scrollBehavior
  root.style.scrollBehavior = 'auto'
  try {
    target.scrollIntoView({ behavior: 'auto', block: 'end' })
  } finally {
    root.style.scrollBehavior = previousScrollBehavior
  }
}

function returnToLatest(): void {
  followLatest.value = true
  scrollToLatestAnchor()
}

watch(renderVersion, async () => {
  await nextTick()
  if (followLatest.value) {
    // 流式管线会持续增高，始终跟随整个页面的真实底部锚点。
    scrollToLatestAnchor()
  }
})

onMounted(() => window.addEventListener('scroll', rememberScrollPosition))
onUnmounted(() => window.removeEventListener('scroll', rememberScrollPosition))
</script>

<template>
  <div class="ask-wrap" :data-trace-real="reply?.traceIsReal ?? model.traceIsReal">
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
    <ConversationLog :greeting="model.greeting">
      <UserMessage v-if="question" :text="question" />
      <AgentPipeline v-if="pipeline" :reply="reply ?? pendingReply" :pipeline="pipeline" />
    </ConversationLog>
    <p v-if="streamFallbackUsed && reply" class="ask-foot" data-testid="stream-fallback-note">
      ✦ 本次回答由完整模式完成（流式通道暂不可用），流程与结果一致。
    </p>
    <ChatComposer :busy="busy" @submit="submitManual" />
    <p class="ask-foot">
      回答基于审核知识库和你提供的信息 · 薇薇不做医疗诊断<br />
      遇到持续不适，请第一时间告诉家长或老师
    </p>
    <button
      v-if="question && !followLatest"
      class="return-to-latest"
      data-testid="return-to-latest"
      type="button"
      aria-label="回到最新回答"
      @click="returnToLatest"
    >
      <span aria-hidden="true">↓</span>
      回到最新
    </button>
    <span ref="latestMessage" class="latest-message-anchor" data-testid="latest-message" aria-hidden="true"></span>
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

.return-to-latest {
  position: fixed;
  right: max(16px, calc((100vw - 820px) / 2 + 16px));
  bottom: calc(16px + env(safe-area-inset-bottom, 0px));
  z-index: 45;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-height: 44px;
  padding: 0 17px;
  border: 1px solid rgba(247, 143, 176, 0.42);
  border-radius: 999px;
  background: rgba(255, 250, 252, 0.96);
  color: var(--ink-1);
  box-shadow: 0 8px 24px rgba(110, 74, 118, 0.18);
  font: inherit;
  font-size: 12px;
  letter-spacing: 0.5px;
  cursor: pointer;
  animation: msgIn 0.28s var(--ease-decay) both;
}

.return-to-latest:focus-visible {
  outline: 3px solid rgba(157, 123, 223, 0.38);
  outline-offset: 3px;
}

@media (hover: hover) {
  .return-to-latest:hover {
    transform: translateY(-2px);
    box-shadow: 0 11px 28px rgba(110, 74, 118, 0.23);
  }
}
</style>
