<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'

import type { TodayContract, TodayTaskView } from '@/contracts'
import type { DailyTaskEntry, DailyTasksController } from '@/composables/useDailyTasks'
import { useMotionPulse } from '@/composables/useMotionPulse'
import { useToast } from '@/composables/useToast'
import TaskCompletionFx from '@/components/effects/TaskCompletionFx.vue'

/**
 * 冻结原型任务卡（923-963 行 + 交互脚本 1440-1496 行）。
 *
 * - 按钮组随 actions stage 渲染（原型按 innerHTML 替换的四种形态）；
 * - done：badge/done-note/进度由 controller 驱动，卡片 scale(1+0.02v)
 *   950ms 脉冲 + TaskCompletionFx（.task-state 视觉中心）；
 * - partial：较轻 scale(1+0.012v) 700ms 脉冲；
 * - start：translateY(-3v) 700ms 脉冲；
 * - replace：rise 450ms 左移淡出 → 470ms 换内容 → decay 600ms 回位
 *   （displayTask 本地镜像延迟切换，其余内容变更即时跟随）；
 * - 冷却由 controller 判定，cooldown 结果不产生任何视觉反馈（与原型一致）。
 */
const props = defineProps<{
  entry: DailyTaskEntry
  controller: DailyTasksController
  copy: TodayContract['feedbackCopy']
  canReplace?: boolean
  /** F6：轻反馈走正式反馈链路（仅完成/部分完成后出现一次）。 */
  submitLightFeedback?: (
    task: TodayTaskView,
    completionStatus: 'completed' | 'partially_completed',
    usefulness: 'helpful' | 'neutral' | 'not_helpful',
  ) => Promise<{ status: string }>
}>()

const emit = defineEmits<{
  'open-panel': [entry: DailyTaskEntry]
  unsuitable: [entry: DailyTaskEntry]
}>()

const { play, delay, dispose } = useMotionPulse()
const { push } = useToast()
const submitting = ref(false)

/* ---------- F6：完成后一次轻反馈 ---------- */
type LightFeedbackState = 'idle' | 'saving' | 'sent' | 'failed'
const feedbackState = ref<LightFeedbackState>('idle')

const pendingOwnFeedback = computed(() =>
  props.controller.pendingFeedback.value.find(
    item => item.slotId === props.entry.slotId &&
      (item.completionStatus === 'completed' || item.completionStatus === 'partially_completed'),
  ),
)

const showFeedbackPrompt = computed(
  () =>
    !!props.submitLightFeedback &&
    !!pendingOwnFeedback.value &&
    (feedbackState.value === 'idle' || feedbackState.value === 'failed'),
)

const FEEDBACK_CHOICES = [
  { key: 'helpful', label: '合适', usefulness: 'helpful' as const, difficulty: 'easy' as const },
  { key: 'hard', label: '有点费劲', usefulness: 'neutral' as const, difficulty: 'difficult' as const },
  { key: 'unhelpful', label: '没什么帮助', usefulness: 'not_helpful' as const, difficulty: 'suitable' as const },
]

async function sendLightFeedback(usefulness: 'helpful' | 'neutral' | 'not_helpful', difficulty: 'easy' | 'difficult' | 'suitable'): Promise<void> {
  const pending = pendingOwnFeedback.value
  if (!pending || pending.completionStatus === 'skipped') return
  if (!pending || !props.submitLightFeedback || feedbackState.value === 'saving') return
  feedbackState.value = 'saving'
  try {
    const result = await props.submitLightFeedback(
      props.entry.task,
      pending.completionStatus,
      usefulness,
    )
    feedbackState.value = result.status === 'recorded' ? 'sent' : 'failed'
    if (feedbackState.value === 'failed') push('评价没有记上，可以再试一次')
  } catch {
    feedbackState.value = 'failed'
    push('评价没有记上，可以再试一次')
  }
}

