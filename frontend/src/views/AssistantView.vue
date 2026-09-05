<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

import type {
  AssistantContract,
  AssistantPipeline,
  AssistantQuickPrompt,
  AssistantReply,
  AssistantScenario,
  AssistantSuggestedTask,
  UiDataSource,
} from '@/contracts'
import type { ConversationMessage } from '@/composables/useAgenticRecommendation'
import AssistantHero from '@/components/assistant/AssistantHero.vue'
import QuickPromptList from '@/components/assistant/QuickPromptList.vue'
import ConversationLog from '@/components/assistant/ConversationLog.vue'
import UserMessage from '@/components/assistant/UserMessage.vue'
import AgentPipeline from '@/components/assistant/AgentPipeline.vue'
import ChatComposer from '@/components/assistant/ChatComposer.vue'
import { useAssistantFlow } from '@/composables/useAssistantFlow'
import { useAgenticRecommendation } from '@/composables/useAgenticRecommendation'
import { useToast } from '@/composables/useToast'

import type { SuggestedTaskState } from '@/contracts'

const props = defineProps<{
  model: AssistantContract
  dataSource?: UiDataSource
  resolveTaskState?: (taskId: string) => SuggestedTaskState
}>()

const emit = defineEmits<{
  'activate-task': [task: AssistantSuggestedTask]
}>()

const demoFlow = useAssistantFlow(props.model)
const agenticFlow = useAgenticRecommendation(props.dataSource ?? null)
const isDemo = computed(() => props.model.state.mode === 'demo')
const question = computed(() => (isDemo.value ? demoFlow.question.value : null))
const reply = computed<AssistantReply | null>(() =>
  isDemo.value ? demoFlow.reply.value : null,
)
const pipeline = computed<AssistantPipeline | null>(() =>
  isDemo.value
    ? demoFlow.pipeline.value
    : null,
)
const busy = computed(() => (isDemo.value ? demoFlow.busy.value : agenticFlow.busy.value))
const renderVersion = computed(() =>
  isDemo.value ? demoFlow.renderVersion.value : agenticFlow.renderVersion.value,
)
const messages = computed(() => (isDemo.value ? [] : agenticFlow.messages.value))
/** traceIsReal 以最新回答为准；等待中沿用契约默认。 */
const traceIsReal = computed(() => {
  if (isDemo.value) return props.model.traceIsReal
  const complete = agenticFlow.messages.value.filter(message => message.status === 'complete')
  return complete[complete.length - 1]?.reply?.traceIsReal ?? props.model.traceIsReal
})
const latestStreamFallbackUsed = computed<boolean>(() => {
  const complete = agenticFlow.messages.value.filter(message => message.status === 'complete')
  return complete[complete.length - 1]?.streamFallbackUsed ?? false
})
const followLatest = ref(true)
const latestMessage = ref<HTMLElement | null>(null)
const { push } = useToast()
/** 🌿 轻一点：开启后本会话后续请求都在安全候选内优先容易开始的短任务。 */
const easyStart = ref(false)

/** 完整回答渲染其静态 pipeline；等待中渲染实时 trace pipeline。 */
function messagePipeline(message: ConversationMessage): AssistantPipeline | null {
  return message.pipeline ?? message.reply?.pipeline ?? null
}

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
  else void agenticFlow.submit(question, { easyStart: easyStart.value })
}

function toggleEasyStart(value: boolean): void {
  easyStart.value = value
  push(value ? '好，接下来优先容易开始的小事' : '已恢复常规推荐')
}

function selectPrompt(prompt: AssistantQuickPrompt): void {
  submit(prompt.question, prompt.id)
}

function submitManual(question: string): void {
  submit(question, 'fallback')
}

function retryMessage(messageId: number): void {
  followLatest.value = true
  void agenticFlow.retry(messageId)
}

function startNewConversation(): void {
  if (agenticFlow.startNewConversation()) {
    push('已开始新对话；今日任务和记录都保留')
  }
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
  <div class="ask-wrap" :data-trace-real="traceIsReal">
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
    <div class="ask-toolbar">
      <QuickPromptList :prompts="model.quickPrompts" :busy="busy" @select="selectPrompt" />
      <button
        v-if="!isDemo && messages.length > 0"
        class="btn btn-ghost new-conversation"
        data-testid="new-conversation"
        type="button"
        :disabled="busy"
        @click="startNewConversation"
      >
        新对话
      </button>
    </div>
    <ConversationLog :greeting="model.greeting">
      <!-- Demo：保留冻结原型的单轮展示。 -->
      <template v-if="isDemo">
        <UserMessage v-if="question" :text="question" />
        <AgentPipeline
          v-if="pipeline"
          :reply="reply ?? pendingReply"
          :pipeline="pipeline"
          :resolve-task-state="resolveTaskState"
          @activate-task="emit('activate-task', $event)"
        />
      </template>
      <!-- Production：按顺序保留整轮会话；旧问答不因新提问消失。 -->
      <template v-else>
        <template v-for="message in messages" :key="message.id">
          <UserMessage :text="message.question" />
          <p
            v-if="message.status === 'stopped'"
            class="ask-foot"
            data-testid="stopped-note"
          >
            已停止等待这条回答；已显示的内容保留，你可以继续追问。
          </p>
          <AgentPipeline
            v-if="message.status !== 'error' && messagePipeline(message)"
            :reply="message.reply ?? pendingReply"
            :pipeline="messagePipeline(message)"
            :resolve-task-state="resolveTaskState"
            @activate-task="emit('activate-task', $event)"
          />
          <p
            v-if="message.status === 'error'"
            class="ask-error"
            data-testid="agentic-error"
            role="alert"
          >
            {{ message.errorMessage ?? '这次没有完成回答。' }}
            <button class="btn btn-ghost" type="button" @click="retryMessage(message.id)">
              重试
            </button>
          </p>
        </template>
      </template>
    </ConversationLog>
    <p
      v-if="latestStreamFallbackUsed"
      class="ask-foot"
      data-testid="stream-fallback-note"
    >
      ✦ 最新这条回答由完整模式完成（流式通道暂不可用），流程与结果一致。
    </p>
    <ChatComposer
      :busy="busy"
      :easy-start="easyStart"
      @submit="submitManual"
      @toggle-easy-start="toggleEasyStart"
    />
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

.ask-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 10px;
}

.ask-toolbar :deep(.quick-prompts) {
  flex: 1 1 auto;
}

.new-conversation {
  flex: 0 0 auto;
  white-space: nowrap;
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