const toneClass = computed(() =>
  props.entry.task.tone === 'default' ? undefined : `t-${props.entry.task.tone}`,
)
const stateClass = computed(() => {
  if (props.entry.interaction === 'done') return 'done'
  if (props.entry.interaction === 'partial') return 'partial'
  if (props.entry.interaction === 'skipped') return 'skippedcard'
  return undefined
})

const badgeText = computed(() => {
  if (props.entry.interaction === 'partial') return '部分完成 · 也算数哦'
  if (props.entry.interaction === 'skipped') return '跳过了 · 没关系呀'
  return '完成 · 今天的花瓣 +1'
})

const doneNote = computed(() =>
  props.entry.interaction === 'partial' ? '🌱 部分完成 · 已记下' : '🌸 已记下 · 今天的一片花瓣',
)

/* ---------- replace 动画的本地内容镜像 ---------- */

const replacePhase = ref<'idle' | 'out' | 'in'>('idle')
const displayTask = ref<TodayTaskView>(props.entry.task)

watch(
  () => props.entry.task,
  task => {
    if (replacePhase.value === 'idle') displayTask.value = task
  },
)

/* ---------- 卡片运动样式（脉冲 + 换卡两相） ---------- */

const pulseTransform = ref('')
const cardStyle = computed(() => {
  if (replacePhase.value === 'out') {
    return {
      transform: 'translateX(-40px) rotate(-1.5deg)',
      opacity: '0',
      transition: 'transform .45s var(--ease-rise), opacity .45s var(--ease-rise)',
    }
  }
  if (replacePhase.value === 'in') {
    return {
      transform: 'none',
      opacity: '1',
      transition: 'transform .6s var(--ease-decay), opacity .6s var(--ease-decay)',
    }
  }
  return pulseTransform.value ? { transform: pulseTransform.value } : undefined
})

/* ---------- 完成特效 ---------- */

const fx = ref<InstanceType<typeof TaskCompletionFx> | null>(null)
const taskState = ref<HTMLElement | null>(null)

function playCompletionFx(): void {
  const rect = taskState.value?.getBoundingClientRect()
  if (!rect) return
  fx.value?.play(rect.left + rect.width / 2, rect.top + rect.height / 2)
}

/* ---------- 动作分发 ---------- */

function pulseCard(durationMs: number, scale: (v: number) => string): void {
  play(
    durationMs,
    v => {
      pulseTransform.value = scale(v)
    },
    () => {
      pulseTransform.value = ''
    },
  )
}

function animateReplace(): void {
  replacePhase.value = 'out'
  delay(470, () => {
    displayTask.value = props.entry.task
    replacePhase.value = 'in'
    delay(600, () => {
      replacePhase.value = 'idle'
      displayTask.value = props.entry.task
    })
  })
}

function notify(message: string): void {
  if (message) push(message)
}

function applyResult(
  act: 'start' | 'done' | 'partial' | 'skip' | 'restore' | 'replace',
  result: Awaited<ReturnType<DailyTasksController['start']>>,
): void {
  if (result === 'submission-failed') {
    notify('这次没有记上，请检查网络后重试')
    return
  }
  if (result !== 'applied') return

  if (act === 'start') {
    /* F3：开始后直接进入执行界面；关闭面板不结束任务。 */
    emit('open-panel', props.entry)
    pulseCard(700, v => `translateY(${-3 * v}px)`)
    notify(props.copy.start)
    return
  }
  if (act === 'done') {
    playCompletionFx()
    pulseCard(950, v => `scale(${1 + 0.02 * v})`)
    notify(props.copy.done)
    return
  }
  if (act === 'partial') {
    pulseCard(700, v => `scale(${1 + 0.012 * v})`)
    notify(props.copy.partial)
    return
  }
  if (act === 'skip') {
    notify(props.copy.skip)
    return
  }
  if (act === 'replace') {
    animateReplace()
    notify(props.copy.replace)
  }
}

function run(act: 'start' | 'done' | 'partial' | 'skip' | 'restore' | 'replace'): void {
  if (submitting.value) return
  const slotId = props.entry.slotId
  const method = act === 'done' ? 'complete' : act
  const result = props.controller[method](slotId)
  if (result instanceof Promise) {
    submitting.value = true
    void result.then(resolved => applyResult(act, resolved)).finally(() => {
      submitting.value = false
    })
  } else {
    applyResult(act, result)
  }
}

onUnmounted(dispose)
</script>

<template>
  <article
    class="card task-card"
    :class="[toneClass, stateClass]"
    :style="cardStyle"
    :aria-busy="submitting || undefined"
    :data-task-id="displayTask.id"
    tabindex="-1"
  >
    <div class="task-top">
      <span class="task-domain">{{ displayTask.domain }}</span>
      <span class="task-meta">{{ displayTask.meta }}</span>
    </div>
    <h3 class="task-name">{{ displayTask.name }}</h3>
    <p class="task-desc">{{ displayTask.description }}</p>
    <div class="task-why">
      <span class="why-icon"><svg class="ic"><use :href="`#${displayTask.whyIcon}`" /></svg></span>
      <div>
        <b>为什么是它</b>
        <p>{{ displayTask.why }}</p>
      </div>
    </div>

    <div class="task-actions">
      <template v-if="entry.actions === 'initial'">
        <button class="btn btn-primary" type="button" data-act="start" :disabled="submitting" @click="run('start')">开始</button>
        <button
          v-if="canReplace"
          class="btn btn-ghost"
          type="button"
          data-act="replace"
          :disabled="submitting"
          @click="run('replace')"
        >换一朵</button>
        <button class="btn btn-ghost" type="button" data-act="skip" :disabled="submitting" @click="run('skip')">先跳过</button>
        <button class="btn btn-ghost" type="button" data-act="unsuitable" :disabled="submitting" @click="emit('unsuitable', props.entry)">现在不适合</button>
      </template>
      <template v-else-if="entry.actions === 'active'">
        <button class="btn btn-ok" type="button" data-act="done" :disabled="submitting" @click="run('done')">✓ 完成啦</button>
        <button class="btn btn-ghost" type="button" data-act="partial" :disabled="submitting" @click="run('partial')">部分完成</button>
        <button
          v-if="canReplace"
          class="btn btn-ghost"
          type="button"
          data-act="replace"
          :disabled="submitting"
          @click="run('replace')"
        >换一朵</button>
        <button class="btn btn-ghost" type="button" data-act="skip" :disabled="submitting" @click="run('skip')">先跳过</button>
        <button class="btn btn-ghost" type="button" data-act="panel" :disabled="submitting" @click="emit('open-panel', props.entry)">看怎么做</button>
      </template>
      <template v-else-if="entry.actions === 'restore'">
        <button class="btn btn-ghost" type="button" data-act="restore" :disabled="submitting" @click="run('restore')">恢复它</button>
      </template>
      <span v-else class="done-note">{{ doneNote }}</span>
    </div>

    <div ref="taskState" class="task-state">
      <svg viewBox="0 0 46 46">
        <circle class="ck-ring" cx="23" cy="23" r="21" />
        <path class="ck-path" d="M14 24 L20.5 30.5 L33 16.5" />
      </svg>
    </div>
    <div class="task-badge">
      <span class="bdot"></span>
      <span class="badge-txt">{{ badgeText }}</span>
    </div>

    <div v-if="showFeedbackPrompt" class="light-feedback" data-testid="light-feedback">
      <span class="lf-q">这次感觉怎么样？</span>
      <button
        v-for="choice in FEEDBACK_CHOICES"
        :key="choice.key"
        class="btn btn-ghost"
        type="button"
        :data-feedback="choice.key"
        :disabled="feedbackState === 'saving'"
        @click="sendLightFeedback(choice.usefulness, choice.difficulty)"
      >{{ choice.label }}</button>
      <span v-if="feedbackState === 'failed'" class="lf-failed">没有记上，再点一次即可</span>
    </div>

    <TaskCompletionFx ref="fx" />
  </article>
</template>
